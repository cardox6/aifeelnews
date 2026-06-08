"""Regression tests for robots.txt compliance edge cases.

The headline case here is the 404 path: a site with NO robots.txt must be
treated as permissive (crawl allowed). A regression once made it the inverse —
a freshly-constructed, never-read RobotFileParser has can_fetch() return False
for every URL, so returning that parser silently DISALLOWED all crawling of any
site without a robots.txt. The fix returns None on 404 so is_url_allowed()
applies its permissive parser-is-None default.
"""

from types import SimpleNamespace

import pytest

from app.utils import robots


@pytest.fixture(autouse=True)
def _clear_robots_cache():
    """Each test starts with an empty robots.txt cache (module-global)."""
    robots._robots_cache.clear()
    yield
    robots._robots_cache.clear()


def _mock_response(status_code: int, text: str = ""):
    """Minimal stand-in for a requests.Response."""

    def raise_for_status():
        if status_code >= 400:
            raise robots.requests.HTTPError(f"{status_code}")

    return SimpleNamespace(
        status_code=status_code, text=text, raise_for_status=raise_for_status
    )


def test_404_robots_is_permissive(monkeypatch):
    """A 404 on robots.txt must ALLOW crawling (no policy = permissive)."""
    monkeypatch.setattr(robots.requests, "get", lambda *a, **k: _mock_response(404))

    allowed, reason = robots.is_url_allowed("https://no-robots.example.com/article")

    assert allowed is True, f"404 robots.txt should allow crawling, got: {reason}"


def test_404_fetch_returns_none(monkeypatch):
    """fetch_robots_txt returns None on 404 so the None-default path is used."""
    monkeypatch.setattr(robots.requests, "get", lambda *a, **k: _mock_response(404))

    assert robots.fetch_robots_txt("no-robots.example.com") is None


def test_network_failure_is_permissive(monkeypatch):
    """A network error fetching robots.txt must ALLOW crawling (fail-open)."""

    def _raise(*a, **k):
        raise robots.requests.RequestException("connection refused")

    monkeypatch.setattr(robots.requests, "get", _raise)

    allowed, _ = robots.is_url_allowed("https://unreachable.example.com/article")

    assert allowed is True


def test_disallow_rule_is_respected(monkeypatch):
    """A real Disallow rule for our path must still BLOCK crawling.

    Mocks at the parser level (not the temp-file file:// read, which is
    platform-fragile on Windows) so the policy-enforcement path is exercised
    deterministically: a populated parser must DENY a disallowed URL.
    """
    from urllib.robotparser import RobotFileParser

    rp = RobotFileParser()
    rp.parse(["User-agent: *", "Disallow: /private/"])
    monkeypatch.setattr(robots, "get_robots_parser", lambda domain: rp)

    allowed, _ = robots.is_url_allowed("https://example.com/private/secret")

    assert allowed is False
