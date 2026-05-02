"""Discord ボット: レート制限と同時リクエスト制限の管理"""

import time


class RateLimiter:
    COOLDOWN_SECONDS = 30
    MAX_CONCURRENT = 4

    def __init__(self):
        self._last_request: dict = {}  # user_id -> monotonic timestamp
        self._active_counts: dict = {}  # user_id -> 処理中リクエスト数

    def check_user(self, user_id: int) -> float:
        """残りクールダウン秒数を返す。制限なしなら 0.0。"""
        elapsed = time.monotonic() - self._last_request.get(user_id, 0.0)
        return max(0.0, self.COOLDOWN_SECONDS - elapsed)

    def record_request(self, user_id: int) -> None:
        """レート制限カウント用にリクエスト時刻を記録する。"""
        self._last_request[user_id] = time.monotonic()

    def check_concurrent(self, user_id: int) -> bool:
        """同時リクエスト上限（MAX_CONCURRENT）に達していれば True を返す。"""
        return self._active_counts.get(user_id, 0) >= self.MAX_CONCURRENT

    def increment_active(self, user_id: int) -> None:
        """処理中リクエストカウンタをインクリメントする。"""
        self._active_counts[user_id] = self._active_counts.get(user_id, 0) + 1

    def decrement_active(self, user_id: int) -> None:
        """処理中リクエストカウンタをデクリメントする。0 になったキーは削除する。"""
        count = self._active_counts.get(user_id, 0)
        if count > 1:
            self._active_counts[user_id] = count - 1
        else:
            self._active_counts.pop(user_id, None)

    def has_user_active(self, user_id: int) -> bool:
        """指定ユーザーの処理中リクエストが 1 件以上あれば True を返す。"""
        return self._active_counts.get(user_id, 0) > 0

    def has_active(self) -> bool:
        """いずれかのユーザーのリクエストが処理中であれば True を返す。"""
        return any(v > 0 for v in self._active_counts.values())
