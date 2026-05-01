"""Discord ボット: レート制限と生成ロックの管理"""

import time

# ── レート制限・生成ロック ─────────────────────────────────────────────────────


class RateLimiter:
    COOLDOWN_SECONDS = 30

    def __init__(self):
        self._last_request: dict = {}  # user_id -> monotonic timestamp
        self._generating = False

    def check_user(self, user_id: int) -> float:
        """残りクールダウン秒数を返す。制限なしなら 0.0。"""
        elapsed = time.monotonic() - self._last_request.get(user_id, 0.0)
        return max(0.0, self.COOLDOWN_SECONDS - elapsed)

    def record_request(self, user_id: int) -> None:
        """レート制限カウント用にリクエスト時刻を記録する。"""
        self._last_request[user_id] = time.monotonic()

    def is_generating(self) -> bool:
        """グローバル生成ロックの状態を返す。"""
        return self._generating

    def set_generating(self, value: bool) -> None:
        """グローバル生成ロックをセット / 解除する。"""
        self._generating = value
