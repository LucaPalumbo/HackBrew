## Problem Statement

A homebrewer needs a simple way to follow beer fermentation from a computer or phone. A pillola inside the fermentatore already supplies density, temperature and battery measurements through an existing Bluetooth-to-HTTP gateway, but there is no application that turns those letture into a live dashboard and a persistent history for each fermentazione.

The homebrewer needs to distinguish current readings from old data, understand trends, and keep successive fermentazioni separate while reusing the same pillola and fermentatore.

The first delivery is for personal use and local execution. Remote hosting and authentication will be addressed later.

## Solution

Build a responsive web application with Vue 3, TypeScript and Vite, a Python/FastAPI backend, MongoDB persistence, Chart.js charts and Server-Sent Events for live updates. Build, development, testing and application execution must be reproducible using Docker and Docker Compose.

The homebrewer creates a named fermentazione, starts it manually, follows its measurements and charts, and ends it manually. Only one fermentazione can be active at a time. Concluded fermentazioni remain available in history. When none is active, the dashboard still shows the latest lettura to help check the pillola and gateway connection, without creating a history of diagnostic readings.

Accept the existing gateway's HTTP contract. The gateway remains an external project and is neither changed nor containerized by this work. Use the domain terms fermentatore, pillola, fermentazione, fermentazione attiva and lettura consistently with the project's glossary.

## User Stories

1. As a homebrewer, I want to open a dashboard on my computer, so that I can check the fermentatore from one place.
2. As a homebrewer, I want the dashboard to adapt to a phone screen, so that I can inspect readings and use the controls comfortably on mobile.
3. As a homebrewer, I want to see the latest density expressed as SG, so that I can follow the progress of my fermentazione using the agreed unit.
4. As a homebrewer, I want to see temperature in degrees Celsius, so that I can understand the current temperature without converting it myself.
5. As a homebrewer, I want to see the pillola's battery percentage, so that I can judge its remaining charge.
6. As a homebrewer, I want to see when the displayed lettura was acquired, so that I can tell how recent the values are.
7. As a homebrewer, I want values to update automatically when a new lettura arrives, so that I do not have to refresh the page.
8. As a homebrewer, I want to see density plotted over time, so that I can understand its trend beyond the most recent value.
9. As a homebrewer, I want to see temperature plotted over time, so that I can inspect changes during the fermentazione.
10. As a homebrewer, I want recorded battery values to remain available alongside the other readings, so that I can inspect the pillola's behaviour throughout a fermentazione.
11. As a homebrewer, I want charts and summary values to use the same stored measurements and units, so that they tell a consistent story.
12. As a homebrewer, I want charts and controls to remain usable on a narrow screen, so that long fermentazioni do not make the mobile dashboard impractical.
13. As a homebrewer, I want an explicit empty state before any lettura has arrived, so that missing data cannot be mistaken for zero density, temperature or battery.
14. As a homebrewer, I want the latest lettura to be visible when no fermentazione is active, so that I can check the connection before starting.
15. As a homebrewer, I want diagnostic readings outside a fermentazione to avoid creating a separate history, so that trial measurements do not clutter my fermentation records.
16. As a homebrewer, I want to give a fermentazione a name, so that I can recognize it later.
17. As a homebrewer, I want to start a fermentazione manually, so that I decide when its monitoring period begins.
18. As a homebrewer, I want the application to allow only one active fermentazione, so that incoming letture have an unambiguous context.
19. As a homebrewer, I want concurrent or repeated start actions to preserve that single-active rule, so that accidental double actions do not create overlapping records.
20. As a homebrewer, I want an explicit waiting state when an active fermentazione has no associated letture yet, so that readings from a previous fermentazione are not presented as its history.
21. As a homebrewer, I want letture from the monitoring period to be associated with the corresponding fermentazione, so that I can follow that beer separately.
22. As a homebrewer, I want to end a fermentazione manually, so that I decide when its monitoring period is complete.
23. As a homebrewer, I want to see whether a fermentazione is active or concluded, so that its state is clear.
24. As a homebrewer, I want concluded fermentazioni to remain listed, so that I can find earlier monitoring sessions.
25. As a homebrewer, I want to open a concluded fermentazione and inspect its recorded values and charts, so that I can review what happened.
26. As a homebrewer, I want to start another fermentazione using the same pillola, so that I can reuse the equipment without mixing successive histories.
27. As a homebrewer, I want later readings to avoid overwriting the history of a concluded fermentazione, so that previous records remain trustworthy.
28. As a homebrewer, I want existing measurements to survive closing and reopening the browser, so that the browser is not responsible for storing my history.
29. As a homebrewer, I want fermentazioni and saved readings to survive application and container restarts, so that restarting HackBrew does not lose my records.
30. As a homebrewer, I want to direct my existing gateway to HackBrew's HTTP receiver, so that I can use the current device and gateway software.
31. As a homebrewer, I want the receiver to accept the gateway's current message fields, so that connecting HackBrew does not require changes to the external project.
32. As a homebrewer, I want the gateway's density scale normalized correctly, so that a transmitted value near 1050 is displayed as SG near 1.050.
33. As a homebrewer, I want useful temperature, density and battery values retained when the gateway's gravity-velocity flag is false, so that an unrelated flag does not hide a valid lettura.
34. As a homebrewer, I want malformed or invalid readings handled explicitly, so that corrupt data does not silently enter the charts or replace good values.
35. As a homebrewer, I want repeated delivery of the same lettura to avoid creating duplicate history entries, so that retries or repeated requests do not distort the charts.
36. As a homebrewer, I want older readings to avoid replacing the latest displayed measurement, so that delayed delivery does not make the dashboard move backward in time.
37. As a homebrewer, I want delayed readings associated with their original monitoring period, so that an earlier fermentazione cannot contaminate the next one.
38. As a homebrewer, I want visibly outdated readings to retain their actual values and acquisition time, so that I can distinguish old measurements from fresh ones.
39. As a homebrewer, I want the dashboard to recover after its live connection is interrupted, so that reopening or reconnecting shows the latest stored state.
40. As a homebrewer, I want gaps in received data to remain distinguishable from measured data, so that the dashboard does not invent missing measurements.
41. As a homebrewer, I want clear feedback when an application operation fails, so that I know whether starting or ending a fermentazione succeeded.
42. As a homebrewer, I want the application and database to start together through Docker Compose, so that I can run HackBrew without manually coordinating its processes.
43. As a homebrewer, I want the frontend build and backend dependencies to be handled in containers, so that setting up HackBrew does not require installing Node or Python on the host.
44. As a contributor, I want to develop and run checks through containers, so that the development workflow follows the same Docker requirement as the application.
45. As a contributor, I want automated checks to exercise actual MongoDB persistence and the browser-visible flow, so that passing tests demonstrate that the agreed stack works together.
46. As a homebrewer, I want startup and run instructions to match the configured project commands, so that I can reproduce the documented setup.
47. As a homebrewer, I want the gateway to remain outside HackBrew's Docker setup, so that its Bluetooth and hardware requirements stay separate from the web application.
48. As a contributor, I want sample configuration and tests to avoid personal credentials and production data, so that the public repository is usable without exposing local secrets or damaging saved fermentazioni.

