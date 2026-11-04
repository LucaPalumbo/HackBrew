## Problem Statement

The homebrewer needs to follow several fermentazioni at the same time, using a different pillola for each one, and associate the equipment that heats or cools each fermentatore. HackBrew currently supports one globally active fermentazione, has no equipment registry or automatic temperature regulation, and retains only part of the measurements supplied by the bridge.

The existing dashboard also makes it difficult to inspect several quantities together or investigate a particular time interval. The homebrewer needs recognizable summaries for active and concluded fermentazioni, a dedicated detail page, and one large, interactive line chart that remains usable on a phone.

Temperature control must have predictable communication-loss behaviour. The homebrewer needs one configurable timeout, shared symmetrically by HackBrew and the actuators, and a definitive manual end that stops all associated thermal devices without later reopening the fermentazione.

## Solution

Extend HackBrew with a registry for pillole and dispositivi termici, concurrent fermentazioni with exclusive equipment assignments, and optional automatic regolazione termica. A fermentazione can instead run in solo monitoraggio, with a pillola and no temperature settings or actuators.

Use one bridge for all registered pillole. Registering a pillola's name and Bluetooth MAC in the web application is sufficient: the bridge obtains the registry automatically and identifies the source of every lettura. Retain every measurement supplied by the bridge and expose it in a single large line chart with selectable series, separate unit scales, a time navigator, zoom, panning and Torna al live.

HackBrew owns the temperature-control logic. Thermal devices execute absolute HTTP commands, report their actual state and implement an autonomous communication timeout. One global setting, initially three hours, can be changed at any time and is synchronized with the actuators. If HackBrew receives no data from a fermentazione's pillola for that duration, it requests all its actuators off and suspends regulation. If an actuator receives no server commands for the same duration, it turns itself off. The fermentazione remains active in both cases.

Keep Vue/TypeScript, Python/FastAPI, MongoDB, live updates and the existing Docker workflow. Existing application data may be discarded during the deliberate upgrade to this version; historical migration is not required.

## User Stories

