"""CORS settings: CSV origins, regex EC2 / custom (Learner Lab)."""

from __future__ import annotations

import re

from app.core.config import Settings


def test_allowed_origins_csv_parsing():
    s = Settings(ALLOWED_ORIGINS="http://a:1,http://b:2")
    assert s.ALLOWED_ORIGINS == "http://a:1,http://b:2"
    assert s.allowed_origins_list == ["http://a:1", "http://b:2"]


def test_resolved_cors_regex_ec2_only():
    s = Settings(CORS_ALLOW_EC2_COMPUTE_DNS=True)
    r = s.resolved_cors_origin_regex
    assert r is not None
    ok = "http://ec2-1-2-3-4.us-east-1.compute.amazonaws.com:3000"
    bad = "http://evil.com"
    assert re.match(r, ok)
    assert re.match(r, bad) is None


def test_resolved_cors_regex_custom_only():
    s = Settings(CORS_ALLOW_ORIGIN_REGEX=r"^https://\d+\.labs\.example\.org$")
    r = s.resolved_cors_origin_regex
    assert r is not None
    assert re.match(r, "https://12.labs.example.org")


def test_resolved_cors_regex_combined():
    s = Settings(
        CORS_ALLOW_EC2_COMPUTE_DNS=True,
        CORS_ALLOW_ORIGIN_REGEX=r"^https://lab\.local$",
    )
    r = s.resolved_cors_origin_regex
    assert r is not None
    assert "|" in r


def test_resolved_cors_regex_none_when_disabled():
    s = Settings()
    assert s.resolved_cors_origin_regex is None
