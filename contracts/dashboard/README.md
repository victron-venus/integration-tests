# Dashboard boundary contract v1.0.0

Canonical schemas and fixtures live here. Python/NAS, Go/Cerbo, shared Vue SPA
and Tauri vendor identical `v1` files, record SHA-256 plus this source revision,
and execute the fixtures against their real flag key/value adapters in CI.
Consumers must update the full fixture set together; a local change is not a
new shared version. Schema IDs select this wire contract; they do not require a
new envelope or change existing MQTT topics. Missing version metadata remains
the legacy v1 transport during migration.

The telemetry schema covers the shared controller/EV subset of the existing
flat dashboard payload. Unknown fields stay forward compatible. Unknown or
invalid flag values become null/absent, never confirmed off. Canonical flags
use bare keys; `input_boolean.` is a legacy alias, while `switch.` remains HA.
Legacy booleans accept finite 0/1 and case/space normalized true/false/on/off.
Native Cerbo measurements retain their ownership; controller flags do not
provide evidence for hardware Mode/SocLimit semantics.

The command schema deliberately defines absolute on/off `inverter/cmd/toggle`
commands for the seven controller flags. Other device writes, HA commands,
implicit toggles, and water controls are outside v1's qualified command subset.
A transport acknowledgement does not establish physical actuator acceptance.

Power is W, SoC is percent, except the documented legacy `ev_charging_kw`
wallbox field. Null/absent/availability=false means unknown; measured zero stays
zero. Breaking units, ownership or control meanings require a new major schema
and new shared fixtures. Additive optional fields can advance a minor version.