## Implementation Decisions

### Confirmed architecture and scope

- Implement the agreed stack: Vue 3 with Composition API, TypeScript and Vite; Python with FastAPI; MongoDB; Chart.js; and SSE for server-to-browser updates.
- Keep the application as a focused web application. Build modules for receiving and normalizing letture, managing the fermentazione lifecycle, storing and querying persisted state, and presenting the dashboard. Keep their interfaces small and avoid adding alternate database implementations or speculative extension frameworks.
- Compile the frontend inside a multi-stage Docker build and serve the compiled application from FastAPI. The normal runtime consists of an application container and a MongoDB container. Development may run Vite in a separate container for live reload.
- Use Docker Compose to coordinate the application and database, and persist MongoDB data in a named volume. Development, build and tests must be executable in containers. The only required application tooling on the host is Docker with Compose.
- Keep the gateway external. Configure it to send HTTP requests to the receiver without requiring extra telemetry fields or changes to its software.
- Target local development and verification for the first delivery. Provide explicit configuration for the gateway's destination address and application listening address. Internet hosting, remote exposure and login are later work.

### Gateway contract and normalization

- Receive the existing JSON message through an HTTP POST operation. Its current fields are `valid`, `gravity_velocity`, `temperature`, `specific_gravity`, `accel_x`, `accel_y`, `accel_z`, `battery` and `timestamp`. Do not require a device identifier, authentication header, fermentazione identifier or schema version that the existing gateway does not send.
- Treat temperature as Celsius and battery as percentage. Divide `specific_gravity` by 1000 to obtain ordinary SG. Retain enough precision in storage; display formatting must not change the underlying measurement.
- Interpret `timestamp` as Unix seconds, including its fractional part, assigned by the gateway at Bluetooth reception. Distinguish acquisition time from the application's HTTP receipt time and store instants consistently in UTC.
- Interpret `valid` as the validity of `gravity_velocity`, not as the validity of the entire lettura. Temperature, density and battery must remain usable when that flag is false. Acceleration and gravity velocity do not add new dashboard features to this delivery.
- Validate required measurement values and timestamps before storage. Reject malformed JSON, missing required measurements, non-finite numbers and out-of-range battery values with a clear client error. Basic validation must not be presented as proof of sensor calibration or physical measurement accuracy.
- A successful ingestion response must mean that the accepted lettura has been persisted as required. Database errors must not be reported as successful delivery.

