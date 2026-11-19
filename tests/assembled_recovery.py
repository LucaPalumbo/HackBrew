"""Keep the assembled system and frozen browser views alive through real service failures."""

import os
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
from playwright.sync_api import Browser, Page, expect

from tests.assembled_system import AssembledSystem, FrozenHistory
from tests.browser.navigation import finish_fermentation, show_management
from tests.database import reset_test_database
from tests.heating import wait_regulation
from tests.heating_recovery import wait_device
from tests.settings import wait_for_sync


def evidence(view: FrozenHistory, stage: str) -> None:
    if directory := os.environ.get("HACKBREW_SCREENSHOT_DIR"):
        viewport = view.page.viewport_size
        assert viewport is not None
        width = viewport["width"]
        view.page.screenshot(
            path=Path(directory) / f"ripresa-integrata-{stage}-{width}.png", full_page=True
        )


def verify_assembled_recovery(
    api: httpx.Client, browser: Browser, phase: Callable[[str, str, Page], None]
) -> None:
    reset_test_database()
    with ExitStack() as stack:
        directory = stack.enter_context(TemporaryDirectory())
        system = AssembledSystem(api, Path(directory), stack)
        desktop = browser.new_page(locale="it-IT", viewport={"width": 1440, "height": 1000})
        mobile = browser.new_page(
            locale="it-IT", viewport={"width": 390, "height": 844}, has_touch=True
        )
        stack.callback(desktop.close)
        stack.callback(mobile.close)
        ipa = FrozenHistory(desktop, system, "ipa")
        lager = FrozenHistory(mobile, system, "lager")
        for view in (ipa, lager):
            evidence(view, "prima")

        # The new minimum is below the current temperature: only retained hysteresis
        # keeps heating active. A fresh idle decision would instead be OFF.
        settings_path = f"/api/fermentations/{system.cycles['ipa']['id']}/thermal-settings"
        api.patch(
            settings_path,
            json={
                "expected_revision": 0,
                "temperature_min": 19,
                "temperature_max": 23,
                "hysteresis": 1,
            },
        ).raise_for_status()
        wait_regulation(api, system.cycles["ipa"], "heating")
        system.confirm_timeout(system.timeout["revision"])
        saved = system.snapshot()
        old_commands = {
            key: simulator.get("/api/v1/state").json()["accepted_command"]
            for key, simulator in system.simulators.items()
        }
        phase("assembled-restart-hysteresis", "assembled-hysteresis-up", desktop)
        system.assert_snapshot(saved)
        wait_regulation(api, system.cycles["ipa"], "heating")
        wait_regulation(api, system.cycles["lager"], "cooling")
        for key in ("heating", "both"):
            previous_sequence = int(old_commands[key]["sequence"])

            def advanced(state: dict[str, Any], previous: int = previous_sequence) -> bool:
                return int(state["accepted_command"]["sequence"]) > previous

            state = wait_device(system.simulators[key], advanced)
            assert state["actual_mode"] == ("heating" if key == "heating" else "cooling")
        assert system.simulators["cooling"].get("/api/v1/state").json()["actual_mode"] == "off"
        for view in (ipa, lager):
            view.reconnect()

        # With persisted ON and fresh data, restart while the physical state is
        # unknown. Observe the wire: even a transient blind ON must fail the test.
        phase("assembled-stop-reconciliation", "assembled-reconciliation-down", desktop)
        heater = system.simulators["heating"]
        heater.patch("/__simulation", json={"confirmation_available": False}).raise_for_status()
        marker = len(system.heater_commands)
        phase("assembled-start-reconciliation", "assembled-reconciliation-up", desktop)
        wait_regulation(api, system.cycles["ipa"], "suspended")
        assert system.heater_commands[marker:]
        assert all(command["mode"] == "off" for command in system.heater_commands[marker:])
        assert system.simulators["cooling"].get("/api/v1/state").json()["actual_mode"] == "off"
        wait_regulation(api, system.cycles["lager"], "cooling")
        system.assert_snapshot(saved)
        heater.patch("/__simulation", json={"confirmation_available": True}).raise_for_status()
        wait_regulation(api, system.cycles["ipa"], "idle")
        system.feed("ipa", "cold")
        system.feed("ipa", "valid")
        wait_regulation(api, system.cycles["ipa"], "heating")
        saved = system.snapshot()

        # Browser and bridge links fail independently of the application services.
        desktop.context.set_offline(True)
        expect(desktop.get_by_label("Collegamento live")).to_contain_text(
            "Riconnessione automatica"
        )
        system.proxy.registry_status = 503
        system.proxy.telemetry_status = 503
        system.bridge.wait_message("registry_sync_failed")
        system.feed("ipa", "signed_accelerations", forwarded=False)
        system.assert_snapshot(saved)
        ipa.assert_preserved()
        system.proxy.registry_status = 200
        system.proxy.telemetry_status = 200
        system.bridge.wait_message('"GET /api/bridge/pills HTTP/1.1" 200')
        desktop.context.set_offline(False)
        ipa.reconnect()

        # Database outage: real HTTP requests fail, last-contact times stay intact,
        # and independent actuator watchdogs remove power without a database.
        timeout = system.set_timeout(8)
        system.confirm_timeout(timeout["revision"])
        system.feed("ipa", "cold")
        system.feed("lager", "valid")
        system.feed("lager", "invalid_velocity")
        wait_regulation(api, system.cycles["ipa"], "heating")
        wait_regulation(api, system.cycles["lager"], "cooling")
        saved = system.snapshot()
        phase("assembled-stop-mongo", "assembled-mongo-down", desktop)
        system.feed("ipa", "signed_accelerations", forwarded=False)
        for method, path, body in (
            (
                "PATCH",
                settings_path,
                {
                    "expected_revision": 1,
                    "temperature_min": 17,
                    "temperature_max": 25,
                    "hysteresis": 1,
                },
            ),
            ("PATCH", "/api/settings", {"communication_timeout_seconds": 77}),
            ("POST", f"/api/fermentations/{system.cycles['ipa']['id']}/end", None),
        ):
            response = api.request(method, path, json=body)
            assert response.status_code == 503, response.text
        for simulator in system.simulators.values():
            wait_device(simulator, lambda state: state["actual_mode"] == "off")
        for view in (ipa, lager):
            expect(view.page.get_by_label("Collegamento live")).to_contain_text(
                "Riconnessione automatica", timeout=15000
            )
            view.assert_preserved()
            evidence(view, "guasto")
        phase("assembled-start-mongo", "assembled-mongo-up", desktop)
        system.assert_snapshot(saved)
        assert api.get("/api/settings").json()["revision"] == timeout["revision"]
        assert api.get("/api/settings").json()["communication_timeout_seconds"] == 8
        for key in ("ipa", "lager"):
            wait_regulation(api, system.cycles[key], "suspended")
            assert system.cycle(key)["status"] == "active"
        # Successful registry sync alone must not refresh telemetry contact times.
        system.bridge.wait_message('"GET /api/bridge/pills HTTP/1.1" 200')
        system.assert_snapshot(saved)
        system.feed("ipa", "valid")
        wait_regulation(api, system.cycles["ipa"], "idle")
        system.feed("ipa", "cold")
        system.feed("lager", "valid")
        system.feed("lager", "invalid_velocity")
        wait_regulation(api, system.cycles["ipa"], "heating")
        wait_regulation(api, system.cycles["lager"], "cooling")
        assert abs(system.readings("ipa")[-1]["temperature"] - 14.85) < 1e-10

        # Persist a terminal conclusion while its physical confirmation is missing.
        combined = system.simulators["both"]
        old_on = combined.get("/api/v1/state").json()["accepted_command"]
        combined.patch("/__simulation", json={"confirmation_available": False}).raise_for_status()
        wait_regulation(api, system.cycles["lager"], "suspended")
        end_path = f"/api/fermentations/{system.cycles['lager']['id']}/end"
        ended_response = api.post(end_path)
        ended_response.raise_for_status()
        ended = ended_response.json()["fermentation"]
        assert ended["thermal_reserved"] is True
        candidate = {
            "name": "Riuso ancora vietato",
            "pill_id": system.pills["spare"]["id"],
            "control_mode": "combined",
            "combined_id": system.devices["both"]["id"],
            "temperature_min": 18,
            "temperature_max": 23,
            "hysteresis": 1,
        }
        assert api.post("/api/fermentations", json=candidate).status_code == 409
        timeout = system.set_timeout(12)
        for key in ("heating", "cooling"):
            wait_for_sync(api, system.devices[key]["id"], revision=timeout["revision"])
        pending = wait_for_sync(api, system.devices["both"]["id"], "pending")
        assert pending["desired_revision"] == timeout["revision"]
        assert pending["applied_revision"] < timeout["revision"]
        # Refresh just before the external coordinator kills the actual app process.
        system.feed("ipa", "valid")
        system.feed("ipa", "cold")
        wait_regulation(api, system.cycles["ipa"], "heating")
        saved = system.snapshot()
        phase("assembled-stop-server", "assembled-server-down", desktop)
        assert system.simulators["heating"].get("/api/v1/state").json()["actual_mode"] == "heating"
        expired = wait_device(
            system.simulators["heating"],
            lambda state: (
                state["actual_mode"] == "off" and state["application_status"] == "timed_out"
            ),
        )
        assert expired["accepted_command"]["mode"] == "heating"
        assert system.simulators["cooling"].get("/api/v1/state").json()["actual_mode"] == "off"
        for view in (ipa, lager):
            expect(view.page.get_by_label("Collegamento live")).to_contain_text(
                "Riconnessione automatica", timeout=15000
            )
            view.assert_preserved()
        phase("assembled-recreate-services", "assembled-services-up", desktop)
        system.assert_snapshot(saved)
        current = system.cycle("lager")
        assert current["status"] == "concluded"
        assert current["ended_at"] == ended["ended_at"]
        assert current["thermal_reserved"] is True
        assert api.post("/api/fermentations", json=candidate).status_code == 409
        assert system.cycle("ipa")["temperature_min"] == 19
        assert system.cycle("ipa")["temperature_max"] == 23
        assert system.cycle("ipa")["hysteresis"] == 1
        assert system.cycle("ipa")["thermal_settings_revision"] == 1
        configuration = api.get("/api/settings").json()
        assert configuration["revision"] == timeout["revision"]
        assert configuration["communication_timeout_seconds"] == 12
        restored_pending = wait_for_sync(api, system.devices["both"]["id"], "pending")
        assert restored_pending["applied_revision"] == pending["applied_revision"]
        assert restored_pending["desired_revision"] == timeout["revision"]
        assert combined.put("/api/v1/control", json=old_on).status_code == 409
        wait_regulation(api, system.cycles["ipa"], "suspended")

        # New data resume active cycles only. A reversed function still waits for OFF.
        system.feed("lager", "valid")
        assert system.cycle("lager")["status"] == "concluded"
        assert system.cycle("lager")["ended_at"] == ended["ended_at"]
        assert system.readings("lager") == saved["readings"]["lager"]
        system.feed("ipa", "valid")
        system.feed("ipa", "cold")
        wait_regulation(api, system.cycles["ipa"], "heating")
        system.simulators["heating"].patch(
            "/__simulation", json={"confirmation_available": False}
        ).raise_for_status()
        system.feed("ipa", "invalid_velocity")
        wait_regulation(api, system.cycles["ipa"], "suspended")
        assert system.simulators["cooling"].get("/api/v1/state").json()["actual_mode"] == "off"
        system.simulators["heating"].patch(
            "/__simulation", json={"confirmation_available": True}
        ).raise_for_status()
        wait_regulation(api, system.cycles["ipa"], "cooling")
        assert system.simulators["heating"].get("/api/v1/state").json()["actual_mode"] == "off"
        system.feed("monitor", "valid")
        assert system.cycle("monitor")["status"] == "active"
        assert "regulation" not in system.cycle("monitor")
        combined.patch("/__simulation", json={"confirmation_available": True}).raise_for_status()
        wait_regulation(api, system.cycles["lager"], "stopped")
        system.confirm_timeout(timeout["revision"])
        for simulator in system.simulators.values():
            state = simulator.get("/api/v1/state").json()
            assert state["applied_config_revision"] == timeout["revision"]
            assert state["applied_timeout_seconds"] == 12
        for view in (ipa, lager):
            view.reconnect()
        # Reconnection can legitimately outlast the short watchdog duration.
        # Fresh advertisements, rather than waiting alone, must restore regulation.
        system.feed("ipa", "valid")
        system.feed("ipa", "invalid_velocity")
        wait_regulation(api, system.cycles["ipa"], "cooling")
        show_management(desktop)
        show_management(mobile)
        expect(
            desktop.get_by_role("region", name="Regolazione IPA integrata", exact=True)
        ).to_contain_text("Raffreddamento attivo", timeout=15000)
        expect(
            mobile.get_by_role("region", name="Regolazione Lager integrata", exact=True)
        ).to_contain_text("Spegnimento confermato", timeout=15000)
        for view in (ipa, lager):
            view.page.get_by_role("tab", name="Andamento", exact=True).click()
            view.assert_preserved()
            evidence(view, "recupero")
        expect(
            mobile.get_by_role("heading", name="Storico: Lager integrata", exact=True)
        ).to_be_visible()
        desktop.get_by_role("button", name="Torna al live", exact=True).click()
        expect(desktop.get_by_label("Intervallo visualizzato")).not_to_have_text(ipa.interval)
        finish_fermentation(desktop)
        wait_regulation(api, system.cycles["ipa"], "stopped")
        assert all(
            simulator.get("/api/v1/state").json()["actual_mode"] == "off"
            for simulator in system.simulators.values()
        )
        assert system.cycle("monitor")["status"] == "active"
        assert len(api.get("/api/fermentations/active").json()["fermentations"]) == 1
    print(
        "Assembled recovery: real bridge, independent cycles, frozen views, "
        "MongoDB failure, watchdogs, settings history and terminal OFF recovered.",
        flush=True,
    )
