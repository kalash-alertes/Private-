"""Vérifie le thème commun, les contrastes et les pages responsives sur données synthétiques, sans réseau réel."""

import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from backend.features.incidents import service as incidents_service
from backend.features.incidents.schemas import IncidentCreationRequest
from backend.features.playbooks import service as playbooks_service
from tests.synthetic_data import build_synthetic_playbook_request, store_synthetic_source_log

playwright_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def theme_browser():
    """Ouvre Chromium ou le canal installé demandé ; ignore les tests si Chromium n'est pas disponible."""
    with playwright_api.sync_playwright() as playwright:
        channel = os.environ.get("PLAYWRIGHT_BROWSER_CHANNEL")
        if not channel and not Path(playwright.chromium.executable_path).exists():
            pytest.skip("Chromium Playwright non installé")
        browser = playwright.chromium.launch(channel=channel)
        yield browser
        browser.close()


@pytest.mark.parametrize("width", [1440, 390, 320])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_common_theme_keeps_pages_readable_and_controls_accessible(
    theme_browser, web_client, database_session, width, theme,
) -> None:
    storage = store_synthetic_source_log(database_session)
    incident = incidents_service.create_incident_from_source_log(
        database_session, IncidentCreationRequest(log_id=storage.source_log_id)
    )
    playbook = playbooks_service.create_playbook(database_session, build_synthetic_playbook_request())
    database_session.rollback()
    paths = [
        "/", "/alertes", f"/alertes/{storage.source_log_id}", "/incidents", f"/incidents/{incident.id}",
        "/logs-bruts", "/journaux", "/parametres/reponse-incidents", "/parametres/playbooks",
        "/parametres/playbooks/nouveau", f"/parametres/playbooks/{playbook.id}/modifier",
        "/parametres/journal-audit", "/parametres/clients", "/parametres/utilisateurs", "/page-inconnue",
    ]
    page = theme_browser.new_page(viewport={"width": width, "height": 900}, reduced_motion="reduce")
    page.add_init_script(f"localStorage.setItem('fAnalyzerInterfaceTheme', '{theme}');")

    def serve_test_response(route):
        address = urlsplit(route.request.url)
        if address.netloc != "theme.test":
            route.abort()
            return
        response = web_client.get(address.path + (f"?{address.query}" if address.query else ""))
        route.fulfill(status=response.status_code, content_type=response.headers["content-type"], body=response.content)

    page.route("**/*", serve_test_response)
    try:
        for path in paths:
            response = page.goto(f"http://theme.test{path}")
            assert response.status == (404 if path == "/page-inconnue" else 200), path
            measurements = page.evaluate("""() => {
              const sample = selector => {
                const element = document.querySelector(selector);
                return element ? getComputedStyle(element) : null;
              };
              return {
                overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                bodyFont: parseFloat(sample('body').fontSize),
                textFont: parseFloat(sample('.page-heading p, .error-card p').fontSize),
                photoBackground: sample('body').backgroundImage,
                glass: sample('.panel, .error-card, .playbook-card, .playbook-form').backdropFilter,
                buttons: [...document.querySelectorAll('.button')].filter(element => element.getClientRects().length)
                  .map(element => ({height: element.getBoundingClientRect().height,
                    font: parseFloat(getComputedStyle(element).fontSize)})),
                primary: sample('.button-primary') ? {
                  text: sample('.button-primary').color, background: sample('.button-primary').backgroundColor
                } : null
              };
            }""")
            assert measurements["overflow"] <= 1, (width, path, measurements)
            assert measurements["bodyFont"] >= 15 and measurements["textFont"] >= 15, path
            assert '/static/images/application_background.jpg' in measurements["photoBackground"], path
            assert measurements["glass"] == "blur(18px)", path
            assert page.locator("html").get_attribute("data-theme") == theme
            assert all(button["height"] >= 36 and button["font"] >= 13 for button in measurements["buttons"]), path
            if measurements["primary"]:
                assert contrast_ratio(
                    measurements["primary"]["text"], measurements["primary"]["background"]
                ) >= 4.5, path
            if path == "/":
                icon_contrasts = page.locator(".stat-icon").evaluate_all("""elements => elements.map(element => ({
                  text: getComputedStyle(element.querySelector('svg')).color,
                  background: getComputedStyle(element).backgroundColor
                }))""")
                assert all(contrast_ratio(icon["text"], icon["background"]) >= 3 for icon in icon_contrasts)
            if path == "/" and width <= 390:
                assert page.locator(".global-search").is_visible()
                page.locator(".mobile-menu").click()
                assert page.locator("#sidebar-toggle").is_checked()
                page.locator('.sidebar .nav-item[href="/alertes"]').click()
                assert page.url == "http://theme.test/alertes"
    finally:
        page.close()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_background_is_a_real_local_jpeg_and_glass_text_has_contrast(theme_browser, web_client, theme) -> None:
    response = web_client.get("/static/images/application_background.jpg")
    assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
    assert response.content.startswith(b"\xff\xd8\xff")
    page = theme_browser.new_page()
    page.add_init_script(f"localStorage.setItem('fAnalyzerInterfaceTheme', '{theme}');")

    def serve_local_file(route):
        address = urlsplit(route.request.url)
        if address.netloc != "theme.test":
            route.abort()
            return
        result = web_client.get(address.path)
        route.fulfill(status=result.status_code, content_type=result.headers["content-type"], body=result.content)

    page.route("**/*", serve_local_file)
    try:
        page.goto("http://theme.test/")
        dimensions = page.evaluate("""async () => {
          const image = new Image();
          image.src = '/static/images/application_background.jpg';
          await image.decode();
          return {width: image.naturalWidth, height: image.naturalHeight};
        }""")
        assert dimensions["width"] >= 1440 and dimensions["height"] >= 900
        surfaces = page.evaluate("""() => {
          return ['.stat-card', '.sidebar', '.topbar', '.page-heading', '.page-footer'].map(selector => {
            const style = getComputedStyle(document.querySelector(selector));
            return {text: style.color, surface: style.backgroundColor};
          });
        }""")
        for surface in surfaces:
            assert surface["surface"].startswith("rgba(")
            channels = surface["surface"].removeprefix("rgba(").removesuffix(")").split(",")
            alpha = float(channels[3])
            assert .75 <= alpha < 1
            for image_channel in (0, 255):
                composed_background = "rgb(" + ", ".join(
                    str(round(float(channel) * alpha + image_channel * (1 - alpha))) for channel in channels[:3]
                ) + ")"
                assert contrast_ratio(surface["text"], composed_background) >= 4.5
        sidebar_styles = page.evaluate("""() => {
          const sidebar = getComputedStyle(document.querySelector('.sidebar'));
          const active = getComputedStyle(document.querySelector('.sidebar .nav-item.active'));
          return {image: sidebar.backgroundImage, activeText: active.color, activeBackground: active.backgroundColor};
        }""")
        assert "/static/images/application_background.jpg" in sidebar_styles["image"]
        assert contrast_ratio(sidebar_styles["activeText"], sidebar_styles["activeBackground"]) >= 4.5
        border = page.locator(".sidebar").evaluate("(element) => getComputedStyle(element).borderRightColor")
        assert border.startswith("rgba(")
        widths = page.locator(".sidebar").evaluate("""element => {
          const style = getComputedStyle(element);
          return [style.borderTopWidth, style.borderRightWidth, style.borderBottomWidth, style.borderLeftWidth];
        }""")
        assert widths == ["4px"] * 4
    finally:
        page.close()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_opaque_fallback_remains_readable_without_photo_or_blur_support(theme_browser, web_client, theme) -> None:
    page = theme_browser.new_page()
    page.add_init_script(f"localStorage.setItem('fAnalyzerInterfaceTheme', '{theme}');")

    def serve_without_glass_support(route):
        address = urlsplit(route.request.url)
        if address.netloc != "theme.test" or address.path.endswith(".jpg"):
            route.abort()
            return
        response = web_client.get(address.path)
        body = response.content
        if address.path.endswith(("pink_theme.css", "dark_theme.css")):
            body = response.text.replace(
                "((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))",
                "(unsupported-glass-filter: unavailable)",
            ).encode("utf-8")
        route.fulfill(status=response.status_code, content_type=response.headers["content-type"], body=body)

    page.route("**/*", serve_without_glass_support)
    try:
        page.goto("http://theme.test/")
        background = page.locator(".stat-card").first.evaluate("(element) => getComputedStyle(element).backgroundColor")
        assert background == ("rgb(24, 40, 32)" if theme == "dark" else "rgb(252, 253, 250)")
        sidebar = page.locator(".sidebar").evaluate("""element => {
          const style = getComputedStyle(element);
          return {background: style.backgroundColor, color: style.color};
        }""")
        assert contrast_ratio(sidebar["color"], sidebar["background"]) >= 4.5
        assert page.locator('a[href="/alertes"]').count() > 0
        assert page.locator(".heading-actions").is_visible()
    finally:
        page.close()


