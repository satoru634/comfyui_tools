"""共通ユーティリティ関数"""

import inspect
from pathlib import Path


def loc() -> str:
    """呼び出し元のファイル名と行番号を [filename.py:LXX] 形式で返す。"""
    f = inspect.currentframe().f_back
    return f"[{Path(f.f_code.co_filename).name}:L{f.f_lineno}]"