### Fermentazione lifecycle and persistence

- Represent a fermentazione with a stable identifier, a non-empty user-provided name, a start instant and an optional end instant. Its observable lifecycle is active followed by concluded. Creating and starting the named fermentazione can be one user action; no separate draft lifecycle is required.
- Enforce the single-active rule using a database-backed invariant that remains correct across concurrent requests and application restarts. A new start while another fermentazione is active must return a clear conflict rather than silently concluding the existing one.
- Persist the latest accepted lettura independently of the fermentazione history, so it remains available for diagnostics when none is active. Keep only this latest diagnostic state rather than accumulating unassigned history.
- Store historical letture with their associated fermentazione and acquisition instant. For the first delivery, regular MongoDB collections are a suitable implementation default; choosing MongoDB does not itself require time-series collections.
- Use the gateway acquisition time to associate a lettura with a known monitoring interval: start inclusive and end exclusive. A late arrival that belongs to an earlier interval may be stored in that earlier fermentazione; measurements acquired outside all monitoring intervals update only the latest diagnostic state. This clarifies the previously discussed association of delayed readings.
- Make repeated delivery of an identical lettura idempotent. Use the available timestamp and measurement content to identify repetition; do not depend on a gateway-supplied event identifier. Older letture may update the appropriate history but must not replace a newer latest lettura.
- Concluding a fermentazione preserves its associated measurements and frees the active slot. Future readings are associated according to their acquisition time, rather than appended indiscriminately to the last concluded fermentazione.
- Read persisted state on application startup and page load. Browser memory and the live event connection are not the system of record.

### Dashboard and live behaviour

- Provide the agreed summary quantities, acquisition time, active-fermentazione state, density and temperature trends, and access to concluded fermentazioni and their historical readings. Stored battery measurements remain available with the other values.
- Distinguish no measurements yet, no active fermentazione, active fermentazione awaiting readings, current readings, outdated readings and recoverable operation errors. Preserve the latest known values with their timestamp when data becomes outdated.
- Use a configurable data-freshness threshold. Five minutes is the initial engineering default, to be adjusted when the actual pillola cadence is verified; it is not a claim about the device's transmission interval. An outdated reading indicates data freshness, not proof that a particular hardware component is offline.
- Deliver new persisted state to connected browsers through SSE. On initial load or reconnection, fetch current state and relevant history so missed live notifications do not leave the dashboard permanently out of date.
- Keep charts chronologically ordered and bound the data transferred or rendered when necessary for mobile usability, while preserving saved source measurements. Do not fabricate samples to fill missing periods or present interpolated data as measurements.
- Use responsive layouts and usable controls for both computer and phone viewports. No visual theme, colour palette, component library or alternate-layout prototype has been approved; those are implementation/design choices within these functional requirements.
- Document the actual configured setup, development, build and test commands. Include placeholder configuration and ignore local secrets, generated artifacts and runtime data.

## Testing Decisions