def contrast_ratio(text_color: str, background_color: str) -> float:
    """Calcule le contraste WCAG de deux couleurs CSS rgb opaques."""
    def luminance(css_color: str) -> float:
        channels = [int(channel.strip()) / 255 for channel in css_color.removeprefix("rgb(").removesuffix(")").split(",")]
        linear_channels = [channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4 for channel in channels]
        return sum(channel * weight for channel, weight in zip(linear_channels, [.2126, .7152, .0722]))

    first, second = sorted((luminance(text_color), luminance(background_color)))
    return (second + .05) / (first + .05)


def test_theme_toggle_persists_across_pages_and_works_without_storage(theme_browser, web_client) -> None:
    page = theme_browser.new_page()

    def serve_theme_page(route):
        address = urlsplit(route.request.url)
        if address.netloc != "theme.test":
            route.abort()
            return
        response = web_client.get(address.path)
        route.fulfill(status=response.status_code, content_type=response.headers["content-type"], body=response.content)

    page.route("**/*", serve_theme_page)
    try:
        page.goto("http://theme.test/")
        toggle = page.get_by_role("button", name="Activer le mode sombre")
        toggle.focus()
        page.keyboard.press("Enter")
        assert page.locator("html").get_attribute("data-theme") == "dark"
        assert page.get_by_role("button", name="Activer le mode clair").get_attribute("aria-pressed") == "true"
        page.goto("http://theme.test/alertes")
        assert page.locator("html").get_attribute("data-theme") == "dark"
        page.reload()
        assert page.locator("html").get_attribute("data-theme") == "dark"
        page.goto("http://theme.test/page-inconnue")
        page.get_by_role("button", name="Activer le mode clair").click()
        assert page.locator("html").get_attribute("data-theme") == "light"
        assert page.evaluate("localStorage.getItem('fAnalyzerInterfaceTheme')") == "light"
        page.evaluate("""() => {
          Storage.prototype.setItem = () => { throw new Error('Stockage bloqué pour le test'); };
        }""")
        page.get_by_role("button", name="Activer le mode sombre").click()
        assert page.locator("html").get_attribute("data-theme") == "dark"
        assert "non mémorisé" in page.locator("#application-theme-toggle").get_attribute("title")
    finally:
        page.close()


def test_theme_button_is_hidden_without_javascript(theme_browser, web_client) -> None:
    page = theme_browser.new_page(java_script_enabled=False)
    page.route("**/*", lambda route: route.fulfill(
        content_type="text/html", body=web_client.get("/").text,
    ) if route.request.url == "http://theme.test/" else route.abort())
    try:
        page.goto("http://theme.test/")
        assert page.locator("#application-theme-toggle").is_hidden()
        assert page.locator(".page-heading h1").is_visible()
    finally:
        page.close()
