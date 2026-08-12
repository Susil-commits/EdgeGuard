"""Unit tests for the EWMA predictive rule engine."""

from worker.rules.predictive import project_breach


class TestProjectBreach:
    def test_returns_false_with_insufficient_history(self):
        """Needs at least 5 data points."""
        assert project_breach([70, 75, 80], threshold=90.0, horizon_minutes=360) is False

    def test_returns_false_for_flat_trend_below_threshold(self):
        """Stable metric well below threshold should not predict a breach."""
        flat = [50.0] * 20
        assert project_breach(flat, threshold=90.0, horizon_minutes=360) is False

    def test_detects_rising_trend_that_will_breach(self):
        """
        Linearly increasing disk usage: starts at 60%, grows by 0.5% per reading.
        With a 6-hour horizon, this should project a breach at 90%.
        """
        # 20 readings from 60% to 69.5% (most recent last → reversed for chronological)
        history_desc = list(reversed([60.0 + i * 0.5 for i in range(20)]))
        assert project_breach(history_desc, threshold=90.0, horizon_minutes=360) is True

    def test_does_not_breach_for_slow_rise_short_horizon(self):
        """Very slow rise over a short horizon should not project a breach."""
        # Rising from 50% → 52% over 20 readings (0.1% per reading)
        history_desc = list(reversed([50.0 + i * 0.1 for i in range(20)]))
        assert project_breach(history_desc, threshold=90.0, horizon_minutes=30) is False

    def test_returns_false_for_declining_trend(self):
        """Declining metric should never predict a breach upward."""
        history_desc = list(reversed([80.0 - i * 0.5 for i in range(20)]))
        assert project_breach(history_desc, threshold=90.0, horizon_minutes=360) is False

    def test_already_above_threshold(self):
        """If metric is already above threshold, EWMA should immediately project a breach."""
        # Already at 95%
        high_history = list(reversed([92.0 + i * 0.2 for i in range(20)]))
        assert project_breach(high_history, threshold=90.0, horizon_minutes=60) is True
