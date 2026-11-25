"""Visit the public Streamlit app and verify its initial planning interface."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Browser, BrowserContext, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

WAKE_TIMEOUT_SECONDS = 25 * 60
POLL_INTERVAL_SECONDS = 12
NAVIGATION_TIMEOUT_SECONDS = 30
WAKE_BUTTON = "Yes, get this app back up!"
READY_TAB = "🧭 Geführte Planung"
READY_MESSAGE = "Bitte zuerst eine Planungsdatei hochladen."
DIAGNOSTIC_PATH = Path("wake-diagnostics") / "failure.png"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class WakeError(Exception):
    """A safe, user-facing reason why readiness could not be verified."""


@dataclass
class Result:
    wake_attempted: bool = False


def validate_url(value: str) -> str:
    url = value.strip()
    if not url:
        raise ValueError("STREAMLIT_APP_URL fehlt. Bitte die Repository-Variable setzen.")
    if any(ch.isspace() or ord(ch) < 32 for ch in url) or any(ch in url for ch in '<>"{}'):
        raise ValueError("STREAMLIT_APP_URL enthält ungültige Zeichen oder einen Platzhalter.")
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("STREAMLIT_APP_URL ist keine gültige HTTPS-Adresse.") from exc
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or "." not in hostname
        or hostname.lower() in {"example.com", "example.org", "example.net"}
        or hostname.lower().endswith((".example.com", ".example.org", ".example.net", ".example", ".invalid", ".test"))
        or hostname.lower().startswith(("your-", "placeholder"))
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError("STREAMLIT_APP_URL muss eine echte HTTPS-Adresse ohne Zugangsdaten sein.")
    return url


def _remaining_ms(deadline: float, limit_seconds: float) -> int:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise WakeError("Die maximale Wartezeit für die Browserprüfung wurde überschritten.")
    return max(1, int(min(remaining, limit_seconds) * 1000))


def navigate(page: Page, url: str, deadline: float) -> None:
    for attempt in range(2):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=_remaining_ms(deadline, NAVIGATION_TIMEOUT_SECONDS))
            return
        except PlaywrightTimeoutError:
            logger.warning("Navigation noch nicht abgeschlossen; warte auf den Seiteninhalt.")
            return
        except PlaywrightError as exc:
            if attempt:
                raise WakeError("Navigation auch nach einem erneuten Versuch fehlgeschlagen.") from exc
            logger.warning("Navigation fehlgeschlagen; ein erneuter Versuch folgt.")
            page.wait_for_timeout(_remaining_ms(deadline, POLL_INTERVAL_SECONDS))


def wait_for_ready(page: Page, deadline: float, result: Result) -> None:
    wake_button = page.get_by_role("button", name=WAKE_BUTTON, exact=True)
    ready_tab = page.get_by_role("tab", name=READY_TAB, exact=True)
    ready_message = page.get_by_text(READY_MESSAGE, exact=True)
    exceptions = page.get_by_test_id("stException")
    logger.info("Warte auf die geführte Planung und den Upload-Hinweis.")
    dom_warning_logged = False
    while time.monotonic() < deadline:
        try:
            if exceptions.first.is_visible():
                raise WakeError("Die Streamlit-Oberfläche zeigt einen Anwendungsfehler.")
            if wake_button.is_visible():
                if not result.wake_attempted:
                    logger.info("Schlafseite erkannt; Aufweckknopf wird einmal betätigt.")
                    result.wake_attempted = True
                    try:
                        wake_button.click(timeout=_remaining_ms(deadline, 10))
                    except PlaywrightError as exc:
                        raise WakeError("Der erkannte Aufweckknopf konnte nicht betätigt werden.") from exc
            elif ready_tab.is_visible() and ready_message.is_visible():
                logger.info(
                    "%s App bereit: geführte Planung und Upload-Hinweis sind sichtbar.",
                    "Aufgeweckte" if result.wake_attempted else "Bereits aktive",
                )
                return
        except PlaywrightError:
            if not dom_warning_logged:
                logger.warning("Seitenwechsel während der Prüfung; warte auf stabilen Inhalt.")
                dom_warning_logged = True
        page.wait_for_timeout(_remaining_ms(deadline, POLL_INTERVAL_SECONDS))
    if result.wake_attempted:
        raise WakeError("Nach dem Aufweckversuch erschien das Bereitschaftsmerkmal nicht rechtzeitig.")
    raise WakeError("Weder die bereite App noch ein verwendbarer Aufweckknopf erschien rechtzeitig.")


def save_diagnostic(page: Page) -> None:
    try:
        DIAGNOSTIC_PATH.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(DIAGNOSTIC_PATH), timeout=5000)
        logger.info("Fehlerbild gespeichert: %s", DIAGNOSTIC_PATH)
    except (OSError, PlaywrightError) as exc:
        logger.warning("Fehlerbild konnte nicht erstellt werden (%s).", type(exc).__name__)


def run_browser(url: str, result: Result) -> None:
    deadline = time.monotonic() + WAKE_TIMEOUT_SECONDS
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, timeout=_remaining_ms(deadline, 30))
        try:
            context = browser.new_context()
            try:
                page = context.new_page()
                try:
                    logger.info("Browserbesuch beginnt.")
                    navigate(page, url, deadline)
                    wait_for_ready(page, deadline, result)
                except (WakeError, PlaywrightError):
                    save_diagnostic(page)
                    raise
            finally:
                close_browser_resource(context, sys.exc_info()[0] is not None)
        finally:
            close_browser_resource(browser, sys.exc_info()[0] is not None)


def close_browser_resource(resource: Browser | BrowserContext, preserve_error: bool) -> None:
    try:
        resource.close()
    except PlaywrightError:
        if not preserve_error:
            raise
        logger.warning("Browserressource konnte nach einem Fehler nicht geschlossen werden.")


def write_summary(success: bool, result: Result, elapsed: float, reason: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as summary:
            summary.write(
                f"## Streamlit-Bereitschaft\n\n"
                f"- Ergebnis: {'Erfolg' if success else 'Fehlgeschlagen'}\n"
                f"- Dauer: {elapsed:.1f} Sekunden\n"
                f"- Aufweckversuch: {'ja' if result.wake_attempted else 'nein'}\n"
                f"- Hinweis: {reason}\n"
            )
    except OSError as exc:
        logger.warning("Job-Zusammenfassung konnte nicht geschrieben werden (%s).", type(exc).__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-config", action="store_true", help="Nur die App-URL prüfen.")
    args = parser.parse_args(argv)
    start = time.monotonic()
    result = Result()
    success = False
    reason = "Konfiguration gültig."
    logger.info("Start (UTC): %s", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    try:
        url = validate_url(os.environ.get("STREAMLIT_APP_URL", ""))
        if not args.check_config:
            run_browser(url, result)
            reason = "Geführte Planung und Upload-Hinweis sichtbar."
        success = True
        logger.info("%s", reason)
    except (ValueError, WakeError) as exc:
        reason = str(exc)
        logger.error("Fehlgeschlagen: %s", reason)
    except (PlaywrightError, OSError) as exc:
        reason = f"Browser- oder Dateifehler ({type(exc).__name__}); Runner- und Browserinstallation prüfen."
        logger.error("Fehlgeschlagen: %s", reason)
    elapsed = time.monotonic() - start
    logger.info("Dauer: %.1f Sekunden; Aufweckversuch: %s.", elapsed, "ja" if result.wake_attempted else "nein")
    if not args.check_config or not success:
        write_summary(success, result, elapsed, reason)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
