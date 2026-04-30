import json


# Discord ボット経由でユーザー入力を受け取るため、巨大文字列によるメモリ枯渇を防ぐ上限
MAX_PROMPT_LENGTH = 3000

IMAGE_SIZE_MIN = 512
IMAGE_SIZE_MAX = 2048


def _validate_image_size(image_size: dict) -> None:
    """入力 JSON の image_size フィールドを検証する"""
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
    """config.json の loras セクション（name -> {file, strength} の辞書）を検証する"""
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
    """config.json を読み込んで内容を検証する。問題があれば ValueError を送出する。"""
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
    """入力 JSON の loras フィールド（使用する LoRA 名のリスト）を検証する"""
    if not isinstance(loras, list):
        raise ValueError("'loras' はリスト形式である必要があります")
    if len(loras) > 4:
        raise ValueError(f"LoRA は最大4個まで指定できます（指定数: {len(loras)}）")
    for i, name in enumerate(loras):
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"'loras[{i}]' は空でない文字列である必要があります")


def _validate_prompts(prompts: dict) -> None:
    """入力 JSON の prompts フィールド（positive/negative プロンプト）を検証する"""
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


def validate_inputs(loras: list[str], prompts: dict, image_size: dict | None) -> bool:
    """入力データを検証する"""
    _validate_loras(loras)
    _validate_prompts(prompts)
    if image_size is not None:
        _validate_image_size(image_size)
    return True


def load_and_validate_input(input_path: str) -> dict:
    """入力ファイルを読み込んで内容を検証する。問題があれば ValueError を送出する。"""
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
    return data
