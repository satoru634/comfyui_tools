"""rate_limiter.py のユニットテスト"""

from unittest.mock import patch

from modules.rate_limiter import RateLimiter

# ── RateLimiter ───────────────────────────────────────────────────────────────


class TestRateLimiter:
    def setup_method(self):
        self.limiter = RateLimiter()

    def test_new_user_not_limited(self):
        assert self.limiter.check_user(1) == 0.0

    def test_immediately_after_record_is_limited(self):
        self.limiter.record_request(1)
        assert self.limiter.check_user(1) > 0.0

    def test_remaining_seconds_near_cooldown_after_record(self):
        self.limiter.record_request(1)
        remaining = self.limiter.check_user(1)
        assert remaining <= RateLimiter.COOLDOWN_SECONDS

    def test_remaining_decreases_over_time(self):
        with patch("modules.rate_limiter.time.monotonic") as mock_time:
            mock_time.return_value = 1000.0
            self.limiter.record_request(1)
            mock_time.return_value = 1015.0
            remaining = self.limiter.check_user(1)
            assert 14.9 < remaining <= 15.0

    def test_after_cooldown_not_limited(self):
        with patch("modules.rate_limiter.time.monotonic") as mock_time:
            mock_time.return_value = 1000.0
            self.limiter.record_request(1)
            mock_time.return_value = 1000.0 + RateLimiter.COOLDOWN_SECONDS + 1
            assert self.limiter.check_user(1) == 0.0

    def test_different_users_are_independent(self):
        self.limiter.record_request(1)
        assert self.limiter.check_user(2) == 0.0

    def test_generating_initially_false(self):
        assert self.limiter.is_generating() is False

    def test_set_generating_true(self):
        self.limiter.set_generating(True)
        assert self.limiter.is_generating() is True

    def test_set_generating_false_after_true(self):
        self.limiter.set_generating(True)
        self.limiter.set_generating(False)
        assert self.limiter.is_generating() is False

    def test_generating_flag_independent_of_rate_limit(self):
        # 生成ロックとレート制限は独立して動作する
        self.limiter.record_request(1)
        self.limiter.set_generating(True)
        assert self.limiter.check_user(1) > 0.0
        assert self.limiter.is_generating() is True

        self.limiter.set_generating(False)
        assert self.limiter.check_user(1) > 0.0
        assert self.limiter.is_generating() is False
