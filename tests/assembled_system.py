"""One real bridge, independent cycles and observable history for recovery scenarios."""

from contextlib import ExitStack
from pathlib import Path
from typing import Any

import httpx
from playwright.sync_api import Page, expect

from tests.bridge_process import BridgeProcess, advertisement_fixture
from tests.bridge_proxy import BridgeProxy
from tests.heating import wait_regulation
from tests.settings import wait_for_sync
from tests.thermal import observed_actuator, thermal_simulator
from tests.thermal_regulation import register_thermal

# RAPT v2 reference frame with temperature uint16 changed from 0x926b to 0x9000.
# 0x9000 / 128 - 273.15 = 14.85 °C; all the other reference fields are unchanged.
COLD_ADVERTISEMENT = "5054020001c16d26149000447f52c931c9022d29973f46"


class AssembledSystem:
    def __init__(self, api: httpx.Client, directory: Path, stack: ExitStack) -> None:
        self.api = api
        self.simulators = {
            capability: stack.enter_context(thermal_simulator(capability))
            for capability in ("heating", "cooling", "both")
        }
        heater_url, self.heater_commands = stack.enter_context(
            observed_actuator(self.simulators["heating"])
        )
        observed_heater = stack.enter_context(httpx.Client(base_url=heater_url))
        self.devices = {
            capability: register_thermal(
                api, observed_heater if capability == "heating" else simulator, capability
            )
            for capability, simulator in self.simulators.items()
        }
        self.pills = {}
        for key, name, mac in (
            ("ipa", "Pillola IPA", "AA:BB:CC:DD:EE:FF"),
            ("lager", "Pillola Lager", "11:22:33:44:55:66"),
            ("monitor", "Pillola monitor", "77:88:99:AA:BB:CC"),
            ("spare", "Pillola libera", "12:34:56:78:9A:BC"),
        ):
            response = api.post("/api/pills", json={"name": name, "mac": mac})
            response.raise_for_status()
            self.pills[key] = response.json()["pill"]
        self.cycles = {}
        for key, name, settings in (
            (
                "ipa",
                "IPA integrata",
                {
                    "control_mode": "heating_cooling",
                    "heater_id": self.devices["heating"]["id"],
                    "cooler_id": self.devices["cooling"]["id"],
                    "temperature_min": 20,
                    "temperature_max": 24,
                    "hysteresis": 1,
                },
            ),
            (
                "lager",
                "Lager integrata",
                {
                    "control_mode": "combined",
                    "combined_id": self.devices["both"]["id"],
                    "temperature_min": 18,
                    "temperature_max": 23,
                    "hysteresis": 1,
                },
            ),
            ("monitor", "Solo letture", {}),
        ):
            response = api.post(
                "/api/fermentations",
                json={"name": name, "pill_id": self.pills[key]["id"], **settings},
            )
            response.raise_for_status()
            self.cycles[key] = response.json()["fermentation"]
        self.timeout = self.set_timeout(60)
        self.proxy = BridgeProxy(str(api.base_url).rstrip("/"))
        stack.callback(self.proxy.stop)
        self.bridge = BridgeProcess(directory, self.proxy.url, interval=0.5, timeout_seconds=5)
        stack.callback(self.bridge.stop)
        self.bridge.wait_message("pills=4", timeout=30)
        assert all(row["last_received_at"] is None for row in self.latest_pills().values())
        for fixture in ("valid", "signed_accelerations", "valid"):
            self.feed("ipa", fixture)
        self.feed("lager", "invalid_velocity")
        self.feed("monitor", "signed_accelerations")
        wait_regulation(api, self.cycles["ipa"], "heating")
        wait_regulation(api, self.cycles["lager"], "cooling")
        assert self.simulators["cooling"].get("/api/v1/state").json()["actual_mode"] == "off"
        reading = self.readings("ipa")[0]
        assert abs(reading["temperature"] - 19.6859375) < 1e-10
        assert abs(reading["specific_gravity"] - 1.0213) < 0.00005
        assert reading["battery"] == 63.2734375
        assert reading["gravity_velocity"] == -14.821796417236328
        assert (reading["accel_x"], reading["accel_y"], reading["accel_z"]) == (
            796.5625,
            34.8125,
            665.4375,
        )
        assert reading["valid"] is True
        assert self.readings("ipa")[1]["accel_x"] == -1
        assert self.readings("ipa")[1]["valid"] is False
        assert abs(self.readings("lager")[0]["temperature"] - 23.9359375) < 1e-10
        assert self.readings("monitor")[0]["accel_z"] == 3
        assert len(api.get("/api/fermentations/active").json()["fermentations"]) == 3

    def set_timeout(self, duration: float) -> dict[str, Any]:
        response = self.api.patch("/api/settings", json={"communication_timeout_seconds": duration})
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    def confirm_timeout(self, revision: int) -> None:
        for device in self.devices.values():
            wait_for_sync(self.api, device["id"], revision=revision)

    def feed(self, key: str, fixture: str, *, forwarded: bool = True) -> None:
        payload = COLD_ADVERTISEMENT if fixture == "cold" else advertisement_fixture(fixture)
        self.bridge.advertise(self.pills[key]["mac"], payload)
        message = "reading_forwarded" if forwarded else "reading_delivery_failed"
        self.bridge.wait_message(f"{message} source={self.pills[key]['mac']}")

    def cycle(self, key: str) -> dict[str, Any]:
        response = self.api.get(f"/api/fermentations/{self.cycles[key]['id']}")
        response.raise_for_status()
        result: dict[str, Any] = response.json()["fermentation"]
        return result

    def readings(self, key: str) -> list[dict[str, Any]]:
        response = self.api.get(f"/api/fermentations/{self.cycles[key]['id']}/readings")
        response.raise_for_status()
        result: list[dict[str, Any]] = response.json()["readings"]
        return result

    def latest_pills(self) -> dict[str, Any]:
        response = self.api.get("/api/readings/latest")
        response.raise_for_status()
        return {row["id"]: row for row in response.json()["pills"]}

    def snapshot(self) -> dict[str, Any]:
        return {
            "contacts": {
                identifier: row["last_received_at"]
                for identifier, row in self.latest_pills().items()
            },
            "readings": {key: self.readings(key) for key in self.cycles},
            "history": self.api.get(
                f"/api/fermentations/{self.cycles['ipa']['id']}/thermal-settings/history"
            ).json()["history"],
            "registry": self.api.get("/api/bridge/pills").json(),
        }

    def assert_snapshot(self, saved: dict[str, Any]) -> None:
        assert self.snapshot() == saved
        assert self.cycle("monitor")["control_mode"] == "monitor_only"
        assert "regulation" not in self.cycle("monitor")
        for key in self.cycles:
            current = self.cycle(key)
            for field in ("id", "name", "pill_id", "started_at", "control_mode", "devices"):
                assert current.get(field) == self.cycles[key].get(field)
            assert all(row["pill_id"] == self.pills[key]["id"] for row in self.readings(key))


