import json
import asyncio
import requests
import websockets


class ComfyUIClient:
    def __init__(self, comfyui_url: str):
        self.url = comfyui_url

    def submit(self, workflow: dict, client_id: str) -> str:
        """ワークフローを ComfyUI に送信して prompt_id を返す"""
        try:
            response = requests.post(
                f"{self.url}/prompt",
                json={"prompt": workflow, "client_id": client_id},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["prompt_id"]
        except requests.ConnectionError:
            raise ValueError(f"ComfyUI に接続できません: {self.url}")
        except requests.Timeout:
            raise ValueError(f"ComfyUI への接続がタイムアウトしました: {self.url}")
        except requests.HTTPError as e:
            raise ValueError(f"ComfyUI がエラーを返しました: {e}")

    def monitor(self, prompt_id: str, client_id: str) -> None:
        """ComfyUI の WebSocket を監視して、ワークフローの完了を待つ"""
        # HTTP URL を WebSocket URL に変換して接続する
        ws_url = self.url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws?clientId={client_id}"
        asyncio.run(self._monitor_ws(prompt_id, ws_url))

    def get_outputs(self, prompt_id: str) -> list[dict]:
        """ComfyUI の履歴から指定された prompt_id の出力を取得する"""
        try:
            response = requests.get(f"{self.url}/history/{prompt_id}", timeout=30)
            response.raise_for_status()
            history = response.json()
            outputs = []
            for node_outputs in history.get(prompt_id, {}).get("outputs", {}).values():
                for image in node_outputs.get("images", []):
                    outputs.append(image)
            return outputs
        except requests.ConnectionError:
            raise ValueError(f"ComfyUI に接続できません: {self.url}")
        except requests.Timeout:
            raise ValueError(f"ComfyUI への接続がタイムアウトしました: {self.url}")
        except requests.HTTPError as e:
            raise ValueError(f"ComfyUI がエラーを返しました: {e}")

    async def _monitor_ws(self, prompt_id: str, ws_url: str) -> None:
        """WebSocket を監視して、指定された prompt_id のワークフローの完了を待つ"""
        try:
            # ComfyUI はワークフローの進行状況を WebSocket で送信するため、完了まで監視する
            async with websockets.connect(ws_url) as ws:
                async for raw in ws:
                    if isinstance(raw, bytes):
                        continue  # ComfyUI はプレビュー画像をバイナリフレームで送信するためスキップする
                    msg = json.loads(raw)
                    msg_type = msg.get("type")
                    msg_data = msg.get("data", {})
                    if msg_data.get("prompt_id") != prompt_id:
                        continue
                    if msg_type == "execution_complete":
                        return
                    if msg_type == "execution_error":
                        raise ValueError(
                            f"ComfyUI 実行エラー: {msg_data.get('exception_message', '不明なエラー')}"
                        )
                    # node が None の executing メッセージはワークフロー全体の完了を示す
                    if msg_type == "executing" and msg_data.get("node") is None:
                        return
        except (OSError, websockets.exceptions.WebSocketException) as e:
            raise ValueError(f"WebSocket 接続エラー: {e}")
