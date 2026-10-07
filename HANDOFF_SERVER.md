> **7 October update — confirmed one-way network:** Read `deployment/ONE_WAY_MYSQL_UPDATE_20261007.md` first. Dashboard .69 SELECTs Operation .73:3306; Operation never connects back to .69. Update .73 export/migrations/grants first, then .69 receiver/UI. Merge new configuration keys into existing Server `.env`; preserve installed secrets/services/models/Profiles. The update guide supersedes old bridge and initial model-install instructions. Local verification is not Server acceptance.

# Server installation handoff — 6 October 2026

## Start here

Owner instruction: **“Set up ระบบนี้ให้หน่อย”** authorizes installation and service setup on the target Server. Read this document before older handoffs. Inspect hostname/IP, OS, existing services, MySQL, current schemas and installation directories; preserve source readings, Profile registries, existing credentials and service state. Record the previous service/config/model revision for rollback. Do not ask the owner again for permission to include configuration/secrets in these private `_final` repositories: that permission was explicit. Never print credentials in logs/reports. Older “never commit .env” instructions are superseded for these private repositories only.

## Deployment map

| Component | Server | MySQL/data responsibility |
|---|---|---|
| Dashboard | 10.195.17.69 | Local `predictive_maintenance` metadata/users/work orders; remote SELECT of raw readings on .73:3306 |
| Operation API and one detector Worker | 10.195.17.73 | Local `ht9046mx_analytics`, frozen models, unified `ht9046mx_events`; raw source SELECT |
| Compressor source | 10.195.17.73:3306 | `ht9046mx_iot.ht9046mx_readings` |
| Vacuum source | 10.195.17.73:3306 | `vacuum_pump_db.vacuum_pump_readings` |

Compressor and Vacuum have separate schemas/column contracts; never reuse Compressor fields for Vacuum. Compressor machine/module/timestamp identity must remain intact. Dashboard gets raw readings and the optional existing derived health contract via MySQL, not an Operation HTTP telemetry endpoint. Dashboard now pulls ordered STATUS/EVENT exports from Operation analytics using SELECT-only access; no reverse bridge connection is required. Current frozen Fleet worker is Shadow and does not manufacture `compressor_health_scores` or healthy scores. If no verified producer populates that optional table, Dashboard must show unavailable ML rather than fabricated Good. Vacuum processing remains Dashboard-owned.

## Included private configuration

Root `.env` is the prepared target config; `deployment/configuration_archive/` preserves existing real local config/credential documents for comparison. Preserve all these files in this private repository. Database values are the existing project credentials, not proof of grants on the two target Servers. Check them locally without printing passwords; compare archived Server credential instructions and existing Server configuration. If an account is not valid remotely, create/use an appropriate account through the Server's existing MySQL admin access and persist its actual values privately. Do not invent credentials or claim connectivity before testing.

Use source accounts with SELECT-only access on the named telemetry schemas. Dashboard metadata and Operation analytics accounts need only their respective writes/additive DDL. Restrict MySQL ingress on .73 to .69 and the intended producers. Dashboard also needs SELECT on the three Operation export tables listed in the update guide. No .69 ingress from .73 is needed. Inspect current firewall/bind-address/grants before changing; keep current required access. Never DROP/TRUNCATE source tables. Back up metadata before additive migrations. No local source DB dump, mock records, test Active pointer or virtual clock is included.

Clone this private repository using authenticated Git access. Install Git LFS, then run `git lfs install`, `git lfs pull`, and `git lfs fsck` before tests or model loading; GitHub ZIP download alone may contain LFS pointers instead of model/data files. Use Python 3.12 and Node supported by the locked Vite version (Node >=22.12 is suitable for both). Create a dedicated venv. Commands below run at repository root using that venv Python and the same root `.env`; service processes must use the same working directory. OS is not assumed: use systemd on Linux or existing Windows service/task infrastructure. Background Windows processes must be hidden. Configure startup at boot, automatic restart/backoff, rotating logs and one instance per service. Do not use temporary foreground terminals as installed services.

Serve built frontends through the existing reverse proxy. APIs stay loopback behind the proxy. Operation's review/management endpoints require authenticated gateway identity and roles; a typed approver header is not authentication. Configure this before LAN exposure. Proxy `/api` without stripping its prefix; Dashboard `/ws` needs WebSocket upgrade and adequate timeouts. Use same-origin browser API paths. Register actual external origins in `.env` when the existing proxy uses a hostname/HTTPS.

