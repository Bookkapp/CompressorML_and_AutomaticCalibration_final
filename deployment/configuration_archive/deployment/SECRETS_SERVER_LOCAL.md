
Generated: 2026-09-24 Asia/Bangkok
Scope: both v1 systems

## Fixed topology used in this handoff

- Application server: 10.195.17.69
- MySQL server: 10.195.17.73:3306
- ML repository: Bookkapp/CompressorML_and_AutomaticCalibration_v1
- Dashboard repository: Bookkapp/Compressor_and_VacuumPump_v1

If the ML worker runs from another host, the DBA must change the MySQL account host restriction from 10.195.17.69 to that exact host.

## Generated credential inventory

| Purpose | Username | Password |
| --- | --- | --- |
| ML analytics/runtime | ht9046mx_runtime | $runtimePw |
| ML source read-only | ht9046mx_source_ro | $sourcePw |
| Dashboard metadata | predictive_app | $predictivePw |
| Vacuum source read-only | acuum_reader | $vacuumPw |
| Compressor source/output read-only | compressor_reader | $compressorPw |
| Dashboard administrator | ADIadmin | $adminPw |
| Dashboard maintenance user | ADImaintenance | $userPw |
| Dashboard token signing key | SECRET_KEY | $secretKey |


## DBA SQL — review before execution

`sql
```sql
CREATE DATABASE IF NOT EXISTS ht9046mx_analytics
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS predictive_maintenance
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'ht9046mx_runtime'@'10.195.17.69' IDENTIFIED BY '238225401AEACA7BC1B3F375FB9A97219AD363C30225BC6D';
CREATE USER IF NOT EXISTS 'ht9046mx_source_ro'@'10.195.17.69' IDENTIFIED BY '3483879F3480BBE6808B44E553AD3B57173061E882EB9D18';
CREATE USER IF NOT EXISTS 'predictive_app'@'10.195.17.69' IDENTIFIED BY '5978AD15CAB23E8A82709BC03A58F753121F0C4B712BEFF3';
CREATE USER IF NOT EXISTS 'vacuum_reader'@'10.195.17.69' IDENTIFIED BY '5C515557E33A06087EF3868AB3089849E1B431B38EAC00C2';
CREATE USER IF NOT EXISTS 'compressor_reader'@'10.195.17.69' IDENTIFIED BY 'B7A8C17CEF718261DF3F90EAF24161B4236B22146E45FAA4';

GRANT SELECT ON ht9046mx_iot.ht9046mx_readings
  TO 'ht9046mx_source_ro'@'10.195.17.69';
GRANT SELECT ON ht9046mx_iot.ht9046mx_readings
  TO 'ht9046mx_runtime'@'10.195.17.69';
GRANT SELECT, INSERT, UPDATE ON ht9046mx_analytics.*
  TO 'ht9046mx_runtime'@'10.195.17.69';

GRANT SELECT, INSERT, UPDATE ON predictive_maintenance.pm_devices
  TO 'ht9046mx_runtime'@'10.195.17.69';
GRANT SELECT, INSERT, UPDATE ON predictive_maintenance.pm_modules
  TO 'ht9046mx_runtime'@'10.195.17.69';
GRANT SELECT, INSERT ON predictive_maintenance.pm_diagnostic_snapshots
  TO 'ht9046mx_runtime'@'10.195.17.69';
GRANT SELECT, INSERT, UPDATE ON predictive_maintenance.pm_alerts
  TO 'ht9046mx_runtime'@'10.195.17.69';

GRANT SELECT, INSERT, UPDATE, DELETE ON predictive_maintenance.*
  TO 'predictive_app'@'10.195.17.69';
GRANT SELECT ON vacuum_pump_db.vacuum_pump_readings
  TO 'vacuum_reader'@'10.195.17.69';
GRANT SELECT ON ht9046mx_iot.ht9046mx_readings
  TO 'compressor_reader'@'10.195.17.69';

