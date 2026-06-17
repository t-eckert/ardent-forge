from forge import retry


def test_failure_kinds_are_distinct_strings():
    kinds = {retry.TRANSIENT, retry.TIMEOUT, retry.DECLINED, retry.VERIFICATION, retry.TERMINAL}
    assert len(kinds) == 5
    assert retry.TRANSIENT == "transient"
    assert retry.TIMEOUT == "timeout"


def test_only_transient_and_timeout_are_retryable():
    assert retry.is_retryable(retry.TRANSIENT) is True
    assert retry.is_retryable(retry.TIMEOUT) is True
    assert retry.is_retryable(retry.DECLINED) is False
    assert retry.is_retryable(retry.VERIFICATION) is False
    assert retry.is_retryable(retry.TERMINAL) is False
    assert retry.is_retryable(None) is False


def test_backoff_is_capped_exponential():
    # base=60, cap=900 → 60, 120, 240, 480, 900 (capped), 900 ...
    assert retry.backoff(1, base=60, cap=900) == 60
    assert retry.backoff(2, base=60, cap=900) == 120
    assert retry.backoff(3, base=60, cap=900) == 240
    assert retry.backoff(4, base=60, cap=900) == 480
    assert retry.backoff(5, base=60, cap=900) == 900
    assert retry.backoff(6, base=60, cap=900) == 900
