"""generate_image_bot.py のユニットテスト"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

import aiohttp

from generate_image_bot import main

from modules.const import (
    RECONNECT_WAIT,
)

from test_helper import (
    valid_config,
    write_config,
)

# ── main: WSServerHandshakeError リトライ ──────────────────────────────────────


class TestMainReconnect:
    """main() が WSServerHandshakeError を捕捉して再試行することを検証する。"""

    def _run_main(self, config_path: str):
        with patch("sys.argv", ["generate_image_bot", "-c", config_path]):
            main()

    def test_retries_on_ws_handshake_error_then_succeeds(self, tmp_path):
        """1回目に WSServerHandshakeError が発生し、2回目に正常終了するケース。"""
        config_path = write_config(tmp_path / "config.json", valid_config())
        request_info = MagicMock()
        request_info.real_url = "wss://gateway.discord.gg"
        error = aiohttp.WSServerHandshakeError(request_info, None, status=520)
        side_effects = [error, None]
        with (
            patch("generate_image_bot.ImageBot") as mock_bot_cls,
            patch("generate_image_bot.time.sleep") as mock_sleep,
            patch("generate_image_bot.write_system_log"),
        ):
            mock_bot_cls.return_value.run.side_effect = side_effects
            self._run_main(config_path)

        assert mock_bot_cls.return_value.run.call_count == 2
        mock_sleep.assert_called_once_with(RECONNECT_WAIT)

    def test_exits_normally_without_error(self, tmp_path):
        """例外が発生しない場合はリトライなしで終了する。"""
        config_path = write_config(tmp_path / "config.json", valid_config())
        with (
            patch("generate_image_bot.ImageBot") as mock_bot_cls,
            patch("generate_image_bot.time.sleep") as mock_sleep,
            patch("generate_image_bot.write_system_log"),
        ):
            mock_bot_cls.return_value.run.return_value = None
            self._run_main(config_path)

        mock_bot_cls.return_value.run.assert_called_once()
        mock_sleep.assert_not_called()

    def test_non_ws_error_propagates(self, tmp_path):
        """WSServerHandshakeError 以外の例外はそのまま伝播する。"""
        config_path = write_config(tmp_path / "config.json", valid_config())
        with (
            patch("generate_image_bot.ImageBot") as mock_bot_cls,
            patch("generate_image_bot.time.sleep"),
            patch("generate_image_bot.write_system_log"),
        ):
            mock_bot_cls.return_value.run.side_effect = RuntimeError("unexpected")
            with pytest.raises(RuntimeError, match="unexpected"):
                self._run_main(config_path)


# ── main: 起動ログ ─────────────────────────────────────────────────────────────


class TestMainStartupLog:
    def _run_main(self, config_path: str):
        with patch("sys.argv", ["generate_image_bot", "-c", config_path]):
            main()

    def test_writes_startup_log_on_launch(self, tmp_path):
        """main() 実行時に startup システムログが書き出されること。"""
        config_path = write_config(tmp_path / "config.json", valid_config())
        log_dir = tmp_path / "log"
        with (
            patch("generate_image_bot.ImageBot") as mock_bot_cls,
            patch("generate_image_bot.time.sleep"),
            patch("generate_image_bot.write_system_log") as mock_write,
        ):
            mock_bot_cls.return_value.log_dir = log_dir
            mock_bot_cls.return_value._shutdown_reason = "signal"
            mock_bot_cls.return_value.run.return_value = None
            self._run_main(config_path)

        mock_write.assert_any_call(log_dir, "startup", shutdown_time=None)

    def test_startup_log_contains_shutdown_time_when_configured(self, tmp_path):
        """config に shutdown_time が設定されている場合、起動ログに含まれること。"""
        cfg = {**valid_config(), "shutdown_time": "18:00"}
        config_path = write_config(tmp_path / "config.json", cfg)
        log_dir = tmp_path / "log"
        with (
            patch("generate_image_bot.ImageBot") as mock_bot_cls,
            patch("generate_image_bot.time.sleep"),
            patch("generate_image_bot.write_system_log") as mock_write,
        ):
            mock_bot_cls.return_value.log_dir = log_dir
            mock_bot_cls.return_value._shutdown_reason = "signal"
            mock_bot_cls.return_value.run.return_value = None
            self._run_main(config_path)

        mock_write.assert_any_call(log_dir, "startup", shutdown_time="18:00")

    def test_writes_startup_log_each_reconnect(self, tmp_path):
        """WSServerHandshakeError で再起動するたびに startup ログが書き出されること。"""
        config_path = write_config(tmp_path / "config.json", valid_config())
        log_dir = tmp_path / "log"
        request_info = MagicMock()
        request_info.real_url = "wss://gateway.discord.gg"
        error = aiohttp.WSServerHandshakeError(request_info, None, status=520)
        with (
            patch("generate_image_bot.ImageBot") as mock_bot_cls,
            patch("generate_image_bot.time.sleep"),
            patch("generate_image_bot.write_system_log") as mock_write,
        ):
            mock_bot_cls.return_value.log_dir = log_dir
            mock_bot_cls.return_value._shutdown_reason = "signal"
            mock_bot_cls.return_value.run.side_effect = [error, None]
            self._run_main(config_path)

        startup_calls = [c for c in mock_write.call_args_list if c.args[1] == "startup"]
        assert len(startup_calls) == 2


# ── main: 終了ログ ─────────────────────────────────────────────────────────────


class TestMainShutdownLog:
    def _run_main(self, config_path: str):
        with patch("sys.argv", ["generate_image_bot", "-c", config_path]):
            main()

    def test_writes_shutdown_log_on_normal_exit(self, tmp_path):
        """bot.run() 正常終了時に shutdown システムログが書き出されること。"""
        config_path = write_config(tmp_path / "config.json", valid_config())
        log_dir = tmp_path / "log"
        with (
            patch("generate_image_bot.ImageBot") as mock_bot_cls,
            patch("generate_image_bot.time.sleep"),
            patch("generate_image_bot.write_system_log") as mock_write,
        ):
            mock_bot_cls.return_value.log_dir = log_dir
            mock_bot_cls.return_value._shutdown_reason = "signal"
            mock_bot_cls.return_value.run.return_value = None
            self._run_main(config_path)

        mock_write.assert_called_with(log_dir, "shutdown", reason="signal")

    def test_shutdown_log_reason_scheduled_when_watcher_triggered(self, tmp_path):
        """定刻シャットダウン時は reason が scheduled になること。"""
        config_path = write_config(tmp_path / "config.json", valid_config())
        log_dir = tmp_path / "log"
        with (
            patch("generate_image_bot.ImageBot") as mock_bot_cls,
            patch("generate_image_bot.time.sleep"),
            patch("generate_image_bot.write_system_log") as mock_write,
        ):
            mock_bot_cls.return_value.log_dir = log_dir
            mock_bot_cls.return_value._shutdown_reason = "scheduled"
            mock_bot_cls.return_value.run.return_value = None
            self._run_main(config_path)

        mock_write.assert_called_with(log_dir, "shutdown", reason="scheduled")

    def test_no_shutdown_log_on_ws_error(self, tmp_path):
        """WSServerHandshakeError 発生時は終了ログを書かないこと。"""
        config_path = write_config(tmp_path / "config.json", valid_config())
        log_dir = tmp_path / "log"
        request_info = MagicMock()
        request_info.real_url = "wss://gateway.discord.gg"
        error = aiohttp.WSServerHandshakeError(request_info, None, status=520)
        with (
            patch("generate_image_bot.ImageBot") as mock_bot_cls,
            patch("generate_image_bot.time.sleep"),
            patch("generate_image_bot.write_system_log") as mock_write,
        ):
            mock_bot_cls.return_value.log_dir = log_dir
            mock_bot_cls.return_value._shutdown_reason = "signal"
            mock_bot_cls.return_value.run.side_effect = [error, None]
            self._run_main(config_path)

        # startup が2回、shutdown が1回（最終正常終了時のみ）
        startup_calls = [c for c in mock_write.call_args_list if c.args[1] == "startup"]
        shutdown_calls = [
            c for c in mock_write.call_args_list if c.args[1] == "shutdown"
        ]
        assert len(startup_calls) == 2
        assert len(shutdown_calls) == 1
