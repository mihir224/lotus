from lotus_api.rate_limit import FixedWindowRateLimiter


def test_rate_limiter_rejects_requests_over_limit() -> None:
    limiter = FixedWindowRateLimiter(requests=2, window_seconds=60)

    assert limiter.check("alice") is None
    assert limiter.check("alice") is None
    assert limiter.check("alice") is not None
    assert limiter.check("bob") is None
