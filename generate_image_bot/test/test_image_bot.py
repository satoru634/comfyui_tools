"""image_bot.py のユニットテスト"""

import asyncio
import contextlib
import io
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from PIL import Image as PILImage

from modules.image_bot import ImageBot
from modules.common_lib import write_system_log, write_discord_log

from test_helper import (
    valid_config,
    make_bot_for_test,
    make_message,
    VALID_CONTENT,
    VALID_OUTPUTS,
)

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

    def test_rate_limit_skipped_when_user_has_active_requests(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        # レート制限中でも処理中リクエストがあれば通過する
        bot._limiter.record_request(99999)
        bot._limiter.increment_active(99999)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        runner.execute.assert_called_once()

    def test_concurrent_limit_sends_error_message(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        from modules.rate_limiter import RateLimiter

        for _ in range(RateLimiter.MAX_CONCURRENT):
            bot._limiter.increment_active(99999)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        msg.add_reaction.assert_called_with("❌")
        assert (
            msg.reply.call_args.args[0]
            == "リクエストが上限に達しています。しばらくお待ちください。"
        )

    def test_other_user_active_does_not_block_request(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        # 別ユーザー（ID=11111）が上限いっぱいまで生成中でも、このユーザー（ID=99999）は通る
        from modules.rate_limiter import RateLimiter

        for _ in range(RateLimiter.MAX_CONCURRENT):
            bot._limiter.increment_active(11111)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        runner.execute.assert_called_once()

    def test_valid_request_calls_execute_with_correct_args(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        runner.execute.assert_called_once_with(
            [], {"positive": "1girl", "negative": "bad quality"}, None
        )

    def test_valid_request_sends_file_to_channel(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        msg.channel.send.assert_called_once()

    def test_valid_request_adds_success_reaction(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        reactions = [c.args[0] for c in msg.add_reaction.call_args_list]
        assert "✅" in reactions

    def test_valid_request_removes_processing_reaction(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("modules.image_bot.discord.File"):
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

    def test_active_count_decremented_after_success(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        assert bot._limiter.has_active() is False

    def test_active_count_decremented_after_error(self, tmp_path):
        runner = MagicMock()
        runner.execute.side_effect = ValueError("error")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        assert bot._limiter.has_active() is False

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
        with patch("modules.image_bot.discord.File") as mock_file:
            asyncio.run(bot._handle_request(msg))
        assert msg.channel.send.call_count == 2
        last_kwargs = msg.channel.send.call_args.kwargs
        assert "reference" not in last_kwargs
        # HTTPException 後にファイルが閉じられるため discord.File が2回生成されること
        assert mock_file.call_count == 2

    def test_image_orientation_vertical_passes_correct_image_size(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        runner.get_image_size.return_value = {"width": 832, "height": 1216}
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        content = (
            "<@1>\npositive: 1girl\nnegative: bad quality\nimage_orientation: vertical"
        )
        msg = make_message(bot.user, content)
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        runner.get_image_size.assert_called_once_with("vertical")
        runner.execute.assert_called_once_with(
            [],
            {"positive": "1girl", "negative": "bad quality"},
            {"width": 832, "height": 1216},
        )

    def test_image_orientation_horizontal_passes_correct_image_size(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        runner.get_image_size.return_value = {"width": 1216, "height": 832}
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        content = "<@1>\npositive: 1girl\nnegative: bad quality\nimage_orientation: horizontal"
        msg = make_message(bot.user, content)
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        runner.get_image_size.assert_called_once_with("horizontal")
        runner.execute.assert_called_once_with(
            [],
            {"positive": "1girl", "negative": "bad quality"},
            {"width": 1216, "height": 832},
        )

    def test_image_orientation_square_passes_correct_image_size(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        runner.get_image_size.return_value = {"width": 1024, "height": 1024}
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        content = (
            "<@1>\npositive: 1girl\nnegative: bad quality\nimage_orientation: square"
        )
        msg = make_message(bot.user, content)
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        runner.get_image_size.assert_called_once_with("square")
        runner.execute.assert_called_once_with(
            [],
            {"positive": "1girl", "negative": "bad quality"},
            {"width": 1024, "height": 1024},
        )

    def test_image_orientation_invalid_sends_error(self, tmp_path):
        runner = MagicMock()
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        content = (
            "<@1>\npositive: 1girl\nnegative: bad quality\nimage_orientation: diagonal"
        )
        msg = make_message(bot.user, content)
        asyncio.run(bot._handle_request(msg))
        msg.add_reaction.assert_called_with("❌")
        runner.execute.assert_not_called()

    def test_no_image_orientation_passes_none_as_image_size(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        runner.get_image_size.assert_not_called()
        runner.execute.assert_called_once_with(
            [], {"positive": "1girl", "negative": "bad quality"}, None
        )

    def test_unknown_workflow_sends_error(self, tmp_path):
        bot = make_bot_for_test(valid_config(), None, tmp_path)
        content = "<@1>\nworkflow: nonexistent\npositive: 1girl\nnegative: bad"
        msg = make_message(bot.user, content)
        with patch(
            "modules.image_bot.WorkflowRunner", side_effect=ValueError("存在しません")
        ):
            asyncio.run(bot._handle_request(msg))
        msg.add_reaction.assert_called_with("❌")
        assert "nonexistent" in msg.reply.call_args.args[0]

    def test_unknown_workflow_does_not_call_execute(self, tmp_path):
        bot = make_bot_for_test(valid_config(), None, tmp_path)
        content = "<@1>\nworkflow: bad\npositive: 1girl\nnegative: bad"
        msg = make_message(bot.user, content)
        with patch(
            "modules.image_bot.WorkflowRunner", side_effect=ValueError("存在しません")
        ):
            asyncio.run(bot._handle_request(msg))

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
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        # 例外が伝播せず、カウンタがデクリメントされていること
        assert bot._limiter.has_active() is False


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
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        files = list(log_dir.glob("*/result_*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["status"] == "success"
        assert data["outputs"] == VALID_OUTPUTS
        assert data["error"] is None

    def test_success_log_contains_image_orientation(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), runner, tmp_path, log_dir)
        content = (
            "<@1>\npositive: 1girl\nnegative: bad quality\nimage_orientation: vertical"
        )
        msg = make_message(bot.user, content)
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        data = json.loads(list(log_dir.glob("*/*.json"))[0].read_text(encoding="utf-8"))
        assert data["image_orientation"] == "vertical"

    def test_success_log_image_orientation_null_when_omitted(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), runner, tmp_path, log_dir)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        data = json.loads(list(log_dir.glob("*/*.json"))[0].read_text(encoding="utf-8"))
        assert data["image_orientation"] is None

    def test_success_log_contains_user_info(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), runner, tmp_path, log_dir)
        msg = make_message(bot.user, VALID_CONTENT)
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot._handle_request(msg))
        data = json.loads(list(log_dir.glob("*/*.json"))[0].read_text(encoding="utf-8"))
        assert data["user_id"] == 99999
        assert data["username"] == "testuser"

    def test_execution_error_writes_error_log(self, tmp_path):
        runner = MagicMock()
        runner.execute.side_effect = ValueError("接続失敗")
        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), runner, tmp_path, log_dir)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        files = list(log_dir.glob("*/result_*.json"))
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
        files = list(log_dir.glob("*/result_*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["status"] == "error"

    def test_parse_error_does_not_write_log(self, tmp_path):
        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), MagicMock(), tmp_path, log_dir)
        msg = make_message(bot.user, "<@1>")  # positive / negative 欠落
        asyncio.run(bot._handle_request(msg))
        assert not log_dir.exists() or len(list(log_dir.glob("*/*.json"))) == 0

    def test_rate_limit_does_not_write_log(self, tmp_path):
        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), MagicMock(), tmp_path, log_dir)
        bot._limiter.record_request(99999)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        assert not log_dir.exists() or len(list(log_dir.glob("*/*.json"))) == 0

    def test_concurrent_limit_does_not_write_log(self, tmp_path):
        from modules.rate_limiter import RateLimiter

        log_dir = tmp_path / "log"
        bot = self._make_bot_with_log(valid_config(), MagicMock(), tmp_path, log_dir)
        for _ in range(RateLimiter.MAX_CONCURRENT):
            bot._limiter.increment_active(99999)
        msg = make_message(bot.user, VALID_CONTENT)
        asyncio.run(bot._handle_request(msg))
        assert not log_dir.exists() or len(list(log_dir.glob("*/*.json"))) == 0


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

        with patch("modules.image_bot.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock(hour=3, minute=0)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                asyncio.run(bot._shutdown_watcher())

        bot.close.assert_called_once()

    def test_watcher_sets_shutdown_requested_before_close(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._shutdown_time = (3, 0)
        bot.is_closed = MagicMock(return_value=False)
        bot.close = AsyncMock()

        with patch("modules.image_bot.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock(hour=3, minute=0)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                asyncio.run(bot._shutdown_watcher())

        assert bot._shutdown_requested is True

    def test_watcher_does_not_trigger_when_time_differs(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._shutdown_time = (3, 0)
        bot.is_closed = MagicMock(side_effect=[False, False, True])
        bot.close = AsyncMock()

        with patch("modules.image_bot.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock(hour=2, minute=59)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                asyncio.run(bot._shutdown_watcher())

        bot.close.assert_not_called()

    def test_watcher_waits_for_generation_to_complete(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._shutdown_time = (3, 0)
        bot.is_closed = MagicMock(return_value=False)
        bot.close = AsyncMock()
        bot._limiter.increment_active(1)

        sleep_count = 0

        async def fake_sleep(n):
            nonlocal sleep_count
            sleep_count += 1
            # 2回目の sleep（1秒待ち）で生成完了とみなす
            if sleep_count >= 2:
                bot._limiter.decrement_active(1)

        with patch("modules.image_bot.datetime") as mock_dt:
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

        with patch("modules.image_bot.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock(hour=3, minute=0)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                asyncio.run(bot._shutdown_watcher())

        # 最初のトリガーで close() が呼ばれ return するため 1 回のみ
        bot.close.assert_called_once()


# ── ImageBot: スラッシュコマンド ──────────────────────────────────────────────


class TestImageBotSlashCommand:
    def _make_interaction(self, guild_set: bool = True):
        interaction = MagicMock()
        if guild_set:
            interaction.guild = MagicMock()
            interaction.guild.id = 222
        else:
            interaction.guild = None
        interaction.user = MagicMock()
        interaction.user.id = 12345
        interaction.user.name = "test_slash_user"
        interaction.channel_id = 111
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
        with patch("modules.image_bot.GenImageModal") as mock_modal_cls:
            asyncio.run(bot._gen_image_command(interaction))
        mock_modal_cls.assert_called_once_with(bot)
        interaction.response.send_modal.assert_called_once_with(
            mock_modal_cls.return_value
        )

    def test_normal_does_not_send_message(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        interaction = self._make_interaction(guild_set=True)
        with patch("modules.image_bot.GenImageModal"):
            asyncio.run(bot._gen_image_command(interaction))
        interaction.response.send_message.assert_not_called()


# ── ImageBot: Discord ログ ────────────────────────────────────────────────────


class TestImageBotDiscordLogging:
    def test_on_ready_writes_discord_ready_log(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._log_dir = tmp_path / "log"
        asyncio.run(bot.on_ready())
        files = list(bot._log_dir.glob("*/discord_*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["type"] == "discord_ready"
        assert "bot_user_id" in data
        assert "bot_username" in data

    def test_on_message_writes_discord_message_log(self, tmp_path):
        runner = MagicMock()
        runner.execute.return_value = VALID_OUTPUTS
        (tmp_path / "output.png").write_bytes(b"x")
        bot = make_bot_for_test(valid_config(), runner, tmp_path)
        bot._log_dir = tmp_path / "log"
        msg = make_message(bot.user, VALID_CONTENT)
        msg.channel.id = 111
        msg.guild.id = 222
        with patch("modules.image_bot.discord.File"):
            asyncio.run(bot.on_message(msg))
        files = list(bot._log_dir.glob("*/discord_*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["type"] == "discord_message"
        assert data["user_id"] == 99999
        assert data["username"] == "testuser"
        assert data["channel_id"] == 111
        assert data["guild_id"] == 222

    def test_on_message_own_message_does_not_write_log(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._log_dir = tmp_path / "log"
        msg = make_message(bot.user, VALID_CONTENT, is_own=True)
        asyncio.run(bot.on_message(msg))
        assert (
            not bot._log_dir.exists()
            or len(list(bot._log_dir.glob("*/discord_*.json"))) == 0
        )

    def test_on_message_dm_does_not_write_log(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._log_dir = tmp_path / "log"
        msg = make_message(bot.user, VALID_CONTENT, guild_set=False)
        asyncio.run(bot.on_message(msg))
        assert (
            not bot._log_dir.exists()
            or len(list(bot._log_dir.glob("*/discord_*.json"))) == 0
        )

    def test_gen_image_command_writes_discord_slash_command_log(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._log_dir = tmp_path / "log"
        interaction = MagicMock()
        interaction.guild = MagicMock()
        interaction.guild.id = 222
        interaction.user = MagicMock()
        interaction.user.id = 777
        interaction.user.name = "slash_user"
        interaction.channel_id = 333
        interaction.response.send_message = AsyncMock()
        interaction.response.send_modal = AsyncMock()
        with patch("modules.image_bot.GenImageModal"):
            asyncio.run(bot._gen_image_command(interaction))
        files = list(bot._log_dir.glob("*/discord_*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["type"] == "discord_slash_command"
        assert data["user_id"] == 777
        assert data["username"] == "slash_user"
        assert data["channel_id"] == 333
        assert data["guild_id"] == 222

    def test_gen_image_command_dm_does_not_write_log(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._log_dir = tmp_path / "log"
        interaction = MagicMock()
        interaction.guild = None
        interaction.response.send_message = AsyncMock()
        asyncio.run(bot._gen_image_command(interaction))
        assert (
            not bot._log_dir.exists()
            or len(list(bot._log_dir.glob("*/discord_*.json"))) == 0
        )


# ── ImageBot: _shutdown_reason ────────────────────────────────────────────────


class TestImageBotShutdownReason:
    def test_default_shutdown_reason_is_signal(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        assert bot._shutdown_reason == "signal"

    def test_shutdown_watcher_sets_scheduled_reason(self, tmp_path):
        bot = make_bot_for_test(valid_config(), MagicMock(), tmp_path)
        bot._shutdown_time = (3, 0)
        bot.is_closed = MagicMock(return_value=False)
        bot.close = AsyncMock()

        with patch("modules.image_bot.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock(hour=3, minute=0)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                asyncio.run(bot._shutdown_watcher())

        assert bot._shutdown_reason == "scheduled"


# ── ImageBot: /tag_image コマンド ─────────────────────────────────────────────


def _make_valid_png_bytes(width: int = 100, height: int = 100) -> bytes:
    """テスト用の有効な PNG バイト列を生成する。"""
    img = PILImage.new("RGB", (width, height))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestTagImageCommand:
    def _make_interaction(self, guild_set=True, content_type="image/png", size=100):
        interaction = MagicMock()
        if guild_set:
            interaction.guild = MagicMock()
            interaction.guild.id = 222
        else:
            interaction.guild = None
        interaction.user = MagicMock()
        interaction.user.id = 99999
        interaction.user.name = "testuser"
        interaction.channel_id = 111
        interaction.response.send_message = AsyncMock()
        mock_message = MagicMock()
        mock_message.add_reaction = AsyncMock()
        mock_message.remove_reaction = AsyncMock()
        mock_message.reply = AsyncMock()
        interaction.original_response = AsyncMock(return_value=mock_message)
        attachment = MagicMock()
        attachment.content_type = content_type
        attachment.size = size
        attachment.filename = "photo.jpg"
        attachment.read = AsyncMock(return_value=_make_valid_png_bytes())
        return interaction, mock_message, attachment

    def _make_bot(self, tmp_path, wd14_runner=None):
        return make_bot_for_test(valid_config(), MagicMock(), tmp_path, wd14_runner)

    def _run_command(self, bot, interaction, attachment, *extra_cms):
        """_validate_image_data と _make_safe_filename をモックして _tag_image_command を実行する。"""
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("modules.image_bot._validate_image_data", return_value="PNG")
            )
            stack.enter_context(
                patch("modules.image_bot._make_safe_filename", return_value="safe.png")
            )
            for cm in extra_cms:
                stack.enter_context(cm)
            asyncio.run(bot._tag_image_command(interaction, attachment))

    def test_dm_sends_ephemeral_error(self, tmp_path):
        bot = self._make_bot(tmp_path)
        interaction, _, attachment = self._make_interaction(guild_set=False)
        asyncio.run(bot._tag_image_command(interaction, attachment))
        interaction.response.send_message.assert_called_once_with(
            "DM からは使用できません。", ephemeral=True
        )

    def test_dm_does_not_call_tag(self, tmp_path):
        wd14 = MagicMock()
        bot = self._make_bot(tmp_path, wd14)
        interaction, _, attachment = self._make_interaction(guild_set=False)
        asyncio.run(bot._tag_image_command(interaction, attachment))
        wd14.tag.assert_not_called()

    def test_shutdown_sends_ephemeral_error(self, tmp_path):
        bot = self._make_bot(tmp_path)
        bot._shutdown_requested = True
        interaction, _, attachment = self._make_interaction()
        asyncio.run(bot._tag_image_command(interaction, attachment))
        interaction.response.send_message.assert_called_once_with(
            "シャットダウン中です。", ephemeral=True
        )

    def test_invalid_mime_sends_ephemeral_error(self, tmp_path):
        bot = self._make_bot(tmp_path)
        interaction, _, attachment = self._make_interaction(content_type="text/plain")
        asyncio.run(bot._tag_image_command(interaction, attachment))
        interaction.response.send_message.assert_called_once_with(
            "画像ファイルのみ対応しています。", ephemeral=True
        )

    def test_none_mime_sends_ephemeral_error(self, tmp_path):
        bot = self._make_bot(tmp_path)
        interaction, _, attachment = self._make_interaction(content_type=None)
        asyncio.run(bot._tag_image_command(interaction, attachment))
        interaction.response.send_message.assert_called_once_with(
            "画像ファイルのみ対応しています。", ephemeral=True
        )

    def test_file_too_large_sends_ephemeral_error(self, tmp_path):
        bot = self._make_bot(tmp_path)
        interaction, _, attachment = self._make_interaction(size=10 * 1024 * 1024)
        asyncio.run(bot._tag_image_command(interaction, attachment))
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert call_kwargs["ephemeral"] is True
        assert "大きすぎます" in interaction.response.send_message.call_args.args[0]

    def test_invalid_format_sends_ephemeral_error(self, tmp_path):
        bot = self._make_bot(tmp_path)
        interaction, _, attachment = self._make_interaction()
        attachment.read = AsyncMock(return_value=b"not_an_image")
        asyncio.run(bot._tag_image_command(interaction, attachment))
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert call_kwargs["ephemeral"] is True
        assert "不正" in interaction.response.send_message.call_args.args[0]

    def test_resolution_too_large_sends_ephemeral_error(self, tmp_path):
        bot = self._make_bot(tmp_path)
        interaction, _, attachment = self._make_interaction()
        attachment.read = AsyncMock(
            return_value=_make_valid_png_bytes(width=4097, height=100)
        )
        asyncio.run(bot._tag_image_command(interaction, attachment))
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert call_kwargs["ephemeral"] is True
        assert "解像度" in interaction.response.send_message.call_args.args[0]

    def test_rate_limit_sends_error_reaction(self, tmp_path):
        bot = self._make_bot(tmp_path)
        bot._limiter.record_request(99999)
        interaction, mock_message, attachment = self._make_interaction()
        self._run_command(bot, interaction, attachment)
        mock_message.add_reaction.assert_called_once_with("❌")

    def test_rate_limit_message_contains_seconds(self, tmp_path):
        bot = self._make_bot(tmp_path)
        bot._limiter.record_request(99999)
        interaction, _, attachment = self._make_interaction()
        self._run_command(bot, interaction, attachment)
        assert "秒" in interaction.response.send_message.call_args.args[0]

    def test_concurrent_limit_sends_error_reaction(self, tmp_path):
        from modules.rate_limiter import RateLimiter

        bot = self._make_bot(tmp_path)
        for _ in range(RateLimiter.MAX_CONCURRENT):
            bot._limiter.increment_active(99999)
        interaction, mock_message, attachment = self._make_interaction()
        self._run_command(bot, interaction, attachment)
        mock_message.add_reaction.assert_called_once_with("❌")

    def test_success_replies_with_tags_and_image(self, tmp_path):
        wd14 = MagicMock()
        wd14.tag.return_value = "1girl, solo"
        bot = self._make_bot(tmp_path, wd14)
        interaction, mock_message, attachment = self._make_interaction()
        mock_file_cm = patch("modules.image_bot.discord.File")
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("modules.image_bot._validate_image_data", return_value="PNG")
            )
            stack.enter_context(
                patch("modules.image_bot._make_safe_filename", return_value="safe.png")
            )
            mock_file = stack.enter_context(mock_file_cm)
            asyncio.run(bot._tag_image_command(interaction, attachment))
        mock_message.reply.assert_called_once_with(
            "1girl, solo", file=mock_file.return_value
        )

    def test_success_uses_safe_filename_for_discord_file(self, tmp_path):
        wd14 = MagicMock()
        wd14.tag.return_value = "1girl"
        bot = self._make_bot(tmp_path, wd14)
        interaction, _, attachment = self._make_interaction()
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch("modules.image_bot._validate_image_data", return_value="PNG")
            )
            stack.enter_context(
                patch("modules.image_bot._make_safe_filename", return_value="safe.png")
            )
            mock_file = stack.enter_context(patch("modules.image_bot.discord.File"))
            asyncio.run(bot._tag_image_command(interaction, attachment))
        _, file_kwargs = mock_file.call_args
        assert (
            file_kwargs.get("filename") == "safe.png"
            or mock_file.call_args.args[1] == "safe.png"
        )

    def test_success_adds_success_reaction(self, tmp_path):
        wd14 = MagicMock()
        wd14.tag.return_value = "1girl"
        bot = self._make_bot(tmp_path, wd14)
        interaction, mock_message, attachment = self._make_interaction()
        self._run_command(bot, interaction, attachment)
        reactions = [c.args[0] for c in mock_message.add_reaction.call_args_list]
        assert "✅" in reactions

    def test_success_removes_processing_reaction(self, tmp_path):
        wd14 = MagicMock()
        wd14.tag.return_value = "1girl"
        bot = self._make_bot(tmp_path, wd14)
        interaction, mock_message, attachment = self._make_interaction()
        self._run_command(bot, interaction, attachment)
        mock_message.remove_reaction.assert_called_once_with("⏳", bot.user)

    def test_value_error_sends_error_reaction_with_message(self, tmp_path):
        wd14 = MagicMock()
        wd14.tag.side_effect = ValueError("接続失敗")
        bot = self._make_bot(tmp_path, wd14)
        interaction, mock_message, attachment = self._make_interaction()
        self._run_command(bot, interaction, attachment)
        reactions = [c.args[0] for c in mock_message.add_reaction.call_args_list]
        assert "❌" in reactions
        assert "接続失敗" in mock_message.reply.call_args.args[0]

    def test_unexpected_error_sends_fixed_message(self, tmp_path):
        wd14 = MagicMock()
        wd14.tag.side_effect = RuntimeError("crash")
        bot = self._make_bot(tmp_path, wd14)
        interaction, mock_message, attachment = self._make_interaction()
        self._run_command(bot, interaction, attachment)
        assert mock_message.reply.call_args.args[0] == "予期しないエラーが発生しました"

    def test_active_count_decremented_after_success(self, tmp_path):
        wd14 = MagicMock()
        wd14.tag.return_value = "1girl"
        bot = self._make_bot(tmp_path, wd14)
        interaction, _, attachment = self._make_interaction()
        self._run_command(bot, interaction, attachment)
        assert bot._limiter.has_active() is False

    def test_active_count_decremented_after_error(self, tmp_path):
        wd14 = MagicMock()
        wd14.tag.side_effect = ValueError("error")
        bot = self._make_bot(tmp_path, wd14)
        interaction, _, attachment = self._make_interaction()
        self._run_command(bot, interaction, attachment)
        assert bot._limiter.has_active() is False

    def test_passes_image_bytes_and_safe_filename_to_tag(self, tmp_path):
        wd14 = MagicMock()
        wd14.tag.return_value = "1girl"
        bot = self._make_bot(tmp_path, wd14)
        interaction, _, attachment = self._make_interaction()
        self._run_command(bot, interaction, attachment)
        call_args = wd14.tag.call_args
        assert call_args.args[1] == "safe.png"


# ── ImageBot: workflow_names ──────────────────────────────────────────────────


class TestImageBotWorkflowNames:
    def test_workflow_names_returns_list_from_config(self, tmp_path):
        wf_config = {
            "comfyui_url": "http://localhost:8188",
            "default_workflow": "sdxl",
            "workflows": {"sdxl": {}, "anima": {}, "anima_rapid": {}},
        }
        wf_config_path = tmp_path / "run_workflow_config.json"
        wf_config_path.write_text(json.dumps(wf_config), encoding="utf-8")
        config = valid_config()
        config["run_workflow_config"] = str(wf_config_path)
        bot = make_bot_for_test(config, MagicMock(), tmp_path)
        assert bot.workflow_names == ["sdxl", "anima", "anima_rapid"]

    def test_workflow_names_returns_empty_list_when_config_not_found(self, tmp_path):
        config = valid_config()
        config["run_workflow_config"] = str(tmp_path / "nonexistent.json")
        bot = make_bot_for_test(config, MagicMock(), tmp_path)
        assert bot.workflow_names == []


# ── _validate_image_data / _make_safe_filename ────────────────────────────────


class TestValidateImageData:
    def test_valid_png_returns_format(self):
        from modules.image_bot import _validate_image_data

        result = _validate_image_data(_make_valid_png_bytes())
        assert result == "PNG"

    def test_invalid_bytes_raises(self):
        from modules.image_bot import _validate_image_data

        with pytest.raises(ValueError, match="tag_image_invalid_format"):
            _validate_image_data(b"not an image")

    def test_oversized_width_raises(self):
        from modules.image_bot import _validate_image_data

        with pytest.raises(ValueError, match="tag_image_resolution_too_large"):
            _validate_image_data(_make_valid_png_bytes(width=4097, height=100))

    def test_oversized_height_raises(self):
        from modules.image_bot import _validate_image_data

        with pytest.raises(ValueError, match="tag_image_resolution_too_large"):
            _validate_image_data(_make_valid_png_bytes(width=100, height=4097))

    def test_exactly_max_resolution_is_allowed(self):
        from modules.image_bot import _validate_image_data

        result = _validate_image_data(_make_valid_png_bytes(width=4096, height=4096))
        assert result == "PNG"


class TestMakeSafeFilename:
    def test_returns_jpg_for_jpeg(self):
        from modules.image_bot import _make_safe_filename

        assert _make_safe_filename("JPEG").endswith(".jpg")

    def test_returns_png_for_png(self):
        from modules.image_bot import _make_safe_filename

        assert _make_safe_filename("PNG").endswith(".png")

    def test_filenames_differ_between_calls(self):
        from modules.image_bot import _make_safe_filename

        assert _make_safe_filename("PNG") != _make_safe_filename("PNG")
