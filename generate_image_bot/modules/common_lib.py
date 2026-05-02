"""Discord ボット: 共通ライブラリ"""

import json
from datetime import datetime
from pathlib import Path

# ── ログ出力 ──────────────────────────────────────────────────────────────────


def write_log(
    log_dir: Path,
    user_id: int,
    username: str,
    parsed: dict,
    status: str,
    outputs: list,
    error: str | None,
) -> None:
    """生成試行の結果を log_dir 配下に result_YYYYMMDD_hhmmss.json として書き出す。"""
    # ディレクトリが存在しない場合は自動生成する
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now()
    filename = f"result_{ts.strftime('%Y%m%d_%H%M%S_%f')}.json"
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
    with open(log_dir / filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
