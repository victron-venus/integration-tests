# Physical Cerbo qualification

The Ubuntu Docker matrix does not qualify hardware. This runner is opt-in and
has no enabled device inventory. Its default is an offline plan, never SSH.

Run its negative gate tests with `python3 -m pytest hardware/`. Copy
`inventory.example.json` to `/etc/victron-lab/` (or under `hardware/` for a local dry-run) and review every identity and
threshold with the lab operator. The example numbers are initial gate targets,
not established hardware performance. Use a dedicated lab meter service, not a
production household installation. `svstat`, `svc`, Python 3.11+, paho-mqtt 2.x
and the exact installed inverter-control native client are prerequisites.
The `expected` identity values are exact strings returned by that client's
`get_value`, including its scalar representation. Controller, Venus firmware,
target and BMS identities must match before testing. Paths differ by device;
the [Victron D-Bus contract](https://github.com/victronenergy/venus/wiki/dbus)
does not guarantee every path on every device.

```sh
python3 hardware/device_runner.py --inventory /etc/victron-lab/cerbo-lab.json --output reports/plan-1
python3 hardware/device_runner.py --inventory /etc/victron-lab/cerbo-lab.json --output reports/preflight-1 --execute --preflight --ack-device cerbo-lab
python3 hardware/device_runner.py --inventory /etc/victron-lab/cerbo-lab.json --output reports/soak-1 --execute --ack-device cerbo-lab
```

Execution additionally requires `enabled: true`, `allow_meter_loss: true`, and
`cleanup_allow: ["restore_meter_service"]`. Host keys must already be installed;
SSH never accepts an unknown key. Inventory paths are confined to `hardware/` or `/etc/victron-lab/`; evidence stays
under `reports/`. The reviewed installation is `/data/inverter-control` using
`/usr/bin/python3`. No package installation or deployment occurs.
The runner sends its reviewed Python source through SSH, records its hash, and
requires the expected installed native-client source hash. Pin the external
meter with `GRID_EXPECTED_SERVICE` and the site's phases, and configure/review
`GRID_LOSS_HOLD_SECONDS` before the run. Defaults can exceed the example 15-second
zero deadline; the runner does not change controller policy to make tests pass.

Evidence includes identity preflight, non-retained controller state sampled at 1 Hz, rolling
cycle/write p95/p99, RSS drift between the first/last 10% of samples, reconnect
durations, the meter stop, accepted-zero observation, recovery and cleanup.
Percentiles are the **maximum observed rolling-window percentiles**, not a
fabricated percentile of the whole run. A minimum one-hour soak, positive
thresholds, monotonically advancing controller uptime, bounded message gaps,
and at least 100 fresh samples are required. Update inverter-control to emit
`setvalue_ms.p99`. Lack of that metric fails qualification.

The reconnect storm disconnects **only a separate read-only NativeDbusClient
probe** through the installed production client's failure/reconnect path. It
does not restart the global D-Bus or the production controller. It proves that
client's reconnect path under device load; production service restart and
subscription replay qualification remain separate scenarios. The controller
soak detects a stalled loop through absent/stale state or non-advancing uptime.
The meter-loss scenario stops the explicit lab meter service with `svc -d` and
requires `grid_control_valid=false`, `grid_loss_state=zero` and
`grid_loss_zero_applied=true` before restoration. This records the controller's
accepted command diagnostic, not proof of physical power or BMS semantics.

Cleanup has no general device authority: it may only `svc -u` the single
previously running meter service whose stop this process journaled. Failures,
timeouts and signals enter `finally`; cleanup failure fails the gate. No files,
containers, other services or hardware settings are removed/restored. Power loss,
SIGKILL or lost SSH can prevent confirmed cleanup: independently check the meter
service before resuming operation. This is why the scenario requires an attended
lab and has no scheduled or pull-request trigger.

For Actions, provision a dedicated `cerbo-lab` self-hosted runner, inventory at
`/etc/victron-lab/<device>.json`, pinned known_hosts and the `hardware-lab`
environment with required reviewers. The workflow only runs manually from main,
serializes device access and always uploads evidence. Organization runner and
environment permissions must prohibit untrusted PR jobs; YAML alone cannot
configure those server-side controls. Dry-run/preflight outputs explicitly do
not qualify hardware. Keep evidence plus its SHA manifest with the release
candidate; a green Docker matrix cannot replace missing physical evidence.
