"""rate_limiter.py のユニットテスト"""

from unittest.mock import patch

from modules.rate_limiter import RateLimiter

# ── RateLimiter: レート制限 ────────────────────────────────────────────────────


class TestRateLimiterCooldown:
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


# ── RateLimiter: 同時リクエスト上限 ───────────────────────────────────────────


class TestRateLimiterConcurrent:
    def setup_method(self):
        self.limiter = RateLimiter()

    def test_new_user_not_at_limit(self):
        assert self.limiter.check_concurrent(1) is False

    def test_below_max_not_at_limit(self):
        for _ in range(RateLimiter.MAX_CONCURRENT - 1):
            self.limiter.increment_active(1)
        assert self.limiter.check_concurrent(1) is False

    def test_at_max_is_at_limit(self):
        for _ in range(RateLimiter.MAX_CONCURRENT):
            self.limiter.increment_active(1)
        assert self.limiter.check_concurrent(1) is True

    def test_decrement_below_max_releases_limit(self):
        for _ in range(RateLimiter.MAX_CONCURRENT):
            self.limiter.increment_active(1)
        self.limiter.decrement_active(1)
        assert self.limiter.check_concurrent(1) is False

    def test_decrement_to_zero_removes_entry(self):
        self.limiter.increment_active(1)
        self.limiter.decrement_active(1)
        assert 1 not in self.limiter._active_counts

    def test_decrement_below_zero_is_safe(self):
        self.limiter.decrement_active(1)
        assert self.limiter.check_concurrent(1) is False

    def test_different_users_are_independent(self):
        for _ in range(RateLimiter.MAX_CONCURRENT):
            self.limiter.increment_active(1)
        assert self.limiter.check_concurrent(2) is False

    def test_has_user_active_false_when_no_requests(self):
        assert self.limiter.has_user_active(1) is False

    def test_has_user_active_true_after_increment(self):
        self.limiter.increment_active(1)
        assert self.limiter.has_user_active(1) is True

    def test_has_user_active_false_after_decrement_to_zero(self):
        self.limiter.increment_active(1)
        self.limiter.decrement_active(1)
        assert self.limiter.has_user_active(1) is False

    def test_has_user_active_independent_of_other_users(self):
        self.limiter.increment_active(2)
        assert self.limiter.has_user_active(1) is False

    def test_has_active_false_when_no_requests(self):
        assert self.limiter.has_active() is False

    def test_has_active_true_after_increment(self):
        self.limiter.increment_active(1)
        assert self.limiter.has_active() is True

    def test_has_active_false_after_all_decremented(self):
        self.limiter.increment_active(1)
        self.limiter.increment_active(2)
        self.limiter.decrement_active(1)
        self.limiter.decrement_active(2)
        assert self.limiter.has_active() is False

    def test_has_active_true_when_any_user_active(self):
        self.limiter.increment_active(1)
        self.limiter.decrement_active(1)
        self.limiter.increment_active(2)
        assert self.limiter.has_active() is True

    def test_concurrent_independent_of_rate_limit(self):
        self.limiter.record_request(1)
        for _ in range(RateLimiter.MAX_CONCURRENT):
            self.limiter.increment_active(1)
        assert self.limiter.check_user(1) > 0.0
        assert self.limiter.check_concurrent(1) is True

        self.limiter.decrement_active(1)
        assert self.limiter.check_user(1) > 0.0
        assert self.limiter.check_concurrent(1) is False
