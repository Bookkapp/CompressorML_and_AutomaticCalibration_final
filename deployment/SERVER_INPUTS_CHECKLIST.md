# Server inputs checklist — both v1 systems


This file is safe to commit: it contains names and placeholders only. Real values belong in the ignored local file `deployment/SECRETS_SERVER_LOCAL.md` and in the Server secret store.

## Topology to confirm

| Item | Intended value |
| --- | --- |
| Application/Web server | `10.195.17.69` |
| MySQL server | `10.195.17.73:3306` |
| ML repository | `Bookkapp/CompressorML_and_AutomaticCalibration_v1` |
| Dashboard repository | `Bookkapp/Compressor_and_VacuumPump_v1` |
| ML API/Web | `127.0.0.1:8000` / `127.0.0.1:8080` behind the approved reverse proxy |
| Operations Dashboard | `0.0.0.0:5001` behind the approved reverse proxy |
| Application timezone | `Asia/Bangkok` |


## Files required on the Server

Clone both private repositories and check out `main` or the immutable tag `v1.0.0-current-architecture`:

```bash
git clone git@github.com:Bookkapp/CompressorML_and_AutomaticCalibration_v1.git
git clone git@github.com:Bookkapp/Compressor_and_VacuumPump_v1.git
```


The ML repository requires the Git LFS objects:

```bash
cd CompressorML_and_AutomaticCalibration_v1
git lfs install
git lfs pull
git lfs ls-files
```

Required deployment files are:

- ML: `deployment/docker-compose.analytics.yml`, SQL migrations in `deployment/`, `apps/api/Dockerfile`, `apps/web/Dockerfile`, and `deployment/.env.analytics` created from the example.
- Dashboard: `requirements.txt`, `package-lock.json`, `schema.sql`, built `public/`, and root `.env` created from `.env.example`.


## Database accounts to create

| User | Used by | Minimum access |
| --- | --- | --- |
| `ht9046mx_runtime` | ML API/scoring worker | read/write analytics; read raw telemetry; controlled writes to Compressor Dashboard tables and the v1 compatibility output |
| `ht9046mx_source_ro` | calibration source connection | `SELECT` only on `ht9046mx_iot.ht9046mx_readings` |
| `predictive_app` | Dashboard API | read/write `predictive_maintenance` only |
| `vacuum_reader` | Dashboard telemetry reader | `SELECT` only on `vacuum_pump_db.vacuum_pump_readings` |
| `compressor_reader` | Dashboard telemetry/score reader | `SELECT` only on `ht9046mx_iot.ht9046mx_readings` and the agreed health-output table |



If the v1 compatibility location is temporarily accepted, the DBA must create this table before granting the two table-level permissions:

```sql
CREATE TABLE IF NOT EXISTS ht9046mx_iot.compressor_health_scores (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  machine_number VARCHAR(64) NOT NULL,
  module_id VARCHAR(64) NOT NULL,
  recorded_at DATETIME(6) NOT NULL,
  health_score DOUBLE NOT NULL,
  `condition` VARCHAR(32) NOT NULL,
  model_version VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_compressor_health_identity
    (machine_number, module_id, recorded_at, model_version),
  KEY idx_compressor_health_latest
    (machine_number, module_id, recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

GRANT SELECT, INSERT ON ht9046mx_iot.compressor_health_scores
  TO 'ht9046mx_runtime'@'<APP_SERVER_IP>';
GRANT SELECT ON ht9046mx_iot.compressor_health_scores
  TO 'compressor_reader'@'<APP_SERVER_IP>';
```

## ML environment file

Create `CompressorML_and_AutomaticCalibration_v1/deployment/.env.analytics` with permissions restricted to the service account:

