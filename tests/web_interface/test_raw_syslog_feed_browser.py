"""Régressions du défilement et de la pause, avec logs synthétiques et HTTP simulé.

Nécessite Playwright et son Chromium ; ignoré s'ils ne sont pas installés.
"""

import os
from pathlib import Path

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_entries(first_number: int, count: int) -> str:
    """Retourne des lignes synthétiques de hauteur fixe, dans l'ordre décroissant."""
    return "".join(
        f'<details data-number="{number}"><summary>Log synthétique {number}</summary>'
        '<div style="height:300px">Champs synthétiques</div></details>'
        for number in range(first_number, first_number - count, -1)
    )


def build_update(last_number: int) -> str:
    """Retourne un fragment synthétique, compatible avec le rafraîchissement réel."""
    return (
        f'<div data-last-number="{last_number}"></div>'
        f'<template data-role="entries">{build_entries(last_number, 20)}</template>'
        '<template data-role="statistics"><p>Bilan synthétique</p></template>'
    )


@pytest.fixture
def raw_feed_browser_page():
    """Charge les vrais CSS/JS dans Chromium ; toutes les requêtes sont simulées."""
    with playwright_api.sync_playwright() as playwright:
        browser_channel = os.environ.get("PLAYWRIGHT_BROWSER_CHANNEL")
        if not browser_channel and not Path(playwright.chromium.executable_path).exists():
            pytest.skip("Chromium Playwright non installé")
        browser = playwright.chromium.launch(channel=browser_channel)
        page = browser.new_page(viewport={"width": 1000, "height": 800})
        next_number = 500

        def fulfill_request(route):
            nonlocal next_number
            if route.request.url.startswith("http://raw-feed.test/nouveaux?"):
                assert route.request.url == f"http://raw-feed.test/nouveaux?apres={next_number}"
                next_number += 20
                route.fulfill(content_type="text/html", body=build_update(next_number))
            elif route.request.url == "http://raw-feed.test/":
                route.fulfill(content_type="text/html", body=(
                    '<style>summary {height:30px;} body {margin:0;}</style>'
                    '<div id="raw-feed-statistics"><p>Bilan synthétique</p></div>'
                    '<span id="raw-feed-live-state"><span></span>En direct</span>'
                    '<button id="raw-feed-pause-button">Pause</button>'
                    '<p id="raw-feed-empty" hidden>Aucun log</p>'
                    '<div class="raw-feed-entries" id="raw-feed-entries" data-last-number="500" '
                    'data-update-url="/nouveaux">' + build_entries(500, 500) + '</div>'
                ))
            else:
                route.abort()

        page.route("**/*", fulfill_request)
        page.goto("http://raw-feed.test/")
        page.add_style_tag(path=str(PROJECT_ROOT / "web_interface" / "static" / "css" / "foundation.css"))
        page.add_style_tag(path=str(PROJECT_ROOT / "web_interface" / "static" / "css" / "raw_syslog_feed.css"))
        page.add_style_tag(path=str(PROJECT_ROOT / "web_interface" / "static" / "css" / "pink_theme.css"))
        page.clock.install()
        page.add_script_tag(path=str(PROJECT_ROOT / "web_interface" / "static" / "js" / "raw_syslog_feed.js"))
        yield page
        browser.close()


@pytest.mark.parametrize("entry_index, is_open", [(10, True), (490, True), (490, False)])
def test_refresh_preserves_visible_log_within_one_pixel(raw_feed_browser_page, entry_index, is_open) -> None:
    page = raw_feed_browser_page
    before = page.evaluate("""({entryIndex, isOpen}) => {
      const container = document.getElementById('raw-feed-entries');
      const entry = container.children[entryIndex];
      entry.open = isOpen;
      container.scrollTop = entry.offsetTop - container.offsetTop + 10;
      return {number: entry.dataset.number, top: entry.getBoundingClientRect().top};
    }""", {"entryIndex": entry_index, "isOpen": is_open})

    for expected_number in (520, 540):
        page.clock.fast_forward(3000)
        page.wait_for_selector(f'details[data-number="{expected_number}"]', state="attached")
        after = page.locator(f'details[data-number="{before["number"]}"]').evaluate(
            "(entry) => ({top: entry.getBoundingClientRect().top, open: entry.open})"
        )
        assert abs(after["top"] - before["top"]) <= 1
        assert after["open"] == is_open
        assert page.locator("#raw-feed-entries > details").count() == 500


def test_refresh_at_top_shows_newest_log(raw_feed_browser_page) -> None:
    page = raw_feed_browser_page
    page.clock.fast_forward(3000)
    page.wait_for_selector('details[data-number="520"]', state="attached")

    assert page.locator("#raw-feed-entries > details").first.get_attribute("data-number") == "520"
    assert page.locator("#raw-feed-entries").evaluate("(container) => container.scrollTop") == 0


def test_pause_discards_inflight_response_without_advancing_cursor(raw_feed_browser_page) -> None:
    page = raw_feed_browser_page
    page.evaluate("() => { window.fetch = () => new Promise(resolve => { window.resolveFeedUpdate = resolve; }); }")
    page.clock.fast_forward(3000)
    page.locator("#raw-feed-pause-button").click()
    page.evaluate("(body) => window.resolveFeedUpdate(new Response(body))", build_update(520))
    page.wait_for_function("() => document.getElementById('raw-feed-live-state').textContent === 'En pause'")
    assert page.locator('details[data-number="520"]').count() == 0
    page.evaluate("""() => {
      window.fetch = async (url) => {
        window.resumedFeedUrl = String(url);
        return new Response('<div data-last-number="500"></div><template data-role="entries"></template>'
          + '<template data-role="statistics"></template>');
      };
    }""")
    page.locator("#raw-feed-pause-button").click()
    page.wait_for_function("() => window.resumedFeedUrl !== undefined")
    assert page.evaluate("() => window.resumedFeedUrl") == "http://raw-feed.test/nouveaux?apres=500"
