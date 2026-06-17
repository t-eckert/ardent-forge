"""Pure helpers for task resilience: failure classification + backoff math.

No I/O — imported by the coordinator and store to decide whether a failed task
should be retried and how long to wait before the next attempt.
"""

# Failure kinds. Recorded on Task.failure_kind and used to decide retry-ability.
TRANSIENT = "transient"        # unexpected exception in a producing stage
TIMEOUT = "timeout"            # stage exceeded its timeout (in-process or reaper)
DECLINED = "declined"          # triage gate returned False — deliberate
VERIFICATION = "verification"  # verify gate returned False — deliberate
TERMINAL = "terminal"          # generic non-retryable failure

_RETRYABLE = frozenset({TRANSIENT, TIMEOUT})


def is_retryable(kind: str | None) -> bool:
    """Only transient exceptions and timeouts are retried automatically."""
    return kind in _RETRYABLE


def backoff(attempt: int, base: int, cap: int) -> int:
    """Seconds to wait before retry number ``attempt`` (1-indexed).

    Exponential: base * 2**(attempt-1), capped at ``cap``.
    attempt=1 → base, attempt=2 → 2*base, ...
    """
    return min(base * (2 ** (attempt - 1)), cap)
