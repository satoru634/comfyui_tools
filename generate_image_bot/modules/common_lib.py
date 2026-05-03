"""Discord ボット: 共通ライブラリ"""

import json
from datetime import datetime
from pathlib import Path

# ── ログ出力 ──────────────────────────────────────────────────────────────────


def _daily_dir(log_dir: Path, ts: datetime) -> Path:
    daily = log_dir / ts.strftime("%Y%m%d")
    daily.mkdir(parents=True, exist_ok=True)
    return daily


def write_log(
    log_dir: Path,
    user_id: int,
    username: str,
    parsed: dict,
    status: str,
    outputs: list,
    error: str | None,
) -> None:
    """生成試行の結果を log_dir/YYYYMMDD/result_hhmmss_ffffff.json として書き出す。"""
    ts = datetime.now()
    daily = _daily_dir(log_dir, ts)
    filename = f"result_{ts.strftime('%H%M%S_%f')}.json"
    data = {
        "status": status,
        "timestamp": ts.isoformat(timespec="seconds"),
        "user_id": user_id,
        "username": username,
        "loras": parsed.get("loras", []),
        "positive": parsed.get("positive", ""),
        "negative": parsed.get("negative", ""),
        "image_orientation": parsed.get("image_orientation"),
        "outputs": outputs,
        "error": error,
    }
    with open(daily / filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_system_log(log_dir: Path, event_type: str, **kwargs) -> None:
    """システムイベント（起動・終了）を log_dir/YYYYMMDD/system_hhmmss_ffffff.json として書き出す。"""
    ts = datetime.now()
    daily = _daily_dir(log_dir, ts)
    filename = f"system_{ts.strftime('%H%M%S_%f')}.json"
    data = {"type": event_type, "timestamp": ts.isoformat(timespec="seconds"), **kwargs}
    with open(daily / filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_discord_log(log_dir: Path, event_type: str, **kwargs) -> None:
    """Discord イベント（接続・メッセージ等）を log_dir/YYYYMMDD/discord_hhmmss_ffffff.json として書き出す。"""
    ts = datetime.now()
    daily = _daily_dir(log_dir, ts)
    filename = f"discord_{ts.strftime('%H%M%S_%f')}.json"
    data = {"type": event_type, "timestamp": ts.isoformat(timespec="seconds"), **kwargs}
    with open(daily / filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
