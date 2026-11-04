"""One real bridge observes registrations made from the running web interface."""

from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.bridge_process import BridgeProcess, advertisement_fixture


@pytest.fixture
def api(empty_api: httpx.Client) -> httpx.Client:
    return empty_api


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_web_registration_adds_sources_to_the_running_real_bridge(
    page: Page, api: httpx.Client, tmp_path: Path, width: int, height: int
) -> None:
    bridge = BridgeProcess(tmp_path, str(api.base_url).rstrip("/"))
    try:
        bridge.wait_message("pills=0")
        page.set_viewport_size({"width": width, "height": height})
        page.goto(str(api.base_url) + "?page=devices")
        for name, mac, fixture in (
            ("Pillola IPA", "aa-bb-cc-dd-ee-ff", "valid"),
            ("Pillola Stout", "112233445566", "invalid_velocity"),
        ):
            page.get_by_label("Nome della pillola", exact=True).fill(name)
            page.get_by_label("MAC Bluetooth", exact=True).fill(mac)
            page.get_by_role("button", name="Registra pillola", exact=True).click()
            card = page.get_by_role("region", name=f"Pillola {name}", exact=True)
            expect(card).to_contain_text("Nessuna lettura ricevuta")
            revision = api.get("/api/bridge/pills").json()["revision"]
            bridge.wait_message(f"registry_synced revision={revision}")
            bridge.advertise(mac, advertisement_fixture(fixture))
            bridge.wait_message("reading_forwarded")
            expect(card).to_contain_text("1.021" if fixture == "valid" else "1.011")
        first = page.get_by_role("region", name="Pillola Pillola IPA", exact=True)
        second = page.get_by_role("region", name="Pillola Pillola Stout", exact=True)
        expect(first).to_contain_text("19,685938")
        expect(first).to_contain_text("-14,821796")
        expect(second).to_contain_text("23,935938")
        expect(second).to_contain_text("misura non valida")
        page.reload()
        expect(first).to_contain_text("1.021")
        expect(second).to_contain_text("1.011")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    finally:
        bridge.stop()