1. As a homebrewer, I want to register a pillola with a recognizable name and its Bluetooth MAC, so that I can identify the source of its measurements.
2. As a homebrewer, I want equivalent MAC spellings to identify the same pillola, so that registration does not accidentally create duplicates.
3. As a homebrewer, I want to see my registered pillole, so that I can choose the appropriate one for each fermentazione.
4. As a homebrewer, I want to register a dispositivo termico with its name, capabilities and connection address, so that HackBrew can use my heating and cooling equipment.
5. As a homebrewer, I want to distinguish heating-only, cooling-only and combined devices, so that I can make a valid equipment selection.
6. As a homebrewer, I want to see whether equipment is assigned or available, so that I do not try to reuse hardware already serving another fermentazione.
7. As a homebrewer, I want one bridge to read all registered pillole, so that I do not need a separate bridge instance for every fermentatore.
8. As a homebrewer, I want the bridge to acquire the pillola registry automatically, so that registering a pillola in the web application is sufficient.
9. As a homebrewer, I want each lettura to identify its pillola, so that simultaneous data streams cannot become mixed.
10. As a homebrewer, I want a latest diagnostic lettura for a pillola outside an active fermentazione, so that I can check the connection before starting.
11. As a homebrewer, I want to create and manually start a named fermentazione, so that I decide what beer I am monitoring and when its monitoring period begins.
12. As a homebrewer, I want to select exactly one pillola when starting a fermentazione, so that its measurements have a clear source.
13. As a homebrewer, I want several fermentazioni to remain active together, so that I can monitor several fermentatori independently.
14. As a homebrewer, I want one pillola to belong to at most one active fermentazione, so that its data is not attributed to two simultaneous batches.
15. As a homebrewer, I want concurrent start requests to respect equipment exclusivity, so that two browser tabs cannot reserve the same hardware.
16. As a homebrewer, I want to start in solo monitoraggio without selecting thermal devices, so that I can observe a fermentazione without automatic control.
17. As a homebrewer, I want temperature limits and hysteresis to be unnecessary in solo monitoraggio, so that I only enter settings that are used.
18. As a homebrewer, I want to choose one heater, one cooler, both separate devices, or one combined device, so that the configuration matches my equipment.
19. As a homebrewer, I want a thermal device to serve only one active fermentazione at a time, so that different fermentazioni cannot send it competing commands.
20. As a homebrewer, I want to enter minimum temperature, maximum temperature and hysteresis when using regulation, so that HackBrew follows the temperature band I choose.
21. As a homebrewer, I want invalid or inconsistent control settings to be rejected clearly, so that an unusable configuration is not silently applied.
22. As a homebrewer, I want HackBrew to start heating at the minimum threshold and stop after the hysteresis margin, so that heating does not oscillate around one temperature.
23. As a homebrewer, I want HackBrew to start cooling at the maximum threshold and stop after the hysteresis margin, so that cooling does not oscillate around one temperature.
24. As a homebrewer, I want heating and cooling to remain mutually exclusive, so that equipment does not work against itself.
25. As a homebrewer, I want to use heating-only or cooling-only equipment without selecting a device for the other function, so that regulation supports the hardware I actually own.
26. As a homebrewer, I want to change the temperature band and hysteresis during an active fermentazione, so that I can adjust my fermentation conditions.
27. As a homebrewer, I want changes to regulation settings to remain recorded, so that I can understand which settings were in effect.
28. As a homebrewer, I want pillola and actuator assignments to remain fixed during an active fermentazione, so that its measurements and equipment remain unambiguous.
29. As a homebrewer, I want one global communication timeout with an initial value of three hours, so that I can understand and manage the communication-loss policy in one place.
30. As a homebrewer, I want to change that timeout in the settings page while fermentazioni are running, so that I do not need to restart a batch or the application.
31. As a homebrewer, I want the server and actuators to use the same timeout duration, so that both sides follow a symmetric policy.
32. As a homebrewer, I want timeout changes to be synchronized with the actuators and any unconfirmed application to be visible, so that I can distinguish the requested setting from what devices have acknowledged.
33. As a homebrewer, I want the server to request all associated actuators off when a pillola stops sending data for the configured duration, so that regulation stops using a disconnected source.
34. As a homebrewer, I want data arriving from another pillola to leave that timeout unchanged, so that one functioning fermentatore cannot hide a disconnected one.
35. As a homebrewer, I want an actuator to turn itself off if server commands stop for the same duration, so that this behaviour also works when HackBrew is unavailable.
36. As a homebrewer, I want communication-loss shutdown to leave the fermentazione active, so that its monitoring cycle does not end because of a temporary interruption.
37. As a homebrewer, I want regulation to remain suspended before any usable temperature is available, so that devices do not act on an invented measurement.
38. As a homebrewer, I want regulation to resume automatically when valid data and device communication return, so that a temporary interruption does not require recreating the fermentazione.
39. As a homebrewer, I want HackBrew to verify device state before resuming regulation after a restart, so that it does not assume a physical state from memory alone.
40. As a homebrewer, I want to distinguish requested device state from confirmed actual state, so that an unsuccessful command cannot appear as a confirmed result.
41. As a homebrewer, I want communication errors to be visible while the fermentazione stays active, so that I can investigate the problem without losing its identity or history.
42. As a homebrewer, I want to end a fermentazione manually and definitively, so that I decide when that cycle is over.
43. As a homebrewer, I want manual termination to request every associated thermal device off, so that neither heating nor cooling continues for a completed batch.
44. As a homebrewer, I want manual termination to remain definitive even if a device is unreachable, so that a later reading or reconnection cannot reopen the fermentazione.
45. As a homebrewer, I want unconfirmed shutdowns to remain visible and prevent device reassignment, so that hardware is not shown as available before it is confirmed off.
46. As a homebrewer, I want repeated termination or shutdown delivery to preserve the same concluded cycle, so that retries do not change its end time or reactivate equipment.
47. As a homebrewer, I want a page of summary cards for active and concluded fermentazioni, so that I can review all my batches in one place.
48. As a homebrewer, I want active fermentazioni to be highlighted and listed first, so that ongoing work is easy to find.
49. As a homebrewer, I want each card to show name, lifecycle state, pillola, latest temperature, density, battery and regulation state, so that I can assess a fermentazione quickly.
50. As a homebrewer, I want to search fermentazioni by name, so that I can find earlier batches as the list grows.
51. As a homebrewer, I want a card to open that fermentazione's detail page, so that I can inspect its settings and complete measurement history.
52. As a homebrewer, I want detail links, browser navigation and reloads to preserve the selected fermentazione, so that I can return to the same batch reliably.
53. As a homebrewer, I want one large line chart in the detail page, so that I can compare measurements on the same time axis.
54. As a homebrewer, I want temperature, density, battery, gravity velocity and all three acceleration axes to be retained and available as chart series, so that no supplied measurement is discarded.
55. As a homebrewer, I want to show and hide individual series from the legend, so that I can focus on the quantities I need.
56. As a homebrewer, I want separate scales for different units, so that measurements of different magnitudes remain readable.
57. As a homebrewer, I want invalid gravity velocity to be identified without invalidating temperature or the other measurements, so that I can trust the meaning of the bridge's quality flag.
58. As a homebrewer, I want lines to connect available samples even when they are far apart in time, so that the chart has no automatic breaks or gap highlighting.
59. As a homebrewer, I want a time navigator with two draggable ends, so that I can select a subset of the recorded period.
60. As a homebrewer, I want quick intervals of one hour, six hours, twenty-four hours and the whole fermentazione, so that common views are easy to select.
61. As a homebrewer, I want wheel zoom, mouse selection zoom, phone pinch zoom and horizontal panning, so that I can investigate a time interval on either device.
62. As a homebrewer, I want an inspected interval to remain fixed when new data arrives, so that live updates do not move the part I am studying.
63. As a homebrewer, I want Torna al live to restore automatic following of the newest data, so that I can return from investigation to current monitoring.
64. As a homebrewer, I want to inspect the complete selected interval rather than only an arbitrary latest page of samples, so that older measurements are not silently omitted.
65. As a homebrewer, I want cards, forms, chart controls and details to work on a phone, so that I can manage fermentazioni away from my computer.
66. As a homebrewer, I want clear empty, loading, disconnected and error states while preserving already loaded values, so that unavailable data is not mistaken for zero or for a new reading.
67. As a homebrewer, I want identical deliveries to avoid duplicate historical samples and delayed readings to retain the correct pillola and fermentazione, so that concurrent streams keep reliable histories.
68. As a homebrewer, I want new records and settings to survive application and container restarts, so that the browser is not responsible for preserving them.
69. As a homebrewer, I want the deliberate upgrade to start with a clean application dataset, so that obsolete development data does not require a compatibility migration.
70. As a contributor, I want development, build, checks and tests to use the Docker workflow, so that host-installed Python, Node or MongoDB are unnecessary.
71. As a contributor, I want automated tests to exercise the public application and HTTP equipment contracts without real hardware, so that regulation and failures can be checked reproducibly.

