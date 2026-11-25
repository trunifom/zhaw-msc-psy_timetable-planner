"""Focused tests for the wake workflow; no published app is contacted."""

from unittest.mock import MagicMock

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from scripts import wake_streamlit as wake


class FakeLocator:
    def __init__(self, visible=False):
        self.visible = visible
        self.clicks = 0
        self.first = self

    def is_visible(self):
        return self.visible

    def click(self, **_kwargs):
        self.clicks += 1


class FakePage:
    def __init__(self):
        self.button = FakeLocator()
        self.tab = FakeLocator()
        self.message = FakeLocator()
        self.exception = FakeLocator()
        self.elapsed = 0.0
        self.on_wait = lambda: None
        self.navigation_errors = []
        self.navigations = 0

    def get_by_role(self, role, **_kwargs):
        return self.button if role == "button" else self.tab

    def get_by_text(self, *_args, **_kwargs):
        return self.message

    def get_by_test_id(self, *_args, **_kwargs):
        return self.exception

    def wait_for_timeout(self, ms):
        self.elapsed += ms / 1000
        self.on_wait()

    def goto(self, *_args, **_kwargs):
        self.navigations += 1
        if self.navigation_errors:
            raise self.navigation_errors.pop(0)


@pytest.mark.parametrize(
    "url",
    ["", "http://app.streamlit.app", "https://<APP_URL>", "https://example.com",
     "https://your-streamlit-app.streamlit.app", "https://user:pass@app.streamlit.app",
     "https://app.streamlit.app:99999", "https://bad host"],
)
def test_invalid_urls(url):
    with pytest.raises(ValueError):
        wake.validate_url(url)


def test_valid_url_preserves_query_without_logging_it():
    url = "https://app.streamlit.app/?language=de"
    assert wake.validate_url(f" {url} ") == url


def test_already_ready_does_not_click(monkeypatch):
    page = FakePage()
    page.tab.visible = page.message.visible = True
    result = wake.Result()
    monkeypatch.setattr(wake.time, "monotonic", lambda: page.elapsed)
    wake.wait_for_ready(page, 30, result)
    assert not result.wake_attempted
    assert page.button.clicks == 0


def test_sleep_page_is_clicked_once_then_app_becomes_ready(monkeypatch):
    page = FakePage()
    page.button.visible = True
    result = wake.Result()
    monkeypatch.setattr(wake.time, "monotonic", lambda: page.elapsed)

    def become_ready():
        if page.elapsed >= 24:
            page.button.visible = False
            page.tab.visible = page.message.visible = True

    page.on_wait = become_ready
    wake.wait_for_ready(page, 40, result)
    assert result.wake_attempted
    assert page.button.clicks == 1


@pytest.mark.parametrize("sleeping", [False, True])
def test_unready_page_times_out_without_repeated_clicks(monkeypatch, sleeping):
    page = FakePage()
    page.button.visible = sleeping
    monkeypatch.setattr(wake.time, "monotonic", lambda: page.elapsed)
    with pytest.raises(wake.WakeError, match="rechtzeitig"):
        wake.wait_for_ready(page, 25, wake.Result())
    assert page.elapsed == 25
    assert page.button.clicks == int(sleeping)


def test_streamlit_exception_is_not_success(monkeypatch):
    page = FakePage()
    page.tab.visible = page.message.visible = page.exception.visible = True
    monkeypatch.setattr(wake.time, "monotonic", lambda: page.elapsed)
    with pytest.raises(wake.WakeError, match="Anwendungsfehler"):
        wake.wait_for_ready(page, 30, wake.Result())


def test_upload_hint_without_tab_is_not_ready(monkeypatch):
    page = FakePage()
    page.message.visible = True
    monkeypatch.setattr(wake.time, "monotonic", lambda: page.elapsed)
    with pytest.raises(wake.WakeError, match="rechtzeitig"):
        wake.wait_for_ready(page, 25, wake.Result())


def test_navigation_retries_once_but_timeout_does_not_reload(monkeypatch):
    page = FakePage()
    monkeypatch.setattr(wake.time, "monotonic", lambda: page.elapsed)
    page.navigation_errors = [PlaywrightError("transient")]
    wake.navigate(page, "https://app.streamlit.app", 60)
    assert page.navigations == 2
    page.navigations = 0
    page.navigation_errors = [PlaywrightTimeoutError("slow")]
    wake.navigate(page, "https://app.streamlit.app", 60)
    assert page.navigations == 1


def test_navigation_failure_is_bounded(monkeypatch):
    page = FakePage()
    page.navigation_errors = [PlaywrightError("first"), PlaywrightError("second")]
    monkeypatch.setattr(wake.time, "monotonic", lambda: page.elapsed)
    with pytest.raises(wake.WakeError, match="erneuten Versuch"):
        wake.navigate(page, "https://app.streamlit.app", 60)
    assert page.navigations == 2


def test_main_returns_success_and_failure_without_leaking_url(monkeypatch, caplog):
    monkeypatch.setenv("STREAMLIT_APP_URL", "https://app.streamlit.app/?token=private")
    monkeypatch.setattr(wake, "run_browser", lambda _url, _result: None)
    assert wake.main([]) == 0
    assert "private" not in caplog.text
    monkeypatch.delenv("STREAMLIT_APP_URL")
    assert wake.main([]) == 1


def test_browser_resources_close_on_failure(monkeypatch):
    playwright = MagicMock()
    browser = playwright.chromium.launch.return_value
    context = browser.new_context.return_value
    manager = MagicMock()
    manager.__enter__.return_value = playwright
    monkeypatch.setattr(wake, "sync_playwright", lambda: manager)
    monkeypatch.setattr(wake, "save_diagnostic", lambda _page: None)

    def fail(_page, _url, _deadline):
        raise wake.WakeError("navigation failed")

    monkeypatch.setattr(wake, "navigate", fail)
    with pytest.raises(wake.WakeError, match="navigation failed"):
        wake.run_browser("https://app.streamlit.app", wake.Result())
    context.close.assert_called_once()
    browser.close.assert_called_once()
