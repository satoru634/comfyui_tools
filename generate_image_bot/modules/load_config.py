"""Discord ボット: 設定ファイルの読み込みと検証"""

import json
import re

from modules.const import (
    REACTION_KEYS,
    MESSAGE_KEYS,
)

# ── 設定読み込み ──────────────────────────────────────────────────────────────


def parse_shutdown_time(value: str) -> tuple[int, int]:
    """'hh:mm' 形式の文字列を (hour, minute) タプルに変換する。不正な場合は ValueError。"""
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ValueError(
            f"'shutdown_time' は 'hh:mm' 形式で指定してください（例: '03:00'）: {value!r}"
        )
    hour, minute = int(value[:2]), int(value[3:])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"'shutdown_time' の時刻が不正です: {value!r}")
    return hour, minute


def _validate_reactions(reactions: dict) -> None:
    """reactions セクションの型と必須キーを検証する。"""
    if not isinstance(reactions, dict):
        raise ValueError(
            "config.json の 'reactions' はオブジェクト形式である必要があります"
        )
    for key in REACTION_KEYS:
        if key not in reactions:
            raise ValueError(f"config.json の 'reactions' に '{key}' キーがありません")
        if not isinstance(reactions[key], str) or not reactions[key].strip():
            raise ValueError(f"'reactions.{key}' は空でない文字列である必要があります")


def _validate_messages(messages: dict) -> None:
    """messages セクションの型と必須キーを検証する。"""
    if not isinstance(messages, dict):
        raise ValueError(
            "config.json の 'messages' はオブジェクト形式である必要があります"
        )
    for key in MESSAGE_KEYS:
        if key not in messages:
            raise ValueError(f"config.json の 'messages' に '{key}' キーがありません")
        if not isinstance(messages[key], str):
            raise ValueError(f"'messages.{key}' は文字列である必要があります")


def load_config(config_path: str) -> dict:
    """設定ファイルを読み込み、必須キーの存在と型を検証して返す。"""
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError("設定ファイルが見つかりません")
    except json.JSONDecodeError as e:
        raise ValueError(f"config.json の解析に失敗しました: {e}")

    if not isinstance(data, dict):
        raise ValueError("config.json はオブジェクト形式である必要があります")

    # トップレベルの文字列キーを検証する
    for key in ("discord_token", "comfyui_output_dir", "run_workflow_config"):
        if key not in data:
            raise ValueError(f"config.json に '{key}' キーがありません")
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError(f"'{key}' は空でない文字列である必要があります")

    if "reactions" not in data:
        raise ValueError("config.json に 'reactions' キーがありません")
    _validate_reactions(data["reactions"])

    if "messages" not in data:
        raise ValueError("config.json に 'messages' キーがありません")
    _validate_messages(data["messages"])

    # shutdown_time は省略・null 可（指定時は hh:mm 形式で検証する）
    st = data.get("shutdown_time")
    if st is not None:
        if not isinstance(st, str):
            raise ValueError(
                "'shutdown_time' は 'hh:mm' 形式の文字列または null である必要があります"
            )
        parse_shutdown_time(st)

    return data
