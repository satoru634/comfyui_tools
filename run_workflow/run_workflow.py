"""ComfyUI ワークフロー自動実行スクリプト"""

import argparse
import asyncio
import copy
import json
import random
import sys
import uuid
from datetime import datetime
from pathlib import Path

import requests
import websockets

# Discord ボット経由でユーザー入力を受け取るため、巨大文字列によるメモリ枯渇を防ぐ上限
MAX_PROMPT_LENGTH = 3000

IMAGE_SIZE_MIN = 512
IMAGE_SIZE_MAX = 2048

# ── 結果出力 ──────────────────────────────────────────────────────────────────


def write_result(
    output_path: str,
    status: str,
    error: str | None,
    parameters: dict | None = None,
    template: str | None = None,
    prompt_id: str | None = None,
    outputs: list | None = None,
):
    result = {
        "status": status,
        "prompt_id": prompt_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "template": template,
        "parameters": parameters or {},
        "outputs": outputs or [],
        "error": error,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


# ── 設定・入力読み込み ─────────────────────────────────────────────────────────


def _validate_image_size(image_size: dict) -> None:
    if not isinstance(image_size, dict):
        raise ValueError("'image_size' はオブジェクト形式である必要があります")
    for key in ("width", "height"):
        if key not in image_size:
            raise ValueError(f"'image_size' に '{key}' キーがありません")
        val = image_size[key]
        if isinstance(val, bool) or not isinstance(val, int):
            raise ValueError(f"'image_size.{key}' は整数である必要があります")
        if not (IMAGE_SIZE_MIN <= val <= IMAGE_SIZE_MAX):
            raise ValueError(
                f"'image_size.{key}' は {IMAGE_SIZE_MIN}〜{IMAGE_SIZE_MAX} の範囲で指定してください（指定値: {val}）"
            )
        if val % 8 != 0:
            raise ValueError(
                f"'image_size.{key}' は 8 の倍数である必要があります（指定値: {val}）"
            )


def _validate_lora_entries(loras: dict) -> None:
    # config.json の loras セクション（name -> {file, strength} の辞書）を検証する
    if not isinstance(loras, dict):
        raise ValueError(
            "config.json の 'loras' はオブジェクト形式である必要があります"
        )
    for name, entry in loras.items():
        if not isinstance(entry, dict):
            raise ValueError(
                f"config.json loras['{name}'] はオブジェクト形式である必要があります"
            )
        if (
            "file" not in entry
            or not isinstance(entry["file"], str)
            or not entry["file"].strip()
        ):
            raise ValueError(
                f"config.json loras['{name}'].file は空でない文字列である必要があります"
            )
        if "strength" not in entry or not isinstance(entry["strength"], (int, float)):
            raise ValueError(
                f"config.json loras['{name}'].strength は数値である必要があります"
            )


def load_config(config_path: str) -> dict:
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError("設定ファイルが見つかりません")
    except json.JSONDecodeError as e:
        raise ValueError(f"config.json の解析に失敗しました: {e}")

    if not isinstance(data, dict):
        raise ValueError("config.json はオブジェクト形式である必要があります")
    if "comfyui_url" not in data:
        raise ValueError("config.json に 'comfyui_url' キーがありません")
    if not isinstance(data["comfyui_url"], str) or not data["comfyui_url"].strip():
        raise ValueError("'comfyui_url' は空でない文字列である必要があります")
    if "default_image_size" not in data:
        raise ValueError("config.json に 'default_image_size' キーがありません")
    try:
        _validate_image_size(data["default_image_size"])
    except ValueError as e:
        raise ValueError(f"config.json の default_image_size が不正です: {e}") from e
    if "loras" not in data:
        raise ValueError("config.json に 'loras' キーがありません")
    _validate_lora_entries(data["loras"])
    return data


def _validate_loras(loras: list) -> None:
    # 入力 JSON の loras フィールド（使用する LoRA 名のリスト）を検証する
    if not isinstance(loras, list):
        raise ValueError("'loras' はリスト形式である必要があります")
    if len(loras) > 4:
        raise ValueError(f"LoRA は最大4個まで指定できます（指定数: {len(loras)}）")
    for i, name in enumerate(loras):
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"'loras[{i}]' は空でない文字列である必要があります")


