"""
A tiny in-memory limiter used to slow down password guessing on the login form.

Limitation : the counters live in this process's memory, so
they reset when the server restarts and are not shared between multiple worker
processes.
"""

import time
from collections import defaultdict, deque

_failures = defaultdict(deque)   # key -> timestamps of recent failed attempts
_MAX_KEYS = 10_000               # stops the dict growing without limit


def _recent(key, window):
    """Failed attempts for `key` inside the window (old ones are forgotten)."""
    attempts = _failures[key]
    cutoff = time.monotonic() - window
    while attempts and attempts[0] < cutoff:
        attempts.popleft()
    if not attempts:
        _failures.pop(key, None)
    return attempts


def is_blocked(key, limit, window):
    return len(_recent(key, window)) >= limit


def record_failure(key):
    if len(_failures) >= _MAX_KEYS:
        _failures.clear()
    _failures[key].append(time.monotonic())


def clear(key):
    _failures.pop(key, None)
