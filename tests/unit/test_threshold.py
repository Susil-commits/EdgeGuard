"""Unit tests for threshold rule engine."""

from worker.rules.threshold import check


class TestThresholdCheck:
    def test_no_match_for_unknown_metric(self):
        assert check("node-1", "unknown_metric", 99.0) is None

    def test_no_match_below_threshold(self):
        assert check("node-1", "cpu_percent", 50.0) is None

    def test_matches_warning(self):
        result = check("node-1", "cpu_percent", 91.0)
        assert result is not None
        assert result.severity == "warning"
        assert result.rule_id == "cpu_high"

    def test_matches_critical_over_warning(self):
        """When both warning and critical rules match, critical should be returned."""
        result = check("node-1", "cpu_percent", 99.0)
        assert result is not None
        assert result.severity == "critical"
        assert result.rule_id == "cpu_critical"

    def test_service_inactive(self):
        """service_active == 0.0 should trigger a critical incident."""
        result = check("node-1", "service_active", 0.0)
        assert result is not None
        assert result.severity == "critical"
        assert result.rule_id == "service_inactive"

    def test_service_active_no_incident(self):
        """service_active == 1.0 should not trigger any incident."""
        result = check("node-1", "service_active", 1.0)
        assert result is None

    def test_disk_warning(self):
        result = check("node-1", "disk_percent", 82.0)
        assert result is not None
        assert result.severity == "warning"

    def test_disk_critical(self):
        result = check("node-1", "disk_percent", 91.0)
        assert result is not None
        assert result.severity == "critical"
