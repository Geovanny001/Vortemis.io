from vortemis.infrastructure.persistence.login_limiter import LoginLimiter


def test_limiter_locks_after_max_attempts() -> None:
    now = [0.0]
    limiter = LoginLimiter(
        max_attempts=3,
        lockout_seconds=60.0,
        clock=lambda: now[0],
    )

    for _ in range(3):
        limiter.record_failure("admin_carles")

    assert limiter.is_locked("admin_carles") is True
    assert limiter.allow("admin_carles") is False
    assert limiter.remaining_seconds("admin_carles") == 60.0

    now[0] = 60.1

    assert limiter.is_locked("admin_carles") is False
    assert limiter.allow("admin_carles") is True


def test_limiter_success_resets_failures() -> None:
    limiter = LoginLimiter(max_attempts=3, clock=lambda: 0.0)

    limiter.record_failure("admin_carles")
    limiter.record_failure("admin_carles")
    limiter.record_success("admin_carles")
    limiter.record_failure("admin_carles")
    limiter.record_failure("admin_carles")

    assert limiter.is_locked("admin_carles") is False


def test_limiter_window_resets_failures() -> None:
    now = [0.0]
    limiter = LoginLimiter(
        max_attempts=3,
        window_seconds=10.0,
        clock=lambda: now[0],
    )

    limiter.record_failure("admin_carles")
    limiter.record_failure("admin_carles")
    now[0] = 11.0
    limiter.record_failure("admin_carles")

    assert limiter.is_locked("admin_carles") is False


def test_limiter_is_per_user() -> None:
    limiter = LoginLimiter(max_attempts=2, clock=lambda: 0.0)

    limiter.record_failure("admin_carles")
    limiter.record_failure("admin_carles")

    assert limiter.is_locked("admin_carles") is True
    assert limiter.is_locked("soc_analyst") is False
