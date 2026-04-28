"""generate_image_bot.py のユニットテスト"""

import asyncio
import json
import re
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from generate_image_bot import (
    load_config,
    MessageParser,
    RateLimiter,
    GenImageModal,
    ImageBot,
    write_log,
    _parse_shutdown_time,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def valid_config() -> dict:
    return {
        "discord_token": "test_token",
        "comfyui_output_dir": "C:/output",
        "run_workflow_config": "../run_workflow/config.json",
        "reactions": {
            "processing": "⏳",
            "success": "✅",
            "error": "❌",
        },
        "messages": {
            "rate_limit": "あと {remaining_seconds} 秒待ってください。",
            "generating": "現在生成中です。しばらくお待ちください。",
            "parse_error": "形式が正しくありません: {error}",
            "execution_error": "生成に失敗しました: {error}",
            "file_too_large": "画像が大きすぎます（{size_mb} MB）",
            "unexpected_error": "予期しないエラーが発生しました",
            "dm_not_supported": "DM からは使用できません。",
            "shutdown_in_progress": "シャットダウン中です。",
        },
    }


def write_config(path: Path, data: dict) -> str:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


def make_bot_for_test(config: dict, runner, output_dir=None) -> ImageBot:
    if output_dir is not None:
        config = {**config, "comfyui_output_dir": str(output_dir)}
    with patch.object(discord.Client, "__init__", return_value=None):
        bot = ImageBot(config, runner)
    # discord.Client.user は _connection.user を参照するため両方設定する
    bot._connection = MagicMock()
    bot._connection.user = MagicMock(name="bot_user")
    return bot


def make_message(bot_user, content: str, guild_set: bool = True, is_own: bool = False):
    msg = MagicMock()
    if is_own:
        msg.author = bot_user
    else:
        msg.author = MagicMock(id=99999)
        msg.author.name = "testuser"
    msg.content = content
    msg.guild = MagicMock() if guild_set else None
    msg.mentions = [bot_user]
    msg.add_reaction = AsyncMock()
    msg.remove_reaction = AsyncMock()
    msg.reply = AsyncMock()
    msg.channel = MagicMock()
    msg.channel.send = AsyncMock()
    return msg


VALID_CONTENT = "<@1>\npositive: 1girl\nnegative: bad quality"
VALID_OUTPUTS = [{"filename": "output.png", "subfolder": "", "type": "output"}]


# ── load_config ───────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_valid_config(self, tmp_path):
        path = write_config(tmp_path / "config.json", valid_config())
        config = load_config(path)
        assert config["discord_token"] == "test_token"
        assert config["comfyui_output_dir"] == "C:/output"
        assert config["reactions"]["processing"] == "⏳"
        assert (
            config["messages"]["unexpected_error"] == "予期しないエラーが発生しました"
        )

    def test_file_not_found(self, tmp_path):
        with pytest.raises(ValueError, match="見つかりません"):
            load_config(str(tmp_path / "nonexistent.json"))

    def test_invalid_json(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="解析に失敗"):
            load_config(str(path))

    @pytest.mark.parametrize(
        "key", ["discord_token", "comfyui_output_dir", "run_workflow_config"]
    )
    def test_missing_top_level_key(self, tmp_path, key):
        data = valid_config()
        del data[key]
        path = write_config(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match=key):
            load_config(path)

    @pytest.mark.parametrize(
        "key", ["discord_token", "comfyui_output_dir", "run_workflow_config"]
    )
    def test_empty_top_level_string(self, tmp_path, key):
        data = valid_config()
        data[key] = "   "
        path = write_config(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match=key):
            load_config(path)

    def test_missing_reactions(self, tmp_path):
        data = valid_config()
        del data["reactions"]
        path = write_config(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match="reactions"):
            load_config(path)

    @pytest.mark.parametrize("key", ["processing", "success", "error"])
    def test_missing_reaction_key(self, tmp_path, key):
        data = valid_config()
        del data["reactions"][key]
        path = write_config(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match=key):
            load_config(path)

    @pytest.mark.parametrize("key", ["processing", "success", "error"])
    def test_empty_reaction_value(self, tmp_path, key):
        data = valid_config()
        data["reactions"][key] = ""
        path = write_config(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match=f"reactions.{key}"):
            load_config(path)

    def test_missing_messages(self, tmp_path):
        data = valid_config()
        del data["messages"]
        path = write_config(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match="messages"):
            load_config(path)

    @pytest.mark.parametrize(
        "key",
        [
            "rate_limit",
            "generating",
            "parse_error",
            "execution_error",
            "file_too_large",
            "unexpected_error",
            "dm_not_supported",
            "shutdown_in_progress",
        ],
    )
    def test_missing_message_key(self, tmp_path, key):
        data = valid_config()
        del data["messages"][key]
        path = write_config(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match=key):
            load_config(path)

    @pytest.mark.parametrize(
        "key",
        [
            "rate_limit",
            "generating",
            "parse_error",
            "execution_error",
            "file_too_large",
            "unexpected_error",
            "dm_not_supported",
            "shutdown_in_progress",
        ],
    )
    def test_message_value_not_string(self, tmp_path, key):
        data = valid_config()
        data["messages"][key] = 123
        path = write_config(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match=f"messages.{key}"):
            load_config(path)


# ── MessageParser ─────────────────────────────────────────────────────────────


class TestMessageParser:
    def setup_method(self):
        self.parser = MessageParser()

    def test_basic_parse(self):
        text = "<@123456>\nloras: my_lora\npositive: 1girl\nnegative: bad quality"
        result = self.parser.parse(text)
        assert result["loras"] == ["my_lora"]
        assert result["positive"] == "1girl"
        assert result["negative"] == "bad quality"

    def test_no_loras_key(self):
        # loras: を省略した場合は空リストになる
        text = "<@123456>\npositive: 1girl\nnegative: bad quality"
        result = self.parser.parse(text)
        assert result["loras"] == []

    def test_multiple_loras(self):
        text = "<@123456>\nloras: lora1, lora2, lora3\npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["loras"] == ["lora1", "lora2", "lora3"]

    def test_loras_strips_spaces(self):
        text = "<@123456>\nloras:  lora1 ,  lora2  \npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["loras"] == ["lora1", "lora2"]

    def test_loras_colon_only_gives_empty_list(self):
        # loras: の後に値がない場合は空リスト
        text = "<@123456>\nloras:\npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["loras"] == []

    def test_multiline_positive(self):
        text = "<@123456>\npositive: 1girl,\n(detailed face:1.3), solo\nnegative: bad"
        result = self.parser.parse(text)
        assert "1girl" in result["positive"]
        assert "(detailed face:1.3), solo" in result["positive"]

    def test_multiline_negative(self):
        text = (
            "<@123456>\npositive: 1girl\nnegative: worst quality,\nbad quality,\nblurry"
        )
        result = self.parser.parse(text)
        assert "worst quality" in result["negative"]
        assert "blurry" in result["negative"]

    def test_colon_in_prompt_value(self):
        # 強調構文の : はキーワードと誤認識されない
        text = "<@123456>\npositive: (face:1.3), (eyes:1.2)\nnegative: bad"
        result = self.parser.parse(text)
        assert result["positive"] == "(face:1.3), (eyes:1.2)"

    def test_mention_not_in_result(self):
        # メンションが値に混入しない
        text = "<@123456> <@!789012>\npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert "<@" not in result["positive"]
        assert "<@" not in result["negative"]

    def test_mention_inline_with_keyword(self):
        # メンションと同じ行にキーワードがある場合でも正しくパースされる
        text = "<@123456> positive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["positive"] == "1girl"

    def test_text_before_first_keyword_ignored(self):
        # キーワード前のテキストは無視される
        text = "<@123456>\nplease generate this\npositive: 1girl\nnegative: bad"
        result = self.parser.parse(text)
        assert result["positive"] == "1girl"

    def test_keywords_case_insensitive(self):
        text = "<@123456>\nPositive: 1girl\nNEGATIVE: bad"
        result = self.parser.parse(text)
        assert result["positive"] == "1girl"
        assert result["negative"] == "bad"

    def test_missing_positive_raises(self):
        text = "<@123456>\nnegative: bad quality"
        with pytest.raises(ValueError, match="positive"):
            self.parser.parse(text)

    def test_missing_negative_raises(self):
        text = "<@123456>\npositive: 1girl"
        with pytest.raises(ValueError, match="negative"):
            self.parser.parse(text)

    def test_strips_leading_trailing_whitespace_from_values(self):
        text = "<@123456>\npositive:   1girl   \nnegative:   bad   "
        result = self.parser.parse(text)
        assert result["positive"] == "1girl"
        assert result["negative"] == "bad"


# ── RateLimiter ───────────────────────────────────────────────────────────────


class TestRateLimiter:
    def setup_method(self):
        self.limiter = RateLimiter()

    def test_new_user_not_limited(self):
        assert self.limiter.check_user(1) == 0.0

    def test_immediately_after_record_is_limited(self):
        self.limiter.record_request(1)
        assert self.limiter.check_user(1) > 0.0

    def test_remaining_seconds_near_cooldown_after_record(self):
        self.limiter.record_request(1)
        remaining = self.limiter.check_user(1)
        assert remaining <= RateLimiter.COOLDOWN_SECONDS

    def test_remaining_decreases_over_time(self):
        with patch("generate_image_bot.time.monotonic") as mock_time:
            mock_time.return_value = 1000.0
            self.limiter.record_request(1)
            mock_time.return_value = 1015.0
            remaining = self.limiter.check_user(1)
            assert 14.9 < remaining <= 15.0

    def test_after_cooldown_not_limited(self):
        with patch("generate_image_bot.time.monotonic") as mock_time:
            mock_time.return_value = 1000.0
            self.limiter.record_request(1)
            mock_time.return_value = 1000.0 + RateLimiter.COOLDOWN_SECONDS + 1
            assert self.limiter.check_user(1) == 0.0

    def test_different_users_are_independent(self):
        self.limiter.record_request(1)
        assert self.limiter.check_user(2) == 0.0

    def test_generating_initially_false(self):
        assert self.limiter.is_generating() is False

    def test_set_generating_true(self):
        self.limiter.set_generating(True)
        assert self.limiter.is_generating() is True

    def test_set_generating_false_after_true(self):
        self.limiter.set_generating(True)
        self.limiter.set_generating(False)
        assert self.limiter.is_generating() is False

    def test_generating_flag_independent_of_rate_limit(self):
        # 生成ロックとレート制限は独立して動作する
        self.limiter.record_request(1)
        self.limiter.set_generating(True)
        assert self.limiter.check_user(1) > 0.0
        assert self.limiter.is_generating() is True

        self.limiter.set_generating(False)
        assert self.limiter.check_user(1) > 0.0
        assert self.limiter.is_generating() is False


# ── ImageBot: on_message フィルタリング ────────────────────────────────────────


class TestImageBotOnMessage:
    def test_ignores_own_message(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        msg = make_message(bot.user, VALID_CONTENT, is_own=True)
        asyncio.run(bot.on_message(msg))
        msg.add_reaction.assert_not_called()

    def test_ignores_dm(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        msg = make_message(bot.user, VALID_CONTENT, guild_set=False)
        asyncio.run(bot.on_message(msg))
        msg.add_reaction.assert_not_called()

    def test_ignores_message_without_mention(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        msg.mentions = []
        asyncio.run(bot.on_message(msg))
        msg.add_reaction.assert_not_called()


# ── ImageBot: _handle_request ─────────────────────────────────────────────────


class TestImageBotHandleRequest:
    def test_parse_error_sends_error_reaction_and_reply(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        msg = make_message(bot.user, "<@1>")  # positive / negative 欠落
        asyncio.run(bot._handle_request(msg))
        msg.add_reaction.assert_called_with("❌")
        msg.reply.assert_called_once()

    def test_parse_error_does_not_call_execute(self, tmp_path):
        runner = MagicMock()
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, "<@1>")
        asyncio.run(bot._handle_request(msg))
        runner.execute.assert_not_called()

    def test_rate_limited_sends_error_reaction(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._limiter.record_request(99999)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        msg.add_reaction.assert_called_with("❌")
        assert "秒" in msg.reply.call_args.args[0]

    def test_global_lock_sends_generating_message(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._limiter.set_generating(True)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        msg.add_reaction.assert_called_with("❌")
        assert msg.reply.call_args.args[0] == "現在生成中です。しばらくお待ちください。"

    def test_valid_request_calls_execute_with_correct_args(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("generate_image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        runner.execute.assert_called_once_with(
            [], {"positive": "1girl", "negative": "bad quality"}
        )

    def test_valid_request_sends_file_to_channel(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("generate_image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        msg.channel.send.assert_called_once()

    def test_valid_request_adds_success_reaction(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("generate_image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        reactions = [c.args[0] for c in msg.add_reaction.call_args_list]
        assert "✅" in reactions

    def test_valid_request_removes_processing_reaction(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("generate_image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        msg.remove_reaction.assert_called_once_with("⏳", bot.user)

    def test_execution_error_sends_error_reaction_with_message(self, tmp_path):
        runner = MagicMock()
        runner.execute.side_effect = ValueError("接続失敗")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        reactions = [c.args[0] for c in msg.add_reaction.call_args_list]
        assert "❌" in reactions
        assert "接続失敗" in msg.reply.call_args.args[0]

    def test_execution_error_removes_processing_reaction(self, tmp_path):
        runner = MagicMock()
        runner.execute.side_effect = ValueError("error")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        msg.remove_reaction.assert_called_once_with("⏳", bot.user)

    def test_unexpected_error_sends_fixed_message(self, tmp_path):
        runner = MagicMock()
        runner.execute.side_effect = RuntimeError("unexpected")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        assert msg.reply.call_args.args[0] == "予期しないエラーが発生しました"

    def test_generating_lock_released_after_success(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("generate_image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        assert bot._limiter.is_generating() is False

    def test_generating_lock_released_after_error(self, tmp_path):
        runner = MagicMock()
        runner.execute.side_effect = ValueError("error")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        assert bot._limiter.is_generating() is False

    def test_sends_without_reference_when_message_deleted(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        # 参照ありの send で HTTPException、フォールバックの send は成功
        msg.channel.send = AsyncMock(
            side_effect=[discord.HTTPException(MagicMock(), "Unknown Message"), None]
        )
        with patch("generate_image_bot.discord.File") as mock_file:
            asyncio.run(bot._handle_request(msg))
        assert msg.channel.send.call_count == 2
        last_kwargs = msg.channel.send.call_args.kwargs
        assert "reference" not in last_kwargs
        # HTTPException 後にファイルが閉じられるため discord.File が2回生成されること
        assert mock_file.call_count == 2

    def test_success_reaction_skipped_when_message_deleted(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)

        async def add_reaction_side_effect(reaction):
            if reaction == "✅":
                raise discord.HTTPException(MagicMock(), "Unknown Message")

        msg.add_reaction.side_effect = add_reaction_side_effect
        with patch("generate_image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        # 例外が伝播せず、生成ロックが解除されていること
        assert bot._limiter.is_generating() is False


# ── ImageBot: _resolve_output_paths ──────────────────────────────────────────


class TestResolveOutputPaths:
    def _make_bot(self, tmp_path) -> ImageBot:
        return make_bot_for_test(valid_config(), MagicMock(), tmp_path)

    def test_valid_file_returns_path(self, tmp_path):
        bot = self._make_bot(tmp_path)
        (tmp_path / "output.png").write_bytes(b"x")
        paths = bot._resolve_output_paths(
            [{"filename": "output.png", "subfolder": "", "type": "output"}]
        )
        assert len(paths) == 1
        assert paths[0] == (tmp_path / "output.png").resolve()

    def test_path_traversal_raises(self, tmp_path):
        bot = self._make_bot(tmp_path)
        with pytest.raises(ValueError, match="不正"):
            bot._resolve_output_paths(
                [{"filename": "../evil.png", "subfolder": "", "type": "output"}]
            )

    def test_file_not_found_raises(self, tmp_path):
        bot = self._make_bot(tmp_path)
        with pytest.raises(ValueError, match="見つかりません"):
            bot._resolve_output_paths(
                [{"filename": "nonexistent.png", "subfolder": "", "type": "output"}]
            )

    def test_file_too_large_raises(self, tmp_path):
        bot = self._make_bot(tmp_path)
        (tmp_path / "big.png").write_bytes(b"x")
        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_size = 10 * 1024 * 1024
            with pytest.raises(ValueError, match="大きすぎます"):
                bot._resolve_output_paths(
                    [{"filename": "big.png", "subfolder": "", "type": "output"}]
                )

    def test_non_output_type_is_skipped(self, tmp_path):
        bot = self._make_bot(tmp_path)
        (tmp_path / "temp.png").write_bytes(b"x")
        paths = bot._resolve_output_paths(
            [{"filename": "temp.png", "subfolder": "", "type": "temp"}]
        )
        assert paths == []

    def test_mixed_types_only_output_returned(self, tmp_path):
        bot = self._make_bot(tmp_path)
        (tmp_path / "out.png").write_bytes(b"x")
        (tmp_path / "tmp.png").write_bytes(b"x")
        items = [
            {"filename": "tmp.png", "subfolder": "", "type": "temp"},
            {"filename": "out.png", "subfolder": "", "type": "output"},
        ]
        paths = bot._resolve_output_paths(items)
        assert len(paths) == 1
        assert paths[0] == (tmp_path / "out.png").resolve()


# ── write_log ─────────────────────────────────────────────────────────────────

_LOG_PARSED = {"loras": ["lora1"], "positive": "1girl", "negative": "bad quality"}
_LOG_OUTPUTS = [{"filename": "out.png", "subfolder": "", "type": "output"}]


class TestWriteLog:
    def test_creates_log_dir_if_not_exists(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 123, "user1", _LOG_PARSED, "success", [], None)
        assert log_dir.is_dir()

    def test_creates_json_file(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 123, "user1", _LOG_PARSED, "success", [], None)
        files = list(log_dir.glob("result_*.json"))
        assert len(files) == 1

    def test_filename_matches_format(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 123, "user1", _LOG_PARSED, "success", [], None)
        filename = list(log_dir.glob("result_*.json"))[0].name
        assert re.match(r"result_\d{8}_\d{6}\.json", filename)

    def test_success_content(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 123, "user1", _LOG_PARSED, "success", _LOG_OUTPUTS, None)
        data = json.loads(list(log_dir.glob("*.json"))[0].read_text(encoding="utf-8"))
        assert data["status"] == "success"
        assert data["user_id"] == 123
        assert data["username"] == "user1"
        assert data["loras"] == ["lora1"]
        assert data["positive"] == "1girl"
        assert data["negative"] == "bad quality"
        assert data["outputs"] == _LOG_OUTPUTS
        assert data["error"] is None

    def test_error_content(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 456, "user2", _LOG_PARSED, "error", [], "接続失敗")
        data = json.loads(list(log_dir.glob("*.json"))[0].read_text(encoding="utf-8"))
        assert data["status"] == "error"
        assert data["error"] == "接続失敗"

    def test_timestamp_format(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 123, "user1", _LOG_PARSED, "success", [], None)
        data = json.loads(list(log_dir.glob("*.json"))[0].read_text(encoding="utf-8"))
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", data["timestamp"])


# ── ImageBot: ログ統合テスト ────────────────────────────────────────────────────


class TestImageBotLogging:
    def _make_bot_with_log(self, config, runner, output_dir, log_dir) -> ImageBot:
        bot = make_bot_for_test(config, runner, output_dir)
        bot._log_dir = log_dir
        return bot

    def test_success_writes_log(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), runner, tmp_path, log_dir)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("generate_image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        files = list(log_dir.glob("result_*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["status"] == "success"
        assert data["outputs"] == VALID_OUTPUTS
        assert data["error"] is None

    def test_success_log_contains_user_info(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), runner, tmp_path, log_dir)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("generate_image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        data = json.loads(list(log_dir.glob("*.json"))[0].read_text(encoding="utf-8"))
        assert data["user_id"] == 99999
        assert data["username"] == "testuser"

    def test_execution_error_writes_error_log(self, tmp_path):
        runner = MagicMock()
        runner.execute.side_effect = ValueError("接続失敗")
        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), runner, tmp_path, log_dir)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        files = list(log_dir.glob("result_*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["status"] == "error"
        assert "接続失敗" in data["error"]

    def test_unexpected_error_writes_error_log(self, tmp_path):
        runner = MagicMock()
        runner.execute.side_effect = RuntimeError("crash")
        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), runner, tmp_path, log_dir)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        files = list(log_dir.glob("result_*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["status"] == "error"

    def test_parse_error_does_not_write_log(self, tmp_path):
        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), MagicMock(), tmp_path, log_dir)
        msg = make_message(bot.user, "<@1>")  # positive / negative 欠落
        asyncio.run(bot._handle_request(msg))
        assert not log_dir.exists() or len(list(log_dir.glob("*.json"))) == 0

    def test_rate_limit_does_not_write_log(self, tmp_path):
        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), MagicMock(), tmp_path, log_dir)
        bot._limiter.record_request(99999)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        assert not log_dir.exists() or len(list(log_dir.glob("*.json"))) == 0

    def test_global_lock_does_not_write_log(self, tmp_path):
        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), MagicMock(), tmp_path, log_dir)
        bot._limiter.set_generating(True)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        assert not log_dir.exists() or len(list(log_dir.glob("*.json"))) == 0


# ── _parse_shutdown_time ──────────────────────────────────────────────────────


class TestParseShutdownTime:
    def test_valid_midnight(self):
        assert _parse_shutdown_time("00:00") == (0, 0)

    def test_valid_noon(self):
        assert _parse_shutdown_time("12:30") == (12, 30)

    def test_valid_end_of_day(self):
        assert _parse_shutdown_time("23:59") == (23, 59)

    def test_invalid_format_no_colon(self):
        with pytest.raises(ValueError, match="hh:mm"):
            _parse_shutdown_time("0300")

    def test_invalid_format_single_digit(self):
        with pytest.raises(ValueError, match="hh:mm"):
            _parse_shutdown_time("3:00")

    def test_invalid_hour_over_23(self):
        with pytest.raises(ValueError, match="不正"):
            _parse_shutdown_time("24:00")

    def test_invalid_minute_over_59(self):
        with pytest.raises(ValueError, match="不正"):
            _parse_shutdown_time("12:60")

    def test_invalid_non_numeric(self):
        with pytest.raises(ValueError, match="hh:mm"):
            _parse_shutdown_time("ab:cd")


# ── load_config: shutdown_time ────────────────────────────────────────────────


class TestLoadConfigShutdownTime:
    def test_shutdown_time_absent_is_valid(self, tmp_path):
        # shutdown_time がなくても正常に読み込める
        path = write_config(tmp_path / "config.json", valid_config())
        config = load_config(path)
        assert config.get("shutdown_time") is None

    def test_shutdown_time_null_is_valid(self, tmp_path):
        data = {**valid_config(), "shutdown_time": None}
        path = write_config(tmp_path / "config.json", data)
        config = load_config(path)
        assert config["shutdown_time"] is None

    def test_shutdown_time_valid_string(self, tmp_path):
        data = {**valid_config(), "shutdown_time": "03:00"}
        path = write_config(tmp_path / "config.json", data)
        config = load_config(path)
        assert config["shutdown_time"] == "03:00"

    def test_shutdown_time_invalid_format_raises(self, tmp_path):
        data = {**valid_config(), "shutdown_time": "0300"}
        path = write_config(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match="hh:mm"):
            load_config(path)

    def test_shutdown_time_not_string_raises(self, tmp_path):
        data = {**valid_config(), "shutdown_time": 300}
        path = write_config(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match="shutdown_time"):
            load_config(path)


# ── ImageBot: シャットダウン ──────────────────────────────────────────────────


class TestImageBotShutdown:
    def test_shutdown_requested_ignores_new_request(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._shutdown_requested = True
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        msg.add_reaction.assert_not_called()
        msg.reply.assert_not_called()

    def test_watcher_calls_close_when_time_matches(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._shutdown_time = (3, 0)
        bot.is_closed = MagicMock(return_value=False)
        bot.close = AsyncMock()

        with patch("generate_image_bot.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock(hour=3, minute=0)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                asyncio.run(bot._shutdown_watcher())

        bot.close.assert_called_once()

    def test_watcher_sets_shutdown_requested_before_close(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._shutdown_time = (3, 0)
        bot.is_closed = MagicMock(return_value=False)
        bot.close = AsyncMock()

        with patch("generate_image_bot.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock(hour=3, minute=0)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                asyncio.run(bot._shutdown_watcher())

        assert bot._shutdown_requested is True

    def test_watcher_does_not_trigger_when_time_differs(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._shutdown_time = (3, 0)
        bot.is_closed = MagicMock(side_effect=[False, False, True])
        bot.close = AsyncMock()

        with patch("generate_image_bot.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock(hour=2, minute=59)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                asyncio.run(bot._shutdown_watcher())

        bot.close.assert_not_called()

    def test_watcher_waits_for_generation_to_complete(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._shutdown_time = (3, 0)
        bot.is_closed = MagicMock(return_value=False)
        bot.close = AsyncMock()
        bot._limiter.set_generating(True)

        sleep_count = 0

        async def fake_sleep(n):
            nonlocal sleep_count
            sleep_count += 1
            # 2回目の sleep（1秒待ち）で生成完了とみなす
            if sleep_count >= 2:
                bot._limiter.set_generating(False)

        with patch("generate_image_bot.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock(hour=3, minute=0)
            with patch("asyncio.sleep", side_effect=fake_sleep):
                asyncio.run(bot._shutdown_watcher())

        bot.close.assert_called_once()

    def test_watcher_does_not_trigger_twice_in_same_minute(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._shutdown_time = (3, 0)
        # is_closed: 1回目 False（ループ継続）、2回目 False（ループ継続）、3回目 True（終了）
        # triggered_minute に記録されるため2回目はトリガーしない
        bot.is_closed = MagicMock(side_effect=[False, False, True])
        bot.close = AsyncMock()

        with patch("generate_image_bot.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock(hour=3, minute=0)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                asyncio.run(bot._shutdown_watcher())

        # 最初のトリガーで close() が呼ばれ return するため 1 回のみ
        bot.close.assert_called_once()


# ── GenImageModal ─────────────────────────────────────────────────────────────


class TestGenImageModal:
    def _make_test_modal(
        self,
        tmp_path,
        loras_val: str = "",
        positive_val: str = "1girl",
        negative_val: str = "bad quality",
    ):
        """discord.ui.Modal.__init__ を回避し、TextInput を MagicMock で差し替えたモーダルを返す。"""
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        modal = object.__new__(GenImageModal)
        modal._bot = bot
        modal.loras = MagicMock(value=loras_val)
        modal.positive = MagicMock(value=positive_val)
        modal.negative = MagicMock(value=negative_val)
        return modal, bot

    def _make_interaction(self, user_id: int = 99999, username: str = "testuser"):
        interaction = MagicMock()
        interaction.user = MagicMock(id=user_id)
        interaction.user.name = (
            username  # MagicMock の name 引数はモック名に使われるため別途設定する
        )
        interaction.response.send_message = AsyncMock()
        mock_message = MagicMock()
        mock_message.add_reaction = AsyncMock()
        mock_message.remove_reaction = AsyncMock()
        mock_message.reply = AsyncMock()
        mock_message.channel = MagicMock()
        mock_message.channel.send = AsyncMock()
        interaction.original_response = AsyncMock(return_value=mock_message)
        return interaction, mock_message

    def test_build_parsed_with_loras(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path, loras_val="lora1, lora2")
        parsed = modal._build_parsed()
        assert parsed["loras"] == ["lora1", "lora2"]
        assert parsed["positive"] == "1girl"
        assert parsed["negative"] == "bad quality"

    def test_build_parsed_no_loras_returns_empty_list(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path, loras_val="")
        parsed = modal._build_parsed()
        assert parsed["loras"] == []

    def test_build_parsed_loras_strips_whitespace(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path, loras_val="  lora1 ,  lora2  ")
        parsed = modal._build_parsed()
        assert parsed["loras"] == ["lora1", "lora2"]

    def test_build_parsed_loras_ignores_empty_items(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path, loras_val=" , , ")
        parsed = modal._build_parsed()
        assert parsed["loras"] == []

    def test_build_message_text_with_loras(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path)
        parsed = {"loras": ["lora1", "lora2"], "positive": "1girl", "negative": "bad"}
        text = modal._build_message_text(parsed)
        assert text == "loras: lora1, lora2\npositive: 1girl\nnegative: bad"

    def test_build_message_text_without_loras(self, tmp_path):
        modal, _ = self._make_test_modal(tmp_path)
        parsed = {"loras": [], "positive": "1girl", "negative": "bad"}
        text = modal._build_message_text(parsed)
        assert "loras:" not in text
        assert text == "positive: 1girl\nnegative: bad"

    def test_on_submit_sends_keyword_format_message(self, tmp_path):
        modal, bot = self._make_test_modal(
            tmp_path, loras_val="my_lora", positive_val="1girl", negative_val="bad"
        )
        interaction, _ = self._make_interaction()
        bot._process_generation = AsyncMock()
        asyncio.run(modal.on_submit(interaction))
        sent = interaction.response.send_message.call_args.args[0]
        assert "loras: my_lora" in sent
        assert "positive: 1girl" in sent
        assert "negative: bad" in sent

    def test_on_submit_no_loras_omits_loras_line(self, tmp_path):
        modal, bot = self._make_test_modal(tmp_path, loras_val="")
        interaction, _ = self._make_interaction()
        bot._process_generation = AsyncMock()
        asyncio.run(modal.on_submit(interaction))
        sent = interaction.response.send_message.call_args.args[0]
        assert "loras:" not in sent

    def test_on_submit_calls_process_generation_with_parsed(self, tmp_path):
        modal, bot = self._make_test_modal(
            tmp_path,
            loras_val="lora1",
            positive_val="masterpiece",
            negative_val="worst",
        )
        interaction, mock_message = self._make_interaction()
        mock_process = AsyncMock()
        bot._process_generation = mock_process
        asyncio.run(modal.on_submit(interaction))
        mock_process.assert_called_once()
        msg_arg, parsed_arg, user_arg = mock_process.call_args.args
        assert msg_arg is mock_message
        assert parsed_arg["loras"] == ["lora1"]
        assert parsed_arg["positive"] == "masterpiece"
        assert parsed_arg["negative"] == "worst"

    def test_on_submit_passes_interaction_user(self, tmp_path):
        modal, bot = self._make_test_modal(tmp_path)
        interaction, _ = self._make_interaction(user_id=12345, username="modaluser")
        mock_process = AsyncMock()
        bot._process_generation = mock_process
        asyncio.run(modal.on_submit(interaction))
        _, _, user_arg = mock_process.call_args.args
        assert user_arg.id == 12345
        assert user_arg.name == "modaluser"


# ── ImageBot: スラッシュコマンド ──────────────────────────────────────────────


class TestImageBotSlashCommand:
    def _make_interaction(self, guild_set: bool = True):
        interaction = MagicMock()
        interaction.guild = MagicMock() if guild_set else None
        interaction.response.send_message = AsyncMock()
        interaction.response.send_modal = AsyncMock()
        return interaction

    def test_dm_sends_ephemeral_dm_not_supported_message(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        interaction = self._make_interaction(guild_set=False)
        asyncio.run(bot._gen_image_command(interaction))
        interaction.response.send_message.assert_called_once_with(
            "DM からは使用できません。", ephemeral=True
        )

    def test_dm_does_not_send_modal(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        interaction = self._make_interaction(guild_set=False)
        asyncio.run(bot._gen_image_command(interaction))
        interaction.response.send_modal.assert_not_called()

    def test_shutdown_sends_ephemeral_shutdown_message(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._shutdown_requested = True
        interaction = self._make_interaction(guild_set=True)
        asyncio.run(bot._gen_image_command(interaction))
        interaction.response.send_message.assert_called_once_with(
            "シャットダウン中です。", ephemeral=True
        )

    def test_shutdown_does_not_send_modal(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._shutdown_requested = True
        interaction = self._make_interaction(guild_set=True)
        asyncio.run(bot._gen_image_command(interaction))
        interaction.response.send_modal.assert_not_called()

    def test_normal_sends_gen_image_modal(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        interaction = self._make_interaction(guild_set=True)
        with patch("generate_image_bot.GenImageModal") as mock_modal_cls:
            asyncio.run(bot._gen_image_command(interaction))
        mock_modal_cls.assert_called_once_with(bot)
        interaction.response.send_modal.assert_called_once_with(
            mock_modal_cls.return_value
        )

    def test_normal_does_not_send_message(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        interaction = self._make_interaction(guild_set=True)
        with patch("generate_image_bot.GenImageModal"):
            asyncio.run(bot._gen_image_command(interaction))
        interaction.response.send_message.assert_not_called()