def _validate_prompts(prompts: dict) -> None:
    if not isinstance(prompts, dict):
        raise ValueError("'prompts' はオブジェクト形式である必要があります")
    for key in ("positive", "negative"):
        if key not in prompts:
            raise ValueError(f"'prompts' に '{key}' キーがありません")
        if not isinstance(prompts[key], str):
            raise ValueError(f"'prompts.{key}' は文字列である必要があります")
        if len(prompts[key]) > MAX_PROMPT_LENGTH:
            raise ValueError(
                f"'prompts.{key}' が長すぎます（最大 {MAX_PROMPT_LENGTH} 文字）"
            )


def load_and_validate_input(input_path: str) -> dict:
    try:
        with open(input_path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError("入力ファイルが見つかりません")
    except json.JSONDecodeError as e:
        raise ValueError(f"入力 JSON の解析に失敗しました: {e}")

    if not isinstance(data, dict):
        raise ValueError("入力 JSON はオブジェクト形式である必要があります")
    if "loras" not in data:
        raise ValueError("入力 JSON に 'loras' キーがありません")
    if "prompts" not in data:
        raise ValueError("入力 JSON に 'prompts' キーがありません")
    _validate_loras(data["loras"])
    _validate_prompts(data["prompts"])
    if "image_size" in data:
        _validate_image_size(data["image_size"])
    return data


# ── LoRA 解決 ─────────────────────────────────────────────────────────────────


def resolve_loras(lora_names: list[str], lora_list: dict) -> list[dict]:
    # ユーザーが指定した LoRA 名を、config.json に定義された実ファイル名・強度に変換する
    resolved = []
    for name in lora_names:
        if name not in lora_list:
            raise ValueError(f"LoRA '{name}' が lora_list.json に存在しません")
        entry = lora_list[name]
        resolved.append(
            {"name": name, "file": entry["file"], "strength": entry["strength"]}
        )
    return resolved


# ── ワークフロー構築 ──────────────────────────────────────────────────────────


class WorkflowBuilder:
    def __init__(self, templates_dir: str):
        self.templates_dir = Path(templates_dir)

    def select_template(self, lora_count: int) -> str:
        # LoRA 数に応じたテンプレートを選択する（template_lora_0.json 〜 template_lora_4.json）
        if not 0 <= lora_count <= 4:
            raise ValueError(
                f"LoRA は 0〜4 個の範囲で指定してください（指定数: {lora_count}）"
            )
        path = self.templates_dir / f"template_lora_{lora_count}.json"
        if not path.exists():
            raise ValueError(
                f"テンプレートファイルが見つかりません: template_lora_{lora_count}.json"
            )
        return str(path)

    def load_template(self, template_path: str) -> dict:
        name = Path(template_path).name
        try:
            with open(template_path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise ValueError(f"テンプレートファイルが見つかりません: {name}")
        except json.JSONDecodeError as e:
            raise ValueError(f"テンプレート JSON の解析に失敗しました ({name}): {e}")

    def apply(
        self,
        workflow: dict,
        prompts: dict,
        resolved_loras: list[dict],
        seed: int | None = None,
        image_size: dict | None = None,
    ) -> dict:
        # テンプレートを直接書き換えないよう deepcopy してから処理する
        workflow = copy.deepcopy(workflow)
        # ComfyUI API 形式はノード ID がキーのフラット辞書のため、_meta.title で書き換え対象を特定する
        title_map = {
            node["_meta"]["title"]: node
            for node in workflow.values()
            if isinstance(node, dict) and "_meta" in node
        }
        self._apply_prompts(title_map, prompts)
        self._apply_loras(title_map, resolved_loras)
        if image_size is not None:
            self._apply_image_size(title_map, image_size)
        self._apply_seeds(
            workflow, seed if seed is not None else random.randint(0, 2**53)
        )
        return workflow

    def _apply_prompts(self, title_map: dict, prompts: dict) -> None:
        for key, field in (
            ("positive_prompt", "positive"),
            ("negative_prompt", "negative"),
        ):
            if key not in title_map:
                raise ValueError(f"テンプレートにノード '{key}' が見つかりません")
            title_map[key]["inputs"]["text"] = prompts[field]

    def _apply_image_size(self, title_map: dict, image_size: dict) -> None:
        key = "empty_latent_image"
        if key not in title_map:
            raise ValueError(f"テンプレートにノード '{key}' が見つかりません")
        title_map[key]["inputs"]["width"] = image_size["width"]
        title_map[key]["inputs"]["height"] = image_size["height"]

    def _apply_loras(self, title_map: dict, resolved_loras: list[dict]) -> None:
        for i, lora in enumerate(resolved_loras, start=1):
            key = f"lora_loader_{i}"
            if key not in title_map:
                raise ValueError(f"テンプレートにノード '{key}' が見つかりません")
            title_map[key]["inputs"]["lora_name"] = lora["file"]
            title_map[key]["inputs"]["strength_model"] = lora["strength"]

    def _apply_seeds(self, workflow: dict, seed: int) -> None:
        # inputs.seed を持つすべてのノードに同一 seed を設定する
        for node in workflow.values():
            if (
                isinstance(node, dict)
                and isinstance(node.get("inputs"), dict)
                and "seed" in node["inputs"]
            ):
                node["inputs"]["seed"] = seed


# ── ComfyUI 通信 ──────────────────────────────────────────────────────────────


class ComfyUIClient:
    def __init__(self, comfyui_url: str):
        self.url = comfyui_url

    def submit(self, workflow: dict, client_id: str) -> str:
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
        # HTTP URL を WebSocket URL に変換して接続する
        ws_url = self.url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws?clientId={client_id}"
        asyncio.run(self._monitor_ws(prompt_id, ws_url))

    def get_outputs(self, prompt_id: str) -> list[dict]:
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
        try:
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


# ── ワークフロー実行 ──────────────────────────────────────────────────────────


class WorkflowRunner:
    """ComfyUI ワークフローの実行を担うクラス。Discord ボット等から import して使用する。"""

    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self._templates_dir = str(Path(__file__).parent / "templates")
        # execute() 実行後に結果を保持する属性。run() が result.json 出力に使用する
        self.template_path: str | None = None
        self.prompt_id: str | None = None
        self.parameters: dict = {}

    def execute(
        self, loras: list[str], prompts: dict, image_size: dict | None = None
    ) -> list[dict]:
        """ワークフローを実行し、出力ファイル一覧を返す。エラー時は ValueError を送出。"""
        self.template_path = None
        self.prompt_id = None
        self.parameters = {}

        _validate_loras(loras)
        _validate_prompts(prompts)
        if image_size is not None:
            _validate_image_size(image_size)
        effective_image_size = (
            image_size if image_size is not None else self.config["default_image_size"]
        )
        resolved = resolve_loras(loras, self.config["loras"])
        self.parameters = {
            "positive": prompts["positive"],
            "negative": prompts["negative"],
            "loras": resolved,
            "image_size": effective_image_size,
        }

        builder = WorkflowBuilder(self._templates_dir)
        self.template_path = builder.select_template(len(resolved))
        workflow = builder.load_template(self.template_path)
        workflow = builder.apply(
            workflow, prompts, resolved, image_size=effective_image_size
        )

        client = ComfyUIClient(self.config["comfyui_url"])
        client_id = str(uuid.uuid4())
        print(f"ワークフロー送信中: {self.config['comfyui_url']}")
        self.prompt_id = client.submit(workflow, client_id)
        print(f"送信完了 prompt_id={self.prompt_id}")
        print("実行完了を待機中...")
        client.monitor(self.prompt_id, client_id)
        outputs = client.get_outputs(self.prompt_id)
        print(f"出力ファイル数: {len(outputs)}")
        return outputs

    def run(self, input_path: str, output_path: str) -> None:
        """入力ファイルを読み込んでワークフローを実行し、結果を output_path に書き出す。"""
        try:
            input_data = load_and_validate_input(input_path)
            outputs = self.execute(
                input_data["loras"],
                input_data["prompts"],
                input_data.get("image_size"),
            )
        except ValueError as e:
            write_result(
                output_path,
                "error",
                str(e),
                parameters=self.parameters,
                template=self.template_path,
            )
            print(f"エラー: {e}", file=sys.stderr)
            sys.exit(1)

        write_result(
            output_path,
            "success",
            None,
            parameters=self.parameters,
            template=self.template_path,
            prompt_id=self.prompt_id,
            outputs=outputs,
        )
        print(f"結果を保存しました: {output_path}")


# ── エントリポイント ──────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="ComfyUI ワークフロー自動実行")
    parser.add_argument("-i", "--input", required=True, help="入力 JSON ファイルのパス")
    default_output = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    parser.add_argument(
        "-o",
        "--output",
        default=default_output,
        help="結果 JSON の出力先（省略時: タイムスタンプ付きファイル名）",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.json",
        help="設定ファイルのパス（省略時: config.json）",
    )
    args = parser.parse_args()

    WorkflowRunner(args.config).run(args.input, args.output)


if __name__ == "__main__":
    main()
