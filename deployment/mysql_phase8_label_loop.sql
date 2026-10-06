-- LEGACY / DO NOT APPLY FOR NEW DEPLOYMENTS.
-- Superseded by mysql_phase8_confirmation_only.sql, which collects only
-- prospective binary anomaly confirmations without recording a cause.
-- Retained for audit of the former design only.
-- Phase 8 controlled technician feedback and automation audit.
-- Apply only after DBA review. This migration does not activate any model/profile.
-- ht9046mx_technician_review is the controlled, incident-linked successor to the
-- generic ht9046mx_maintenance_outcome table. Do not double-write both tables.

CREATE TABLE IF NOT EXISTS ht9046mx_cause_taxonomy (
    cause_code VARCHAR(64) NOT NULL,
    taxonomy_version VARCHAR(64) NOT NULL,
    label_th VARCHAR(255) NOT NULL,
    label_en VARCHAR(255) NOT NULL,
    group_code VARCHAR(64) NOT NULL,
    requires_note BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 100,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (cause_code, taxonomy_version),
    KEY ix_cause_taxonomy_active (active, display_order)
) ENGINE=InnoDB;

INSERT IGNORE INTO ht9046mx_cause_taxonomy
    (cause_code, taxonomy_version, label_th, label_en, group_code, requires_note, display_order)
VALUES
    ('REFRIGERANT_UNDERCHARGE_LEAK', 'v1', 'น้ำยาน้อยหรือสงสัยการรั่ว', 'Refrigerant undercharge / leak', 'LOW_SIDE', TRUE, 10),
    ('HIGH_SIDE_CONDITION', 'v1', 'ภาวะแรงดันสูง', 'High-side condition', 'HIGH_SIDE', TRUE, 20),
    ('VALVE_CONTROL', 'v1', 'วาล์วหรือการควบคุม', 'Valve / control', 'LOCAL_CONTROL', FALSE, 30),
    ('COMPRESSOR_CAPACITY', 'v1', 'สมรรถนะ Compressor', 'Compressor capacity', 'LOCAL_MECHANICAL', FALSE, 40),
    ('SENSOR_DATA_QUALITY', 'v1', 'Sensor หรือคุณภาพข้อมูล', 'Sensor / data quality', 'DATA', FALSE, 50),
    ('FACILITY_COMMON_CAUSE', 'v1', 'Facility หรือสาเหตุร่วม', 'Facility / common cause', 'COMMON_CAUSE', TRUE, 60),
    ('NO_FAULT_FOUND', 'v1', 'ตรวจแล้วไม่พบปัญหา', 'No fault found', 'NO_FAULT', TRUE, 70),
    ('UNKNOWN', 'v1', 'ยังระบุสาเหตุไม่ได้', 'Unknown', 'UNKNOWN', TRUE, 80);

CREATE TABLE IF NOT EXISTS ht9046mx_technician_review (
    review_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    alert_id BIGINT UNSIGNED NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    incident_start DATETIME(6) NOT NULL,
    incident_end DATETIME(6) NOT NULL,
    inspection_status VARCHAR(32) NOT NULL,
    primary_cause_code VARCHAR(64) NULL,
    action_code VARCHAR(64) NULL,
    refrigerant_amount DECIMAL(12,4) NULL,
    refrigerant_unit VARCHAR(32) NULL,
    pre_measurement_json JSON NULL,
    post_measurement_json JSON NULL,
    technician_note TEXT NULL,
    evidence_quality VARCHAR(32) NOT NULL DEFAULT 'UNKNOWN',
    technician_id VARCHAR(128) NOT NULL,
    label_status VARCHAR(32) NOT NULL DEFAULT 'PENDING_QA',
    taxonomy_version VARCHAR(64) NOT NULL DEFAULT 'v1',
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (review_id),
    UNIQUE KEY uq_technician_review_idempotency (idempotency_key),
    KEY ix_technician_review_alert (alert_id, created_at),
    CONSTRAINT fk_review_alert FOREIGN KEY (alert_id)
        REFERENCES ht9046mx_shadow_alert_episode(alert_id),
    CONSTRAINT chk_incident_interval CHECK (incident_end > incident_start)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ht9046mx_incident_telemetry (
    snapshot_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    alert_id BIGINT UNSIGNED NOT NULL,
    machine_number VARCHAR(32) NOT NULL,
    module TINYINT UNSIGNED NOT NULL,
    event_time DATETIME(6) NOT NULL,
    source_grain VARCHAR(16) NOT NULL,
    hp1 DOUBLE NULL, lp1 DOUBLE NULL, hp2 DOUBLE NULL, lp2 DOUBLE NULL,
    valve DOUBLE NULL, temp_high DOUBLE NULL, temp_low DOUBLE NULL,
    anomaly_score DOUBLE NULL, threshold_value DOUBLE NULL,
    raw_flag BOOLEAN NOT NULL DEFAULT FALSE,
    persistent_flag BOOLEAN NOT NULL DEFAULT FALSE,
    sv_state VARCHAR(16) NULL,
    busy_state VARCHAR(32) NULL,
    state_code VARCHAR(64) NULL,
    message_code VARCHAR(64) NULL,
    message_text TEXT NULL,
    data_quality_status VARCHAR(64) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (snapshot_id),
    UNIQUE KEY uq_incident_telemetry (alert_id, event_time, source_grain),
    KEY ix_incident_telemetry_lookup (machine_number, module, event_time),
    CONSTRAINT fk_snapshot_alert FOREIGN KEY (alert_id)
        REFERENCES ht9046mx_shadow_alert_episode(alert_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ht9046mx_automation_run (
    run_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    job_type VARCHAR(64) NOT NULL,
    started_at DATETIME(6) NOT NULL,
    completed_at DATETIME(6) NULL,
    result_status VARCHAR(64) NOT NULL,
    artifact_version VARCHAR(128) NULL,
    detail_json JSON NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (run_id),
    KEY ix_automation_run_type_time (job_type, started_at)
) ENGINE=InnoDB;
