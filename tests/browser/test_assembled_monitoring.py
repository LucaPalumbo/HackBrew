"""Real bridge and actuators while a browser explores a frozen historical interval."""

from contextlib import ExitStack
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.assembled_system import AssembledSystem, FrozenHistory
from tests.browser.navigation import close_raw_readings


@pytest.fixture
def api(empty_api: httpx.Client) -> httpx.Client:
    return empty_api


@pytest.mark.parametrize("width", [1440, 390])
def test_independent_cycles_keep_frozen_history_across_network_reconnections(
    api: httpx.Client, page: Page, tmp_path: Path, width: int
) -> None:
    with ExitStack() as stack:
        system = AssembledSystem(api, tmp_path, stack)
        page.set_viewport_size({"width": width, "height": 1000})
        view = FrozenHistory(page, system, "ipa")
        before = system.snapshot()
        page.context.set_offline(True)
        expect(page.get_by_label("Collegamento live")).to_contain_text("Riconnessione automatica")
        system.proxy.registry_status = 503
        system.proxy.telemetry_status = 503
        system.bridge.wait_message("registry_sync_failed")
        system.feed("ipa", "signed_accelerations", forwarded=False)
        system.assert_snapshot(before)
        view.assert_preserved()
        system.proxy.registry_status = 200
        system.proxy.telemetry_status = 200
        system.bridge.wait_message('"GET /api/bridge/pills HTTP/1.1" 200')
        system.feed("lager", "valid")
        assert system.readings("ipa") == before["readings"]["ipa"]
        assert len(system.readings("lager")) == 2
        page.context.set_offline(False)
        view.reconnect()
        system.feed("ipa", "cold")
        overview = page.context.new_page()
        overview.goto(str(api.base_url))
        expect(
            overview.get_by_role("button", name="Apri IPA integrata", exact=False)
        ).to_contain_text("14,9 °C", timeout=15000)
        view.assert_preserved()
        close_raw_readings(page)
        page.get_by_role("button", name="Torna al live", exact=True).click()
        expect(page.get_by_label("Intervallo visualizzato")).not_to_have_text(view.interval)
