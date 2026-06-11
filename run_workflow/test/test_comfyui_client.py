"""comfyui_client.py のユニットテスト"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import requests

from test_helper import (
    make_ws_message,
)

from modules.comfyui_client import (
    ComfyUIClient,
)

# ── ComfyUIClient.submit ──────────────────────────────────────────────────────


class TestComfyUIClientSubmit:
    def setup_method(self):
        self.client = ComfyUIClient("http://127.0.0.1:8188")

    def test_valid(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"prompt_id": "abc123"}
        with patch(
            "modules.comfyui_client.requests.post", return_value=mock_resp
        ) as mock_post:
            result = self.client.submit({"node": "data"}, "client-1")
        assert result == "abc123"
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["client_id"] == "client-1"

    def test_connection_error(self):
        with patch(
            "modules.comfyui_client.requests.post",
            side_effect=requests.ConnectionError(),
        ):
            with pytest.raises(ValueError, match="ComfyUI に接続できません"):
                self.client.submit({}, "client-1")

    def test_timeout(self):
        with patch(
            "modules.comfyui_client.requests.post", side_effect=requests.Timeout()
        ):
            with pytest.raises(ValueError, match="タイムアウト"):
                self.client.submit({}, "client-1")

    def test_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("500")
        with patch("modules.comfyui_client.requests.post", return_value=mock_resp):
            with pytest.raises(ValueError, match="ComfyUI がエラーを返しました"):
                self.client.submit({}, "client-1")


# ── ComfyUIClient._monitor_ws ─────────────────────────────────────────────────


class TestComfyUIClientMonitorWs:
    def setup_method(self):
        self.client = ComfyUIClient("http://127.0.0.1:8188")

    def _run(self, messages: list) -> None:
        msgs = messages

        class FakeWs:
            def __init__(self):
                self._iter = iter(msgs)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=FakeWs())
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        with patch("modules.comfyui_client.websockets.connect", return_value=mock_cm):
            asyncio.run(self.client._monitor_ws("prompt-1", "ws://localhost/ws"))

    def test_completes_on_execution_complete(self):
        self._run(
            [make_ws_message(type="execution_complete", data={"prompt_id": "prompt-1"})]
        )

    def test_completes_on_executing_null_node(self):
        self._run(
            [
                make_ws_message(
                    type="executing", data={"node": None, "prompt_id": "prompt-1"}
                )
            ]
        )

    def test_ignores_different_prompt_id(self):
        self._run(
            [
                make_ws_message(type="execution_complete", data={"prompt_id": "other"}),
                make_ws_message(
                    type="execution_complete", data={"prompt_id": "prompt-1"}
                ),
            ]
        )

    def test_raises_on_execution_error(self):
        with pytest.raises(ValueError, match="CUDA OOM"):
            self._run(
                [
                    make_ws_message(
                        type="execution_error",
                        data={"prompt_id": "prompt-1", "exception_message": "CUDA OOM"},
                    )
                ]
            )

    def test_ignores_binary_frames(self):
        self._run(
            [
                b"\x89PNG\r\n\x1a\n",
                make_ws_message(
                    type="execution_complete", data={"prompt_id": "prompt-1"}
                ),
            ]
        )

    def test_websocket_connection_error(self):
        with patch(
            "modules.comfyui_client.websockets.connect", side_effect=OSError("refused")
        ):
            with pytest.raises(ValueError, match="WebSocket 接続エラー"):
                asyncio.run(self.client._monitor_ws("prompt-1", "ws://localhost/ws"))


# ── ComfyUIClient.get_outputs ─────────────────────────────────────────────────


class TestComfyUIClientGetOutputs:
    def setup_method(self):
        self.client = ComfyUIClient("http://127.0.0.1:8188")

    def _mock_history(self, images_by_node: dict) -> dict:
        return {
            "prompt-1": {
                "outputs": {
                    nid: {"images": imgs} for nid, imgs in images_by_node.items()
                }
            }
        }

    def test_valid_with_images(self):
        history = self._mock_history(
            {
                "9": [{"filename": "img1.png", "subfolder": "", "type": "output"}],
                "25": [{"filename": "img2.png", "subfolder": "", "type": "output"}],
            }
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = history
        with patch("modules.comfyui_client.requests.get", return_value=mock_resp):
            outputs = self.client.get_outputs("prompt-1")
        assert {o["filename"] for o in outputs} == {"img1.png", "img2.png"}

    def test_valid_no_outputs(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        with patch("modules.comfyui_client.requests.get", return_value=mock_resp):
            assert self.client.get_outputs("prompt-1") == []

    def test_connection_error(self):
        with patch(
            "modules.comfyui_client.requests.get",
            side_effect=requests.ConnectionError(),
        ):
            with pytest.raises(ValueError, match="ComfyUI に接続できません"):
                self.client.get_outputs("prompt-1")

    def test_timeout(self):
        with patch(
            "modules.comfyui_client.requests.get", side_effect=requests.Timeout()
        ):
            with pytest.raises(ValueError, match="タイムアウト"):
                self.client.get_outputs("prompt-1")


# ── ComfyUIClient._is_completed ──────────────────────────────────────────────


class TestComfyUIClientIsCompleted:
    def setup_method(self):
        self.client = ComfyUIClient("http://127.0.0.1:8188")

    def test_returns_true_when_prompt_in_history(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"prompt-1": {"outputs": {}}}
        with patch("modules.comfyui_client.requests.get", return_value=mock_resp):
            assert self.client._is_completed("prompt-1") is True

    def test_returns_false_when_prompt_not_in_history(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        with patch("modules.comfyui_client.requests.get", return_value=mock_resp):
            assert self.client._is_completed("prompt-1") is False

    def test_returns_false_on_connection_error(self):
        with patch(
            "modules.comfyui_client.requests.get",
            side_effect=requests.ConnectionError(),
        ):
            assert self.client._is_completed("prompt-1") is False


# ── ComfyUIClient.upload_image ────────────────────────────────────────────────


class TestComfyUIClientUploadImage:
    def setup_method(self):
        self.client = ComfyUIClient("http://127.0.0.1:8188")

    def test_returns_filename(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "name": "uploaded.png",
            "subfolder": "",
            "type": "input",
        }
        with patch(
            "modules.comfyui_client.requests.post", return_value=mock_resp
        ) as mock_post:
            result = self.client.upload_image(b"image_data", "photo.png")
        assert result == "uploaded.png"
        call_kwargs = mock_post.call_args.kwargs
        assert "image" in call_kwargs["files"]

    def test_connection_error(self):
        with patch(
            "modules.comfyui_client.requests.post",
            side_effect=requests.ConnectionError(),
        ):
            with pytest.raises(ValueError, match="ComfyUI に接続できません"):
                self.client.upload_image(b"data")

    def test_timeout(self):
        with patch(
            "modules.comfyui_client.requests.post", side_effect=requests.Timeout()
        ):
            with pytest.raises(ValueError, match="タイムアウト"):
                self.client.upload_image(b"data")

    def test_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("413")
        with patch("modules.comfyui_client.requests.post", return_value=mock_resp):
            with pytest.raises(ValueError, match="ComfyUI がエラーを返しました"):
                self.client.upload_image(b"data")


# ── ComfyUIClient.get_history ─────────────────────────────────────────────────


class TestComfyUIClientGetHistory:
    def setup_method(self):
        self.client = ComfyUIClient("http://127.0.0.1:8188")

    def test_returns_history_for_prompt(self):
        raw = {
            "prompt-1": {
                "outputs": {"1": {"tags": ["1girl, solo"]}},
            }
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = raw
        with patch("modules.comfyui_client.requests.get", return_value=mock_resp):
            result = self.client.get_history("prompt-1")
        assert result == raw["prompt-1"]

    def test_returns_empty_dict_when_prompt_not_found(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        with patch("modules.comfyui_client.requests.get", return_value=mock_resp):
            assert self.client.get_history("prompt-1") == {}

    def test_connection_error(self):
        with patch(
            "modules.comfyui_client.requests.get",
            side_effect=requests.ConnectionError(),
        ):
            with pytest.raises(ValueError, match="ComfyUI に接続できません"):
                self.client.get_history("prompt-1")

    def test_timeout(self):
        with patch(
            "modules.comfyui_client.requests.get", side_effect=requests.Timeout()
        ):
            with pytest.raises(ValueError, match="タイムアウト"):
                self.client.get_history("prompt-1")
