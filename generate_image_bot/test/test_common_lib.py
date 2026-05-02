"""common_lib.py のテスト"""

import json
import re

from modules.common_lib import write_log

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
        assert re.match(r"result_\d{8}_\d{6}_\d{6}\.json", filename)

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

    def test_image_orientation_included_in_log(self, tmp_path):
        log_dir = tmp_path / "log"
        parsed = {**_LOG_PARSED, "image_orientation": "vertical"}
        write_log(log_dir, 123, "user1", parsed, "success", [], None)
        data = json.loads(list(log_dir.glob("*.json"))[0].read_text(encoding="utf-8"))
        assert data["image_orientation"] == "vertical"

    def test_image_orientation_null_when_omitted(self, tmp_path):
        log_dir = tmp_path / "log"
        write_log(log_dir, 123, "user1", _LOG_PARSED, "success", [], None)
        data = json.loads(list(log_dir.glob("*.json"))[0].read_text(encoding="utf-8"))
        assert data["image_orientation"] is None