class FrozenHistory:
    def __init__(self, page: Page, system: AssembledSystem, key: str) -> None:
        self.page = page
        self.name = system.cycles[key]["name"]
        self.url = (
            f"{str(system.api.base_url).rstrip('/')}/?fermentation={system.cycles[key]['id']}"
        )
        page.goto(self.url)
        expect(
            page.get_by_role("heading", name=f"Dettaglio: {self.name}", exact=True)
        ).to_be_visible()
        page.get_by_role("button", name="Tutto", exact=True).click()
        if key == "ipa":
            samples = system.readings(key)
            end = (samples[1]["timestamp"] + samples[2]["timestamp"]) / 2
            page.get_by_label("Fine intervallo", exact=True).evaluate(
                "(element, value) => { element.value = String(value); "
                "element.dispatchEvent(new Event('input', { bubbles: true })) }",
                end,
            )
        page.get_by_label("Batteria %", exact=True).uncheck()
        expect(page.get_by_text("Caricamento storico…", exact=True)).to_have_count(0)
        self.interval = page.get_by_label("Intervallo visualizzato").inner_text()
        self.table = page.get_by_role("table", name="Letture della fermentazione")
        expect(self.table.get_by_role("row")).to_have_count(3 if key == "ipa" else 2)
        rows = self.table.text_content()
        assert rows is not None
        self.rows = rows
        self.times = self.table.locator("time").evaluate_all(
            "elements => elements.map(element => element.dateTime)"
        )
        assert self.times
        assert len(self.times) == (2 if key == "ipa" else 1)
        self.assert_preserved()

    def assert_preserved(self) -> None:
        expect(self.page.get_by_label("Intervallo visualizzato")).to_have_text(self.interval)
        expect(self.table).to_have_text(self.rows)
        assert (
            self.table.locator("time").evaluate_all(
                "elements => elements.map(element => element.dateTime)"
            )
            == self.times
        )
        expect(self.page.get_by_label("Batteria %", exact=True)).not_to_be_checked()
        assert self.page.url == self.url

    def reconnect(self) -> None:
        expect(self.page.get_by_label("Collegamento live")).to_have_text(
            "Collegamento live attivo", timeout=90000
        )
        expect(self.page.get_by_text("Caricamento storico…", exact=True)).to_have_count(0)
        self.assert_preserved()
