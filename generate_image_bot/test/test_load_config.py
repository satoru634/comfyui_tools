"""load_config.py のテスト"""

import pytest

from modules.load_config import load_config, parse_shutdown_time

from test_helper import (
    valid_config,
    write_config,
)

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
            "concurrent_limit",
            "parse_error",
            "execution_error",
            "file_too_large",
            "unexpected_error",
            "dm_not_supported",
            "shutdown_in_progress",
            "tag_image_invalid_type",
            "tag_image_error",
            "tag_image_invalid_format",
            "tag_image_resolution_too_large",
            "invalid_workflow",
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
            "concurrent_limit",
            "parse_error",
            "execution_error",
            "file_too_large",
            "unexpected_error",
            "dm_not_supported",
            "shutdown_in_progress",
            "tag_image_invalid_type",
            "tag_image_error",
            "tag_image_invalid_format",
            "tag_image_resolution_too_large",
            "invalid_workflow",
        ],
    )
    def test_message_value_not_string(self, tmp_path, key):
        data = valid_config()
        data["messages"][key] = 123
        path = write_config(tmp_path / "config.json", data)
        with pytest.raises(ValueError, match=f"messages.{key}"):
            load_config(path)


# ── _parse_shutdown_time ──────────────────────────────────────────────────────


class TestParseShutdownTime:
    def test_valid_midnight(self):
        assert parse_shutdown_time("00:00") == (0, 0)

    def test_valid_noon(self):
        assert parse_shutdown_time("12:30") == (12, 30)

    def test_valid_end_of_day(self):
        assert parse_shutdown_time("23:59") == (23, 59)

    def test_invalid_format_no_colon(self):
        with pytest.raises(ValueError, match="hh:mm"):
            parse_shutdown_time("0300")

    def test_invalid_format_single_digit(self):
        with pytest.raises(ValueError, match="hh:mm"):
            parse_shutdown_time("3:00")

    def test_invalid_hour_over_23(self):
        with pytest.raises(ValueError, match="不正"):
            parse_shutdown_time("24:00")

    def test_invalid_minute_over_59(self):
        with pytest.raises(ValueError, match="不正"):
            parse_shutdown_time("12:60")

    def test_invalid_non_numeric(self):
        with pytest.raises(ValueError, match="hh:mm"):
            parse_shutdown_time("ab:cd")


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