- **Primary seam, confirmed with the user:** test the externally visible behaviour of the running HackBrew application. Submit deterministic gateway-format letture through its public HTTP receiver, perform lifecycle operations through its normal interfaces, and verify public responses, the event stream and the browser-visible result. This is one application-level seam, not a separate test interface for every internal module.
- Use the real FastAPI application, real MongoDB storage in an isolated container and the built Vue application for end-to-end checks. Replace the external Bluetooth gateway with deterministic HTTP input at its existing integration boundary. Neither the pillola hardware nor the external gateway implementation is under test.
- Prefer API-level integration checks through that same public boundary for normalization, validation, chronology, duplication, lifecycle conflicts and persistence. Use browser end-to-end checks for displayed quantities, automatic updates, empty and outdated states, history selection and responsive interaction. Pytest and Playwright are suitable test-runner defaults for these roles.
- A good test observes a result a caller or homebrewer depends on: a stored lettura returned by a query, one active fermentazione, a value shown in the agreed unit, a preserved history or an explicit failure. Avoid assertions about internal call order, private helpers, CSS class names, framework internals or a particular collection arrangement.
- Cover the complete happy path: start a named fermentazione, submit a gateway-format lettura, observe normalized values and charts without refreshing, conclude it, start the next one and verify that both histories remain separate.
- Cover diagnostics: show an empty state initially, accept readings while no fermentazione is active, show only the latest diagnostic lettura, then start a fermentazione without copying earlier diagnostic measurements into its history.
- Cover protocol edge cases: SG normalization, `valid=false` with useful measurements, malformed input, non-finite or invalid quantities, repeated messages, out-of-order arrivals and delayed readings at start/end boundaries.
- Cover lifecycle consistency: competing start requests, starting while one fermentazione is active, ending the active fermentazione and preserving historical records across later starts. Verify observable invariants through the application rather than relying on mocked persistence.
- Cover reliability within HackBrew's scope: preserve data after restarting the application against the same MongoDB volume, recover the browser after an SSE interruption, keep old values visibly outdated, and avoid acknowledging a successful write when MongoDB is unavailable.
- Run representative browser flows at desktop and phone viewport sizes. Assert usable controls, visible values and accessible historical information, rather than fixing every pixel of an unapproved visual design.
- Keep test data and storage isolated from the homebrewer's persistent volume. Tests must run through the Docker workflow and must not require the user's actual hardware, GitHub credentials or production data.
- There is no prior implementation, test suite or established testing pattern in the repository. These checks establish the first test coverage; no existing tests can be cited as prior art. Building a UI prototype and testing prototype implementation details are not prerequisites for this specification.

## Out of Scope

- Running, modifying, repairing or dockerizing the external Bluetooth gateway or changing pillola firmware.
- Adding gateway authentication, durable buffering, retransmission or recovery of readings that the existing gateway has already discarded.
- Internet deployment, reverse-proxy and domain setup, remote hosting configuration, TLS setup and GitHub login. The future intended user is the GitHub account LucaPalumbo, but authentication is explicitly deferred.
- Multiple users, public registration, multiple simultaneous fermentatori or multiple active fermentazioni.
- Temperature-control commands, actuators, automatic fermentation completion, notifications and alarms, recipe management, ABV/attenuation calculations and predictive analytics.
- Data export/import, bulk editing, historical data deletion, a full calibration workflow or interpreting acceleration and gravity velocity as additional dashboard features.
- Building three design variants or treating a UI prototype as production implementation. No prototype has been created or selected in this conversation.
- Requiring a specific cloud service or a host installation of Node, Python or MongoDB to use the Docker workflow.

## Further Notes

- HackBrew is a temporary product/repository name. Avoid unnecessary coupling to it in data formats or integration contracts.
- The functional scope, stack and application-level testing seam have been confirmed with the user.
- The project currently contains planning and agent documentation, with no application source, build configuration, Docker setup, tests or UI prototype. This specification describes work to implement, not features already delivered.
- The confirmed external project is [RaptPillGateway-ble-http](https://github.com/LucaPalumbo/RaptPillGateway-ble-http). Its inspected commit is `0bfc4a7fbbcfc2f231f75452d194de86677d46e2`. The current contract has no device or measurement identifier and no configurable authentication header.
- Interpretation of SG scale, battery percentage and the gravity-velocity flag was cross-checked against the original [rapt-ble parser and protocol fixtures](https://github.com/sairon/rapt-ble), commit `1473743be0d6dc9c151aae64588e7feffe7147c6`. Derived fixture examples are synthetic inputs, not captured readings from the user's actual pillola.
- A real gateway-message check remains part of integration verification when hardware is available. It should confirm the observed units, clock and reading cadence without blocking implementation of the documented contract.
- The receiver cannot reconstruct measurements discarded before they reach HackBrew. The application will preserve accepted data and show its freshness, while gateway reliability improvements remain separate work.
- The technical defaults above clarify previously open details about timestamps, duplicates, validation and freshness. Exact dependency versions, collection/index arrangement and interface route names are implementation choices; they must satisfy the observable behaviour and tests described here.