## Completion and rollback

Record Server hostname/IP/OS, Git commit, model checksum/version, resolved working directories/services, redacted DB mapping and actual test outcomes in `deployment/SERVER_ACCEPTANCE.md`. Verify clock/timezone Asia/Bangkok, raw timestamp/state/column mapping, source freshness, restart/boot persistence, repeated source overlap without duplicate events, and simultaneous machine/module tabs. Compare query/render latency and memory under actual source load; previous warm local HTTP results do not prove cold Server performance. Report unresolved source contracts and missing Active coverage honestly.

Roll back service code/config to the recorded revision and the Fleet pointer through revision CAS; do not roll back by deleting telemetry/Profiles. Setup alone never approves a Profile, certifies Normal, changes SV scope or converts a Shadow model to live alerts. Run Active approval through the existing manual workflow with real eligible evidence.

## Operation .73 installation

Private repository: https://github.com/Bookkapp/CompressorML_and_AutomaticCalibration_final
Companion: https://github.com/Bookkapp/Compressor_and_VacuumPump_final

Read `AGENTS.md`, `README_System.md`, `SOT.md`, `HANDOFF.md`, `Project.md`, `Roadmap.md`, then `deployment/SERVER_WORKER_HANDOFF_20261006.md`. This root handoff supersedes that document's old instruction to omit development secrets from private source control. Historical checkpoint descriptions are not current Server acceptance evidence.

```sh
python -m venv .venv
# Activate .venv for your OS, then:
python -m pip install -r apps/api/requirements.txt
npm --prefix apps/web ci
npm --prefix apps/web run build
python -m pytest apps/api/tests
```

Ensure the analytics DB exists and accounts/grants work. Review additive DDL against existing schemas, then:

```sh
python -m apps.api.app.context_migrate --allow-remote
python -m apps.api.app.qualified_detector --allow-remote --migrate-only
python -m apps.api.app.fleet_bundle --store runtime/fleet-stable install deployment/models/fleet-stable-v1-586e67981fc6d695467f0d01.zip
python -m apps.api.app.fleet_bundle --store runtime/fleet-stable status
```

Verify `deployment/models/SHA256SUMS` before install; the loader additionally validates the package. Never overwrite an existing model store. Read its actual pointer revision, then switch the packaged version to Shadow through CAS (empty store expected revision=0):

```sh
python -m apps.api.app.fleet_bundle --store runtime/fleet-stable switch fleet-stable-v1-586e67981fc6d695467f0d01 --expected-revision 0 --actor server-setup --reason "Owner-authorized initial Server Shadow setup"
python -m apps.api.app.qualified_detector --allow-remote
python -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000 --workers 1
python -m apps.api.app.worker --detector-only
```

Install API and detector Worker as separate persistent services, one scheduler instance. API tabs do not create Worker instances. Do not start the legacy automatic training scheduler. Build output `apps/web/dist/` is served by the proxy on .73; proxy `/api` and `/health` to loopback8000. Configure authentication/roles at that proxy first. Root `.env` preserves bounded detector/Fleet Shadow and disables the reverse bridge; the Dashboard owns pull delivery and operational Alert dedupe. Operation reads Compressor; Vacuum schema access belongs to Dashboard. Worker/export writes are local derived evidence only, never raw sensor rows.

Frozen runtime package is sufficient for inference and portable installation. It is not an Active Context registry DB backup. Existing target Profiles must be preserved. No real Profile approval is included. Future retraining requires fresh reviewed compatible data, confirmed contracts, prepared intake/minutes/events and independent validation; optional prepared history is not a production source DB dump. Do not attempt retraining on absent local notebook evidence or treat packaged historical study reports as prospective data.

Current Transition library has zero conservatively admitted donor groups. Unsupported SV/Valve regimes remain NOT_EVALUATED; controls/transitions still enter unified Event history. Fleet Shadow cannot fill missing verified Reference/Engineer/state/pressure-basis evidence by assertion. psi was confirmed, but psig/psia and controller/service contracts require actual equipment evidence for Active. Validate reconnect/retry/late-arrival handling, event identities and pointer persistence with real Server data; test failures in an isolated QA schema.