## Implementation Decisions

### Application architecture and scope

- Retain Vue/TypeScript and the existing charting stack for the frontend, Python/FastAPI for the backend, MongoDB for persistence, and Docker/Compose for the application and tooling. Keep the existing supported command interface and extend its documentation when needed.
- Add the equipment registry and regulation interfaces, and extend the existing fermentazione, telemetry/history, live-update and frontend interfaces into coherent public application boundaries. Regulation runs server-side and continues without an open browser. Browser timers must never own actuator control.
- The bridge repository is now included specifically for multi-pillola collection, registry synchronization and source identification. This supersedes the original MVP exclusion of bridge changes. The bridge remains external to the three application components; its containerization is not required.
- Hardware drivers and actuator firmware are not implemented by this specification. Define and document a provisional HTTP contract, provide a deterministic simulator for development and automated verification, and require future physical devices to implement its actual-state and autonomous-timeout behaviour.

### Registry and resource ownership

- A pillola has a stable application identifier, name and unique normalized Bluetooth MAC. Accept a documented MAC notation and normalize equivalent case/separator representations. Validate input and reject duplicate identities. This is the pillola's Bluetooth address, not the bridge's network address.
- A dispositivo termico has a stable identifier, name, capability (heating, cooling or both), and configured HTTP base address. Retain requested state, actual confirmed state, acknowledgement time, communication error, applied configuration revision and assignment/reservation information as needed to expose truthful public status.
- Registration and equipment selection are public application operations. Compatible capability checks and ownership checks belong on the server as well as in the UI.
- Replace the global single-active-fermentazione restriction with atomic per-resource exclusivity. One active fermentazione owns exactly one pillola and optionally one heater and/or one cooler, or one combined device. Do not combine a both-capabilities device with extra separate devices in the same selection. The same hardware cannot be reserved by simultaneous start requests.
- A dispositivo termico awaiting confirmed shutdown remains reserved even after its fermentazione has concluded. Release it only when the off state is confirmed. Pillola assignment and thermal-device assignment cannot be changed while a fermentazione is active.
- Resource registration does not imply a separate recipe or beer catalogue. A beer name names the monitored fermentazione.

