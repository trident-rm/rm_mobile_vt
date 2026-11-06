"""Backoff and reset policy for USB read failures."""
from __future__ import annotations

from dataclasses import dataclass
import random

from .config import RecoveryConfig


@dataclass(frozen=True)
class RecoverySnapshot:
    consecutive_failures: int
    healthy_reads: int
    last_delay_s: float
    last_error: str | None
    last_error_at: float | None
    total_errors: int
    reset_count: int


class RecoveryController:
    """Track failures, calculate backoff, and decide when a USB reset is due.

    Backoff is reset only after sustained successful reads.  This prevents the
    observed "open succeeds, immediate EIO" loop from collapsing into a tight
    reopen storm.
    """

    def __init__(self, config: RecoveryConfig, rng: random.Random | None = None) -> None:
        self.config = config
        self._rng = rng or random.Random()
        self.consecutive_failures = 0
        self.healthy_reads = 0
        self.healthy_since: float | None = None
        self.last_error: str | None = None
        self.last_error_at: float | None = None
        self.last_delay = 0.0
        self.total_errors = 0
        self.reset_count = 0
        self._last_reset_failure = 0

    def on_error(self, now: float, reason: str) -> float:
        self.consecutive_failures += 1
        self.total_errors += 1
        self.healthy_reads = 0
        self.healthy_since = None
        self.last_error = reason
        self.last_error_at = now

        exponent = max(0, self.consecutive_failures - 1)
        delay = self.config.initial_backoff_s * (self.config.multiplier ** exponent)
        delay = min(delay, self.config.max_backoff_s)
        if delay > 0 and self.config.jitter_fraction > 0:
            delay += delay * self.config.jitter_fraction * self._rng.uniform(-1.0, 1.0)
        delay = max(0.0, delay)
        self.last_delay = delay
        return delay

    def on_read_success(self, now: float) -> bool:
        """Record a successful read.  Return True if a failure streak ended."""
        self.healthy_reads += 1
        if self.healthy_since is None:
            self.healthy_since = now
        healthy_by_count = self.healthy_reads >= self.config.healthy_reads
        healthy_by_time = (
            self.healthy_since is not None
            and now - self.healthy_since >= self.config.healthy_seconds
        )
        if healthy_by_count or healthy_by_time:
            recovered = self.consecutive_failures > 0
            self.consecutive_failures = 0
            self._last_reset_failure = 0
            self.healthy_reads = 0
            self.healthy_since = None
            self.last_delay = 0.0
            return recovered
        return False

    def on_open_success(self, now: float) -> None:
        # Opening the interface proves only that libusb can claim it.  Do not
        # clear the failure streak until real reads succeed.
        self.healthy_reads = 0
        self.healthy_since = None

    def should_reset(self) -> bool:
        threshold = self.config.reset_after_failures
        if threshold <= 0:
            return False
        return (
            self.consecutive_failures >= threshold
            and self.consecutive_failures - self._last_reset_failure >= threshold
        )

    def mark_reset(self) -> None:
        self._last_reset_failure = self.consecutive_failures
        self.reset_count += 1

    def snapshot(self) -> RecoverySnapshot:
        return RecoverySnapshot(
            consecutive_failures=self.consecutive_failures,
            healthy_reads=self.healthy_reads,
            last_delay_s=self.last_delay,
            last_error=self.last_error,
            last_error_at=self.last_error_at,
            total_errors=self.total_errors,
            reset_count=self.reset_count,
        )