```dotenv
HT9046MX_APP_MODE=live
HT9046MX_PROJECT_ROOT=/opt/CompressorML_and_AutomaticCalibration_v1
HT9046MX_API_CORS_ORIGINS=http://10.195.17.69:8080

HT9046MX_ANALYTICS_DB_HOST=10.195.17.73
HT9046MX_ANALYTICS_DB_PORT=3306
HT9046MX_ANALYTICS_DB_NAME=ht9046mx_analytics
HT9046MX_ANALYTICS_DB_USER=ht9046mx_runtime
HT9046MX_ANALYTICS_DB_PASSWORD=<FROM_SECRET_STORE>

HT9046MX_SOURCE_DB_HOST=10.195.17.73
HT9046MX_SOURCE_DB_PORT=3306
HT9046MX_SOURCE_DB_NAME=ht9046mx_iot
HT9046MX_SOURCE_DB_USER=ht9046mx_source_ro
HT9046MX_SOURCE_DB_PASSWORD=<FROM_SECRET_STORE>
HT9046MX_SOURCE_TABLE=ht9046mx_readings
HT9046MX_SOURCE_TIMESTAMP_COLUMN=recorded_at
HT9046MX_SOURCE_MACHINE_COLUMN=machine_number
HT9046MX_SOURCE_GLOBAL_STATUS_COLUMN=Status
HT9046MX_SOURCE_HP1_TEMPLATE=Hp_1st_{module}
HT9046MX_SOURCE_LP1_TEMPLATE=Lp_1st_{module}
HT9046MX_SOURCE_HP2_TEMPLATE=Hp_2nd_{module}
HT9046MX_SOURCE_LP2_TEMPLATE=Lp_2nd_{module}
HT9046MX_SOURCE_VALVE_TEMPLATE=Valve_{module}
HT9046MX_SOURCE_TEMP_HIGH_TEMPLATE=TempHi_{module}
HT9046MX_SOURCE_TEMP_LOW_TEMPLATE=TempLo_{module}
HT9046MX_SOURCE_MODULE_STATUS_TEMPLATE=Status_{module}
HT9046MX_SOURCE_BUSY_TEMPLATE=Busy_{module}
HT9046MX_SOURCE_SV_TEMPLATE=SV_{module}
HT9046MX_SOURCE_COMPRESSOR_ON_STATUS=Run
HT9046MX_SOURCE_MODULE_ON_STATUS=On
HT9046MX_SOURCE_BUSY_NORMAL_VALUES=0,False,Off
HT9046MX_SOURCE_SV_OFF_VALUES=Off,0,False
HT9046MX_SOURCE_TIMEZONE=<CONFIRM_IANA_TIMEZONE>
HT9046MX_SOURCE_PRESSURE_UNIT=<CONFIRM_PSIG_OR_PSIA>
HT9046MX_PROFILE_WINDOW_CONTRACT=qualified_observed_1m
HT9046MX_QUALIFIED_1M_PREVIEW_ENABLED=false

HT9046MX_DASHBOARD_REFRESH_MINUTES=5
HT9046MX_SCORING_INTERVAL_MINUTES=1
HT9046MX_TECHNICIAN_FEEDBACK_START_AT=<SET_AT_ACTUAL_GO_LIVE_WITH_OFFSET>
HT9046MX_ALERT_DATETIME_TIMEZONE=<CONFIRM_IANA_TIMEZONE_OF_DETECTED_AT>

# Change to true only after source/time/unit/codebook/service evidence is approved.
HT9046MX_PROFILE_CANDIDATE_ENABLED=false
HT9046MX_PROFILE_HISTORY_DAYS=30
HT9046MX_PROFILE_SHADOW_DAYS=3
HT9046MX_PROFILE_MIN_CALIBRATION_DAYS=7
HT9046MX_PROFILE_MIN_CALIBRATION_WINDOWS=200
HT9046MX_PROFILE_MIN_SHADOW_WINDOWS=200
HT9046MX_PROFILE_RETRY_MIN_NEW_DAYS=3
HT9046MX_PROFILE_STATE_CONTRACT_VERSION=<APPROVED_VERSION>
HT9046MX_PROFILE_CONTROLLER_CODEBOOK_VERSION=<APPROVED_VERSION>
HT9046MX_PROFILE_SERVICE_EPOCH_VERSION=<APPROVED_VERSION>

HT9046MX_PROFILE_CANDIDATE_CRON=0 2 * * *
HT9046MX_MODEL_CANDIDATE_CRON=0 3 * * 0
HT9046MX_SHADOW_SCORE_CRON=* * * * *
HT9046MX_PROFILE_CANDIDATE_COMMAND=
# Owner-selected rule-only path: leave ARX/model-candidate command empty.
HT9046MX_MODEL_CANDIDATE_COMMAND=
# Keep scoring command disabled until a durable version-matched one-minute
# live writer, authentication, rollback and fresh Server gates pass.
HT9046MX_SHADOW_SCORE_COMMAND=
```


## Dashboard environment file

Create `Compressor_and_VacuumPump_v1/.env`:

```dotenv
APP_NAME=ADI HT9046 Predictive Maintenance
APP_HOST=0.0.0.0
PORT=5001
APP_TIMEZONE=Asia/Bangkok
APP_ENV=production
SECRET_KEY=<FROM_SECRET_STORE_MIN_32_CHARS>
ALLOWED_ORIGINS=https://<APPROVED_DASHBOARD_HOSTNAME>

DB_HOST=10.195.17.73
DB_PORT=3306
DB_USER=predictive_app
DB_PASSWORD=<FROM_SECRET_STORE>
DB_NAME=predictive_maintenance
DB_CHARSET=utf8mb4

TELEMETRY_ENABLED=true
TELEMETRY_DB_HOST=10.195.17.73
TELEMETRY_DB_PORT=3306
TELEMETRY_DB_CHARSET=utf8mb4
TELEMETRY_POLL_INTERVAL_SECONDS=5
TELEMETRY_CONNECT_TIMEOUT_SECONDS=10
TELEMETRY_READ_TIMEOUT_SECONDS=30

VACUUM_DB_USER=vacuum_reader
VACUUM_DB_PASSWORD=<FROM_SECRET_STORE>
VACUUM_SCHEMA=vacuum_pump_db
VACUUM_TABLE=vacuum_pump_readings
VACUUM_DEVICE_COLUMN=devices_id

COMPRESSOR_DB_USER=compressor_reader
COMPRESSOR_DB_PASSWORD=<FROM_SECRET_STORE>
COMPRESSOR_SCHEMA=ht9046mx_iot
COMPRESSOR_TABLE=ht9046mx_readings
COMPRESSOR_MACHINE_COLUMN=machine_number
COMPRESSOR_TIMESTAMP_COLUMN=recorded_at
COMPRESSOR_SENSOR_SCALE=1

COMPRESSOR_HEALTH_ENABLED=false
COMPRESSOR_HEALTH_SCHEMA=ht9046mx_iot
COMPRESSOR_HEALTH_TABLE=compressor_health_scores
COMPRESSOR_HEALTH_MACHINE_COLUMN=machine_number
COMPRESSOR_HEALTH_MODULE_COLUMN=module_id
COMPRESSOR_HEALTH_TIMESTAMP_COLUMN=recorded_at
COMPRESSOR_HEALTH_SCORE_COLUMN=health_score
COMPRESSOR_HEALTH_CONDITION_COLUMN=condition
COMPRESSOR_HEALTH_MODEL_COLUMN=model_version

MQTT_ENABLED=false
ADMIN_USERNAME=ADIadmin
ADMIN_PASSWORD=<FROM_SECRET_STORE_MIN_12_CHARS>
USER_USERNAME=ADImaintenance
USER_PASSWORD=<FROM_SECRET_STORE_MIN_12_CHARS_DIFFERENT_FROM_ADMIN>
SEED_DEMO_DATA=false
```

Keep `COMPRESSOR_HEALTH_ENABLED=false` until the output table, freshness/timezone semantics and runtime model provenance have passed staging. Enabling it early would present unapproved output as operational evidence.

## Migration order

1. Back up `predictive_maintenance` and take a schema-only snapshot.
2. Create `ht9046mx_analytics` and application users through the DBA.
3. Apply ML migrations in order:
   - `deployment/mysql_shadow_schema.sql`
   - `deployment/mysql_phase6_calibration_registry.sql`
   - `deployment/mysql_phase8_confirmation_only.sql`
4. Do **not** apply `mysql_phase8_label_loop.sql`; it is the superseded cause-taxonomy design.
5. Apply/review Dashboard `schema.sql` on staging.
6. Verify required indexes, foreign keys and table ownership.

## Start and verify

ML stack:

```bash
cd /opt/CompressorML_and_AutomaticCalibration_v1/deployment
docker compose --env-file .env.analytics -f docker-compose.analytics.yml build
docker compose --env-file .env.analytics -f docker-compose.analytics.yml up -d
docker compose -f docker-compose.analytics.yml ps
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8080/health
```

Dashboard:

```bash
cd /opt/Compressor_and_VacuumPump_v1
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
npm ci
npm run frontend:build
python -m pytest -q
python -m uvicorn app.main:app --host 0.0.0.0 --port 5001
```

Before enabling production alerts, verify source reachability, `SELECT`-only source privileges, timezone and pressure units, **one-minute qualified** idempotent replay, profile shadow graph, approval/rollback audit, one-owner Compressor alert behavior, Dashboard freshness, restart recovery, p95/p99 load and backup restore.

## Current blockers

- Historical rows written before the scorer-provenance correction retain an incorrect `ARX-Ridge__seed_13` label and must be excluded from ARX validation. The owner selected a rule-only path; an ARX release is **not** a launch prerequisite. The new one-minute scorer is read-only preview; durable live writes still need exact Active-Profile parity, fail-closed unsupported-data behavior, target-server shadow, alert-budget and rollback acceptance before production alerting. See `deployment/QUALIFIED_1M_CALIBRATION_CHECKPOINT.md`.
- Source/detected-at timezone semantics must be confirmed rather than assumed.
- Profile state/codebook/service-epoch versions require owner approval.
- The health-output table location in the raw schema should be corrected or narrowly permissioned.
- A GitHub snapshot is not deployment approval; staging and UAT remain required.

## Change log

- 2026-09-25 — Changed the sample Server profile/scoring commands to disabled-by-default, removed ARX as a release prerequisite and linked the rule-only parity/approval gates. No live environment or database was changed.