### Bridge and telemetry contract

- One bridge obtains the list of registered pillole from a documented HTTP registry endpoint, provisionally GET /api/bridge/pills, and periodically synchronizes additions. Its polling interval is an integration detail distinct from the user-facing communication timeout.
- Return a stable pillola identifier, name, Bluetooth MAC and registry revision. The bridge reads the registered MACs and includes the originating pillola's normalized Bluetooth MAC in every telemetry message. A provisional added field is pill_mac. Reject missing, malformed or unknown source identity with an explicit client error rather than assigning data to an arbitrary active fermentazione.
- Preserve the existing POST /telemetry boundary and the bridge's nine measurement/metadata fields: valid, gravity_velocity, temperature, specific_gravity, accel_x, accel_y, accel_z, battery and timestamp, alongside pillola identity. Keep temperature in Celsius, normalize specific_gravity from SG times 1000 to SG, retain battery percentage and retain the existing gravity-velocity scale of SG points per day.
- Preserve acceleration values without inventing a physical unit that is absent from the gateway documentation. Label them as gateway acceleration values with unit unspecified until the actual protocol scale is established. Do not label these values as g or metres per second squared without evidence.
- The valid flag qualifies gravity_velocity only. False does not discard the lettura or prevent temperature regulation. Missing or invalid optional quantities are unavailable rather than zero. The chart plots usable values from each series and does not introduce temporal gap splitting.
- Partition latest diagnostic readings, persisted measurements, chronological ordering, deduplication and live snapshots by pillola. Identical readings from different pillole are distinct. Deduplication includes source identity and all retained measurement/quality content, without rounding away distinct measurements.
- Preserve the existing acquisition-time association rule: a lettura belongs to that pillola's fermentazione whose interval contains its timestamp, start inclusive and end exclusive. Delayed readings may enrich a concluded interval without reopening it or replacing a newer live measurement. A different pillola's interval must never capture the reading.
- Keep acquisition time and server receipt time distinct. Preserve a historical sample's original receipt metadata on duplicate delivery; separately track the latest successful telemetry reception per pillola for communication timeout evaluation. Invalid requests and another pillola's traffic do not refresh this timestamp.
- Preserve latest diagnostic readings when a pillola has no active fermentazione, without introducing a complete diagnostic history outside fermentation intervals. The bridge's registry request itself does not count as receiving a pillola measurement.
- Do not introduce durable bridge buffering or failed-delivery retransmission as part of registry synchronization. An unavailable registry or HTTP delivery failure must not manufacture data or report a successful persisted delivery.

### Fermentazione lifecycle and temperature regulation

