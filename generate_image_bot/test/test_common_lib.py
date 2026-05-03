"""common_lib.py のテスト"""

import json
import re

from modules.common_lib import write_log, write_system_log, write_discord_log

# ── write_log ─────────────────────────────────────────────────────────────────

_LOG_PARSED = {"loras": ["lora1"], "positive": "1girl", "negative": "bad quality"}
_LOG_OUTPUTS = [{"filename": "out.png", "subfolder": "", "type": "output"}]


class TestWriteLog:
    def test_creates_log_dir_if_not_exists(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 123, "user1", _LOG_PARSED, "success", [], None)
        assert log_dir.is_dir()

    def test_creates_json_file_in_daily_subdir(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 123, "user1", _LOG_PARSED, "success", [], None)
        files = list(log_dir.glob("*/result_*.json"))
        assert len(files) == 1

    def test_filename_matches_format(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 123, "user1", _LOG_PARSED, "success", [], None)
        filename = list(log_dir.glob("*/result_*.json"))[0].name
        assert re.match(r"result_\d{6}_\d{6}\.json", filename)

    def test_daily_dir_name_matches_date_format(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 123, "user1", _LOG_PARSED, "success", [], None)
        daily_dirs = [p for p in log_dir.iterdir() if p.is_dir()]
        assert len(daily_dirs) == 1
        assert re.match(r"\d{8}$", daily_dirs[0].name)

    def test_success_content(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 123, "user1", _LOG_PARSED, "success", _LOG_OUTPUTS, None)
        data = json.loads(list(log_dir.glob("*/*.json"))[0].read_text(encoding="utf-8"))
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
        data = json.loads(list(log_dir.glob("*/*.json"))[0].read_text(encoding="utf-8"))
        assert data["status"] == "error"
        assert data["error"] == "接続失敗"

    def test_timestamp_format(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 123, "user1", _LOG_PARSED, "success", [], None)
        data = json.loads(list(log_dir.glob("*/*.json"))[0].read_text(encoding="utf-8"))
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", data["timestamp"])

    def test_image_orientation_included_in_log(self, tmp_path):
        log_dir = tmp_path / "log"
        parsed = {**_LOG_PARSED, "image_orientation": "vertical"}
        write_log(log_dir, 123, "user1", parsed, "success", [], None)
        data = json.loads(list(log_dir.glob("*/*.json"))[0].read_text(encoding="utf-8"))
        assert data["image_orientation"] == "vertical"

    def test_image_orientation_null_when_omitted(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 123, "user1", _LOG_PARSED, "success", [], None)
        data = json.loads(list(log_dir.glob("*/*.json"))[0].read_text(encoding="utf-8"))
        assert data["image_orientation"] is None


# ── write_system_log ──────────────────────────────────────────────────────────


class TestWriteSystemLog:
    def test_creates_json_file_in_daily_subdir(self, tmp_path):
        log_dir = tmp_path / "log"
        write_system_log(log_dir, "startup", shutdown_time="18:00")
        files = list(log_dir.glob("*/system_*.json"))
        assert len(files) == 1

    def test_filename_matches_format(self, tmp_path):
        log_dir = tmp_path / "log"
        write_system_log(log_dir, "startup")
        filename = list(log_dir.glob("*/system_*.json"))[0].name
        assert re.match(r"system_\d{6}_\d{6}\.json", filename)

    def test_startup_content(self, tmp_path):
        log_dir = tmp_path / "log"
        write_system_log(log_dir, "startup", shutdown_time="18:00")
        data = json.loads(
            list(log_dir.glob("*/system_*.json"))[0].read_text(encoding="utf-8")
        )
        assert data["type"] == "startup"
        assert data["shutdown_time"] == "18:00"
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", data["timestamp"])

    def test_startup_without_shutdown_time(self, tmp_path):
        log_dir = tmp_path / "log"
        write_system_log(log_dir, "startup", shutdown_time=None)
        data = json.loads(
            list(log_dir.glob("*/system_*.json"))[0].read_text(encoding="utf-8")
        )
        assert data["type"] == "startup"
        assert data["shutdown_time"] is None

    def test_shutdown_content(self, tmp_path):
        log_dir = tmp_path / "log"
        write_system_log(log_dir, "shutdown", reason="scheduled")
        data = json.loads(
            list(log_dir.glob("*/system_*.json"))[0].read_text(encoding="utf-8")
        )
        assert data["type"] == "shutdown"
        assert data["reason"] == "scheduled"

    def test_creates_log_dir_if_not_exists(self, tmp_path):
        log_dir = tmp_path / "log"
        write_system_log(log_dir, "startup")
        assert log_dir.is_dir()


# ── write_discord_log ─────────────────────────────────────────────────────────


class TestWriteDiscordLog:
    def test_creates_json_file_in_daily_subdir(self, tmp_path):
        log_dir = tmp_path / "log"
        write_discord_log(log_dir, "discord_ready", bot_user_id=1, bot_username="Bot")
        files = list(log_dir.glob("*/discord_*.json"))
        assert len(files) == 1

    def test_filename_matches_format(self, tmp_path):
        log_dir = tmp_path / "log"
        write_discord_log(log_dir, "discord_ready", bot_user_id=1, bot_username="Bot")
        filename = list(log_dir.glob("*/discord_*.json"))[0].name
        assert re.match(r"discord_\d{6}_\d{6}\.json", filename)

    def test_discord_ready_content(self, tmp_path):
        log_dir = tmp_path / "log"
        write_discord_log(log_dir, "discord_ready", bot_user_id=123, bot_username="Bot")
        data = json.loads(
            list(log_dir.glob("*/discord_*.json"))[0].read_text(encoding="utf-8")
        )
        assert data["type"] == "discord_ready"
        assert data["bot_user_id"] == 123
        assert data["bot_username"] == "Bot"
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", data["timestamp"])

    def test_discord_message_content(self, tmp_path):
        log_dir = tmp_path / "log"
        write_discord_log(
            log_dir,
            "discord_message",
            user_id=999,
            username="user1",
            channel_id=111,
            guild_id=222,
        )
        data = json.loads(
            list(log_dir.glob("*/discord_*.json"))[0].read_text(encoding="utf-8")
        )
        assert data["type"] == "discord_message"
        assert data["user_id"] == 999
        assert data["username"] == "user1"
        assert data["channel_id"] == 111
        assert data["guild_id"] == 222

    def test_discord_slash_command_content(self, tmp_path):
        log_dir = tmp_path / "log"
        write_discord_log(
            log_dir,
            "discord_slash_command",
            user_id=777,
            username="slash_user",
            channel_id=333,
            guild_id=444,
        )
        data = json.loads(
            list(log_dir.glob("*/discord_*.json"))[0].read_text(encoding="utf-8")
        )
        assert data["type"] == "discord_slash_command"
        assert data["user_id"] == 777
        assert data["guild_id"] == 444

    def test_creates_log_dir_if_not_exists(self, tmp_path):
        log_dir = tmp_path / "log"
        write_discord_log(log_dir, "discord_ready", bot_user_id=1, bot_username="Bot")
        assert log_dir.is_dir()
