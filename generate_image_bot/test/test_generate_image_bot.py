"""generate_image_bot.py のユニットテスト"""

import pytest
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
        ):
            mock_bot_cls.return_value.run.side_effect = RuntimeError("unexpected")
            with pytest.raises(RuntimeError, match="unexpected"):
                self._run_main(config_path)