- Extend fermentazione creation to accept its name, pillola and thermal-device selection. No actuators means solo monitoraggio and requires no temperature limits or hysteresis. Actuator selection requires minimum temperature, maximum temperature and hysteresis.
- Validate finite control values, minimum less than maximum, positive hysteresis, and switch-off thresholds within the configured band. Do not silently clamp invalid settings. For heating-only or cooling-only equipment, simply leave the unavailable function off.
- For minimum L, maximum U and hysteresis H: heating starts at temperature at or below L and stops at or above L plus H; cooling starts at or above U and stops at or below U minus H. Between a function's thresholds, retain its current confirmed control state. With 18–22 degrees Celsius and H of 0.5, the thresholds are 18/18.5 for heating and 22/21.5 for cooling.
- Enforce mutual exclusion for both separate and combined devices. Before enabling the opposite function, obtain confirmation that the previous function is off. A missing confirmation suspends regulation rather than assuming the transition succeeded.
- A fermentazione without a usable temperature remains in a waiting/suspended state with actuators off. The active/concluded lifecycle is separate from regulation states such as monitor-only, waiting, heating, cooling, idle, suspended or error.
- Permit active changes to minimum, maximum and hysteresis. Validate the new set together, persist the change with time and revision, preserve its history, and reevaluate control against the latest usable reading. A settings change must not change the selected equipment or monitoring interval.
- Regulation responds to new measurements and evaluates communication deadlines independently of telemetry arrival. A periodic server-side control process must continue checking deadlines and renewing actuator commands even when measurements are less frequent.
- Resume regulation automatically after valid data and device communication return, only for an active fermentazione. On restart, reload persisted ownership, settings, deadlines and concluded status, reconcile actual device state, and only then issue appropriate commands. Persist enough state to preserve hysteresis across a restart without treating an unverified physical state as confirmed.
- A communication failure requests associated devices off, exposes the failure and leaves the fermentazione active. Desired off and confirmed off are separate states; do not claim successful shutdown without acknowledgement. Retry/reconcile shutdown without enabling the opposite function.
- Manual end commits one definitive conclusion timestamp and requires off for every associated actuator/function. It remains concluded when delivery fails. Persist pending shutdown and continue retry/reconciliation after failures or restarts. New data, reconnecting devices and repeated end requests cannot reopen it; repeated end preserves the original conclusion time and state.

### Symmetric configurable communication timeout

- Introduce one persisted global setting in the settings page, provisionally communication_timeout_seconds, initially 10800 seconds (three hours). Accept a positive finite duration with explicit units and reject zero, negative or malformed values. It applies to all fermentazioni and can be changed at any time through the normal application interface.
- On the server, measure elapsed time since the latest accepted telemetry reception from each assigned pillola. Once the configured duration has elapsed without data, request every associated actuator off and suspend regulation while leaving the fermentazione active. Do not reset the timer on settings reads, bridge registration polling, another pillola's data or failed input.
- On an actuator, measure elapsed time since its last accepted valid server control command. If that duration expires, the actuator must turn itself off autonomously. Reading device state must not renew this deadline. Periodic state commands keep the lease alive while server-side regulation permits it.
- Both sides use the same configured duration. They have different last-contact instants, so symmetry does not imply they expire at the same wall-clock instant. This single timeout replaces all earlier fixed shutdown durations discussed during planning.
- A timeout change reevaluates server deadlines against existing receipt times instead of pretending that new telemetry arrived. Shortening it below an existing silence interval requests off immediately. Synchronize the new duration with devices, renew commands at an interval comfortably below the configured duration, and expose desired versus acknowledged timeout/configuration revision. An unreachable device cannot be reported as already updated.
- Communication status in the UI follows this persisted timeout. Remove the old separate fixed freshness policy from the resulting behaviour rather than retaining competing warning/shutdown thresholds. The chart has no gap-timeout setting.
- Timeout configuration and last-contact metadata survive application/container restarts. After a timeout-triggered suspension, new usable data and confirmed device communication allow automatic resumption; concluded fermentazioni remain concluded.

### Provisional public HTTP interfaces