-- v1 compatibility table. Prefer moving this output to ht9046mx_analytics
CREATE TABLE IF NOT EXISTS ht9046mx_iot.compressor_health_scores (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  machine_number VARCHAR(64) NOT NULL,
  module_id VARCHAR(64) NOT NULL,
  recorded_at DATETIME(6) NOT NULL,
  health_score DOUBLE NOT NULL,
  condition VARCHAR(32) NOT NULL,
  model_version VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_compressor_health_identity
    (machine_number, module_id, recorded_at, model_version),
  KEY idx_compressor_health_latest
    (machine_number, module_id, recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

GRANT SELECT, INSERT ON ht9046mx_iot.compressor_health_scores
  TO 'ht9046mx_runtime'@'10.195.17.69';
GRANT SELECT ON ht9046mx_iot.compressor_health_scores
  TO 'compressor_reader'@'10.195.17.69';

FLUSH PRIVILEGES;
```
`

If a user already exists, CREATE USER IF NOT EXISTS will not replace its password. The DBA must compare the existing secret-store entry and use ALTER USER only through the approved rotation procedure.

## ML .env.analytics

Target file: /opt/CompressorML_and_AutomaticCalibration_v1/deployment/.env.analytics

`dotenv
```dotenv
HT9046MX_APP_MODE=live
HT9046MX_PROJECT_ROOT=/opt/CompressorML_and_AutomaticCalibration_v1
HT9046MX_API_CORS_ORIGINS=http://10.195.17.69:8080

HT9046MX_ANALYTICS_DB_HOST=10.195.17.73
HT9046MX_ANALYTICS_DB_PORT=3306
HT9046MX_ANALYTICS_DB_NAME=ht9046mx_analytics
HT9046MX_ANALYTICS_DB_USER=ht9046mx_runtime
HT9046MX_ANALYTICS_DB_PASSWORD=238225401AEACA7BC1B3F375FB9A97219AD363C30225BC6D

HT9046MX_SOURCE_DB_HOST=10.195.17.73
HT9046MX_SOURCE_DB_PORT=3306
HT9046MX_SOURCE_DB_NAME=ht9046mx_iot
HT9046MX_SOURCE_DB_USER=ht9046mx_source_ro
HT9046MX_SOURCE_DB_PASSWORD=3483879F3480BBE6808B44E553AD3B57173061E882EB9D18
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
HT9046MX_SOURCE_TIMEZONE=REPLACE_WITH_CONFIRMED_IANA_TIMEZONE

HT9046MX_DASHBOARD_REFRESH_MINUTES=5
HT9046MX_SCORING_INTERVAL_MINUTES=5
HT9046MX_TECHNICIAN_FEEDBACK_START_AT=REPLACE_AT_ACTUAL_GO_LIVE_WITH_OFFSET
HT9046MX_ALERT_DATETIME_TIMEZONE=REPLACE_WITH_CONFIRMED_IANA_TIMEZONE_OF_DETECTED_AT

HT9046MX_PROFILE_CANDIDATE_ENABLED=true
HT9046MX_PROFILE_HISTORY_DAYS=30
HT9046MX_PROFILE_SHADOW_DAYS=3
HT9046MX_PROFILE_MIN_CALIBRATION_DAYS=7
HT9046MX_PROFILE_MIN_CALIBRATION_WINDOWS=200
HT9046MX_PROFILE_MIN_SHADOW_WINDOWS=200
HT9046MX_PROFILE_RETRY_MIN_NEW_DAYS=3
HT9046MX_PROFILE_STATE_CONTRACT_VERSION=REPLACE_WITH_APPROVED_VERSION
HT9046MX_PROFILE_CONTROLLER_CODEBOOK_VERSION=REPLACE_WITH_APPROVED_VERSION
HT9046MX_PROFILE_SERVICE_EPOCH_VERSION=REPLACE_WITH_APPROVED_VERSION

HT9046MX_PROFILE_CANDIDATE_CRON=0 2 * * *
HT9046MX_MODEL_CANDIDATE_CRON=0 3 * * 0
HT9046MX_SHADOW_SCORE_CRON=*/5 * * * *
HT9046MX_PROFILE_CANDIDATE_COMMAND=
HT9046MX_MODEL_CANDIDATE_COMMAND=
HT9046MX_SHADOW_SCORE_COMMAND=python -m apps.api.app.inference
```
`


## Dashboard .env

Target file: /opt/Compressor_and_VacuumPump_v1/.env

`dotenv
```dotenv
APP_NAME=ADI HT9046 Predictive Maintenance
APP_HOST=0.0.0.0
PORT=5001
APP_TIMEZONE=Asia/Bangkok
APP_ENV=production
SECRET_KEY=48C7F3416DD49B9BC9E0EB61A4DC489F8CBB94ED16CC20AD83479C9FCD9121A46B2D87D044CC327A770388A2835206F4
ALLOWED_ORIGINS=https://REPLACE_WITH_APPROVED_DASHBOARD_HOSTNAME

DB_HOST=10.195.17.73
DB_PORT=3306
DB_USER=predictive_app
DB_PASSWORD=5978AD15CAB23E8A82709BC03A58F753121F0C4B712BEFF3
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
VACUUM_DB_PASSWORD=5C515557E33A06087EF3868AB3089849E1B431B38EAC00C2
VACUUM_SCHEMA=vacuum_pump_db
VACUUM_TABLE=vacuum_pump_readings
VACUUM_DEVICE_COLUMN=devices_id

COMPRESSOR_DB_USER=compressor_reader
COMPRESSOR_DB_PASSWORD=B7A8C17CEF718261DF3F90EAF24161B4236B22146E45FAA4
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
ADMIN_PASSWORD=A7A7E1852EB1804D1F514F7093D315E6AD639FBB
USER_USERNAME=ADImaintenance
USER_PASSWORD=AB17519B81D7CCF6EB39E0CC3606110F5D7CFC19
SEED_DEMO_DATA=false
```
`

Keep COMPRESSOR_HEALTH_ENABLED=false until staging validates the output table, timestamps/freshness, profile approval, runtime model name/algorithm and single-owner Compressor alert behavior. Change it to 	rue only in the approved release change.

## Still requires human/DBA confirmation

1. Actual host running the ML worker; this file assumes 10.195.17.69.
2. Source 
ecorded_at IANA timezone.
3. detected_at IANA timezone and whether the writer stores UTC or local time.
4. Prospective technician-feedback start timestamp at actual go-live.
5. Pressure units and COMPRESSOR_SENSOR_SCALE (currently set to 1, not inferred).
6. Approved profile state/codebook/service-epoch versions.
7. Approved Dashboard HTTPS hostname for CORS/origin.
8. Whether the compatibility score table may remain in ht9046mx_iot or must move.
9. Verification that new robust-z rows carry `robust-z-envelope-v1`, historical mislabeled rows are excluded from ARX validation, and the new Cold-only ARX release has passed separate validation before it is selected for live use.

## Required deployment order

1. Clone both private repos and pull ML Git LFS objects.
2. DBA backs up current schemas, creates users, and applies reviewed migrations.
3. Copy only the two environment blocks above into on-server secret files.
4. Run tests/builds, then launch in staging/shadow-only mode.
5. Verify read-only source grants, timezone, freshness, idempotency, alert ownership, restart and rollback.
6. Generate calibration candidates and complete three-day shadow review.
7. Human approver activates profiles; production alerts remain disabled until all release blockers close.
8. Enable Dashboard Compressor health output last.

After deployment, rotate these generated passwords if this local file has been copied, emailed or exposed outside the approved operator channel.
