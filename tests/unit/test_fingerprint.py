"""Unit tests for fingerprint generation."""

from worker.rules.fingerprint import make_fingerprint


def test_fingerprint_is_deterministic():
    fp1 = make_fingerprint("node-abc", "disk_critical")
    fp2 = make_fingerprint("node-abc", "disk_critical")
    assert fp1 == fp2


def test_fingerprint_differs_by_node():
    fp1 = make_fingerprint("node-abc", "disk_critical")
    fp2 = make_fingerprint("node-xyz", "disk_critical")
    assert fp1 != fp2


def test_fingerprint_differs_by_rule():
    fp1 = make_fingerprint("node-abc", "disk_critical")
    fp2 = make_fingerprint("node-abc", "cpu_critical")
    assert fp1 != fp2


def test_fingerprint_is_hex_string():
    fp = make_fingerprint("node-abc", "disk_critical")
    assert len(fp) == 64  # sha256 hex = 64 chars
    assert all(c in "0123456789abcdef" for c in fp)