- Provide list/register operations for pillole and thermal devices, provisionally GET/POST /api/pills and GET/POST /api/thermal-devices. Expose availability, capabilities and truthful communication/control status so the frontend does not infer ownership from names.
- Extend the existing fermentazioni list/create/detail/end interfaces for concurrent activity and equipment assignment. The list includes both active and concluded records, active first, and retains name search and bounded navigation. Provide an atomic temperature-control settings update operation on an individual fermentazione and a read interface for its settings-change history.
- Provide GET/PATCH /api/settings for the global timeout. The response makes the persisted desired value and device synchronization status observable. Frontend settings changes do not require a process restart or environment-file edit.
- Extend history queries to accept explicit acquisition-time bounds and cursor navigation over the selected interval, preserving every stored sample including equal timestamps. Extend latest/diagnostic queries to identify the pillola and live notifications to identify their entity/fermentazione rather than representing one global active record.
- Keep public validation/error semantics consistent with the existing API: invalid input is explained, unknown resources are distinguished from resource conflicts, concurrent ownership conflicts are explicit, and database failure is not acknowledged as a successful persisted mutation.
- The provisional actuator contract uses PUT /api/v1/control for an absolute requested mode (off, heating or cooling), the common timeout duration, a command identifier and monotonically ordered revision/ownership information. GET /api/v1/state returns capabilities, confirmed actual mode, applied timeout/configuration revision and acknowledgement information. These paths are placeholders and belong behind one replaceable integration adapter.
- Commands are idempotent and ordered so that retries or delayed older ON commands cannot supersede a newer OFF or the end of an ownership period. A device rejects unsupported modes and obsolete commands. A combined device has one mutually exclusive mode; off disables both functions.
- Device acknowledgements distinguish accepted desired mode from actual applied state. The server reconciles both, retains pending/error state if confirmation is absent, and does not free the reservation based only on a network write completing.
- The HTTP simulator exposes these same device endpoints, autonomous timeout behaviour and controllable failures for automated tests. Test-only simulation controls stay outside the production application API.

### Cards, detail and combined chart

- Add a device-registration page, a fermentazioni overview, a dedicated fermentazione detail view and the global settings page. Preserve responsive layout and Italian user-facing terminology. Do not prescribe an unapproved visual theme.
- Each summary card shows name, active/concluded status, pillola, latest temperature, SG, battery and regulation state. Highlight active cards and list them before concluded records; retain name search. Missing measurements are explicit, not zero. Live updates refresh the relevant card without switching the user's selected detail.
- The detail exposes lifecycle, assignments, regulation settings/status and timestamps, plus one large combined line chart. The view is directly addressable; browser back/forward, reload and reopening a link preserve the selected fermentazione.
- Provide seven numerical series: temperature, SG, battery, gravity velocity and acceleration X/Y/Z. Show all seven initially and keep them distinguishable and individually selectable from a legend. Use separate scales for temperature, density, battery, gravity velocity and the acceleration axes' common scale, with honest unit labels and real acquisition time on the horizontal axis.
- This is a line chart, not a scatter plot. Connect available usable samples regardless of elapsed time. Do not break or highlight lines because of temporal gaps, add synthetic samples, replace missing values with zero or interpolate stored measurements. Values unavailable for a series are omitted from that series while other quantities remain usable.
- Provide a time navigator with two draggable bounds, quick intervals of 1h, 6h, 24h and Tutto, wheel zoom, mouse-area-selection zoom, phone pinch zoom and horizontal pan. Make pan and selection-zoom gestures distinguishable and provide usable controls on touch screens.
- Fetch the complete requested time interval through bounded API queries as necessary; a chart must not silently become only the latest 200 samples. Preserve exact samples and make loading, empty intervals and retrieval failure explicit. Use cancellation/stale-response handling so rapid changes cannot replace the current window with an older request.
- User time selection, zoom and pan hold the visible interval fixed while new readings arrive. Torna al live restores automatic following of the newest readings. Updating another fermentazione must not reset this view or its selected series.
- Preserve an accessible exact-value representation of the selected readings alongside chart interactions, following the existing table-based approach. Assert behaviour and readability at desktop and phone widths rather than fixed chart internals or arbitrary pixels.

