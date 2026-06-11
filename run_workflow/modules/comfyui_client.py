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

    def upload_image(self, image_data: bytes, filename: str = "image.png") -> str:
        """画像を ComfyUI にアップロードし、ComfyUI 側のファイル名を返す"""
        try:
            response = requests.post(
                f"{self.url}/upload/image",
                files={"image": (filename, image_data)},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["name"]
        except requests.ConnectionError:
            raise ValueError(f"ComfyUI に接続できません: {self.url}")
        except requests.Timeout:
            raise ValueError(f"ComfyUI への接続がタイムアウトしました: {self.url}")
        except requests.HTTPError as e:
            raise ValueError(f"ComfyUI がエラーを返しました: {e}")

    def get_history(self, prompt_id: str) -> dict:
        """ComfyUI の履歴から指定された prompt_id のデータを返す"""
        try:
            response = requests.get(f"{self.url}/history/{prompt_id}", timeout=30)
            response.raise_for_status()
            return response.json().get(prompt_id, {})
        except requests.ConnectionError:
            raise ValueError(f"ComfyUI に接続できません: {self.url}")
        except requests.Timeout:
            raise ValueError(f"ComfyUI への接続がタイムアウトしました: {self.url}")
        except requests.HTTPError as e:
            raise ValueError(f"ComfyUI がエラーを返しました: {e}")

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

    def _is_completed(self, prompt_id: str) -> bool:
        """history API でワークフローの完了を確認する"""
        try:
            response = requests.get(f"{self.url}/history/{prompt_id}", timeout=5)
            response.raise_for_status()
            return prompt_id in response.json()
        except Exception:
            return False

    async def _monitor_ws(self, prompt_id: str, ws_url: str) -> None:
        """WebSocket を監視して、指定された prompt_id のワークフローの完了を待つ。
        接続前に完了している場合は _is_completed のポーリングにフォールバックする。"""
        try:
            async with websockets.connect(ws_url) as ws:
                ws_iter = ws.__aiter__()
                while True:
                    try:
                        raw = await asyncio.wait_for(ws_iter.__anext__(), timeout=2.0)
                    except asyncio.TimeoutError:
                        # メッセージが来ない場合は history を確認する（高速実行時の競合状態対策）
                        if self._is_completed(prompt_id):
                            return
                        continue
                    except StopAsyncIteration:
                        return
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