### Storage, upgrade and operational behaviour

- Persist registries, assignments/reservations, retained metrics and quality flags, per-pillola latest state and communication metadata, fermentazioni, control-setting changes, pending shutdown and global settings in MongoDB. Enforce ownership and deduplication atomically under concurrent requests and after restart.
- The user explicitly authorizes discarding the current application dataset when deliberately adopting this version. Document a targeted reset/upgrade procedure instead of implementing a legacy-data migration. Do not make database deletion an unconditional application-start behaviour or delete unrelated Docker volumes.
- After that one-time reset, new data and settings must persist through ordinary rebuilds, restarts, reconnects and upgrades. Avoid coupling the product's temporary name to equipment identity or the protocol.
- Preserve truthful failure behaviour: no fabricated latest measurements, no acknowledged unsaved telemetry, no silent reopening of ended cycles, and no claim that an unreachable actuator has physically turned off. Database/network recovery must reconcile persisted pending actions.

## Testing Decisions

- The user confirmed the testing boundary during this to-spec session: public HTTP APIs and browser-visible behaviour against the real application and real MongoDB in isolated Docker, including bridge contracts and HTTP actuator simulators. Use these application-level boundaries rather than new private-helper tests or direct database assertions.
- Existing prior art is the pytest HTTP suite for telemetry validation, normalization, duplicate/concurrent deliveries, chronological association, lifecycle conflicts and history pagination; Playwright desktop/mobile tests for live updates, historical selection, reload/back navigation and recovery; and operational checks that restart/recreate actual application/database containers while preserving the isolated test volume.
- A good test verifies a user-observable result: equipment reserved or rejected, correctly sourced persisted values returned by public queries, commands and confirmed state exposed by the actuator contract, a visible suspension/error, a terminal conclusion, or the selected time interval remaining fixed. Do not test collection structure, private call order, component internals, CSS classes or a particular chart object implementation.
- Cover registration validation, normalized duplicate MACs, device capability selection, and one bridge collecting several registered pillole. Verify registry synchronization and source MAC using deterministic BLE advertisement/input fixtures at the bridge's external input boundary and its real HTTP exchange, without requiring Bluetooth hardware. Keep contract fixtures shared/documented so a fake gateway alone cannot conceal an incompatible real bridge change.
- Cover concurrent fermentazioni with distinct pillole; reject reuse of either a pillola or thermal device under competing requests; keep readings, latest diagnostics, card state and history separate even for identical timestamps and values. Include delayed delivery across successive fermentazioni using the same pillola, interval boundaries and concurrent duplicates including extra metrics/quality differences.
- Exercise the regulation table through submitted telemetry and externally observed device commands/state: heating and cooling trigger/stop boundaries, equality at thresholds, hysteresis retention, heating-only, cooling-only, combined hardware, mutual exclusion, no temperature, monitor-only, and active settings changes with recorded history.
- Use stateful HTTP actuator simulators supporting acknowledgements, delayed/stale commands, lost connectivity and autonomous expiry. Test requested versus actual state, failure to turn off, retries, ownership reservation until confirmed off, manual end during an outage, terminal behaviour after reconnect and prevention of stale ON reactivation.
- Exercise the public timeout setting with short valid test durations instead of waiting three hours or introducing a production clock-control endpoint. Verify the initial three-hour value separately. Observe server-side no-data shutdown, actuator-side no-command expiry, irrelevant pillola traffic, rejection of invalid input, command renewal, shortening/extending the timeout, synchronized acknowledged values and visible pending configuration when devices are unreachable.
- Stop the actual application container while a simulator is active and verify the actuator contract's autonomous expiry without server intervention. Restart/recreate the actual application with the same test MongoDB data and verify reconciliation, persisted settings, independent fermentazioni, hysteresis behaviour, pending off actions and irreversible manual conclusion. These checks prove the integration and simulator contract, not the implementation of a future physical actuator's firmware.
- Browser flows cover device registration, starting monitor-only and regulated fermentazioni, overview ordering/highlighting/search, detail links and navigation, live card updates, active settings edits and the global timeout page. Include empty states, errors and recovery at desktop and phone viewport sizes.
- Browser chart flows verify one line chart with all seven series available, usable legend toggles/unit labels and exact values, connecting widely separated samples, the full requested history beyond one API page, slider bounds, presets, wheel and mouse-selection zoom, touch interactions, pan, frozen inspection while new data arrives and Torna al live. Check observable ranges/data and accessible representations; use visual evidence where necessary to establish actual line rendering without inspecting Chart.js internals.
- Preserve the existing guarantees for MongoDB outages and interrupted live connections. Extend operational recovery tests to stateful regulation, not just a mocked restart or a browser reload. Automated tests and their cleanup remain isolated from the homebrewer's application volume and must never execute the upgrade reset against real data.
- Run all tooling and checks through the supported Docker command interface. Automated acceptance must not require physical pillole, Bluetooth, real actuators, cloud accounts or credentials. Record hardware compatibility checks separately when a real gateway/actuator is available, including actual on/off confirmation, common timeout propagation and autonomous expiry.

## Out of Scope

- Internet hosting, domains, reverse proxies, TLS, GitHub login, authentication, multiple users and public registration. Personal use remains the target; authentication and remote deployment remain deferred.
- A beer/recipe catalogue, recipes, fermentation profiles with scheduled temperature steps, automatic lifecycle completion, analytics, ABV/attenuation calculations, notifications and alarms.
- Changing pillola firmware, calibrating sensors, inventing acceleration units, implementing thermal-device firmware/drivers, or promising physical watchdog behaviour without a compatible actuator. The required HTTP behaviour and simulator are included; real hardware compliance is a separate integration check.
- Bridge durable queues, failed-message retransmission or recovery of readings discarded before HackBrew received them. Containerizing the bridge or expanding the application into additional deployed infrastructure is not required.
- Reassigning pillole or thermal devices during an active fermentazione, adding a manual override that bypasses regulation, or supporting simultaneous independent heating and cooling output.
- Migrating or importing the current development dataset, bulk editing/export, and a general-purpose destructive reset button. The approved clean upgrade is a targeted operational step.
- Automatic graph gap detection, gap highlighting, temporal gap breaks or a configurable gap threshold. Earlier fixed communication durations are superseded by the single configurable symmetric timeout.
- A wholesale visual redesign, multiple design prototypes or requiring a new frontend framework/database/test architecture.

## Further Notes

- Shared understanding of the functional evolution was explicitly confirmed by the user after the final clarification: no chart gaps, one global editable symmetric communication timeout initially three hours. The public HTTP/browser testing boundaries, real MongoDB and actuator simulators were separately confirmed during this specification session.
- The baseline is an implemented MVP with Docker tooling, live monitoring, manual lifecycle, historical queries, public HTTP/browser tests and operational restart/outage verification. This specification supersedes its single-active-fermentazione restriction, limited retained metrics, scatter charts, fixed freshness policy and earlier exclusion of the specifically approved bridge changes.
- The bridge is [LucaPalumbo/RaptPillGateway-ble-http](https://github.com/LucaPalumbo/RaptPillGateway-ble-http). The previously inspected baseline commit is 0bfc4a7fbbcfc2f231f75452d194de86677d46e2; it sends nine fields without source identity, selects one configured Bluetooth MAC and has no actuator protocol. Bridge implementation work must verify the current source before modifying it. The physical acceleration unit remains undocumented.
- Actuator URL paths and field names above are provisional integration choices explicitly delegated by the user. Keep their adapter replaceable while retaining the agreed observable behaviour, including real-state confirmation, command ordering and autonomous expiry. Do not report a simulated device passing tests as proof that physical firmware already supports this contract.
- No application behaviour, bridge code, production database reset or hardware provisioning is performed by publishing this specification. Implementation should be decomposed into linked, reviewable tickets, including the necessary bridge work, while keeping the overall acceptance behaviour in this spec.
