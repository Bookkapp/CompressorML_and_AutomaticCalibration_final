-- Phase 6/7 calibration-profile registry for the HT9046MX shadow service.
-- Apply after mysql_shadow_schema.sql. This stores analytics evidence only;
-- it never writes source telemetry, PLC values, or machine-control commands.

CREATE TABLE IF NOT EXISTS ht9046mx_calibration_batch (
    batch_id CHAR(36) NOT NULL,
    batch_status VARCHAR(32) NOT NULL,
    source_start DATETIME(6) NOT NULL,
    calibration_end DATETIME(6) NOT NULL,
    shadow_start DATETIME(6) NOT NULL,
    shadow_end DATETIME(6) NOT NULL,
    source_timezone VARCHAR(64) NOT NULL,
    source_table_ref VARCHAR(255) NOT NULL,
    profile_algorithm_version VARCHAR(128) NOT NULL,
    feature_version VARCHAR(128) NOT NULL,
    manifest_json JSON NOT NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    completed_at TIMESTAMP(6) NULL,
    PRIMARY KEY (batch_id),
    KEY ix_calibration_batch_status (batch_status, created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ht9046mx_calibration_profile (
    profile_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    batch_id CHAR(36) NOT NULL,
    profile_version VARCHAR(128) NOT NULL,
    machine_number VARCHAR(32) NOT NULL,
    module TINYINT UNSIGNED NOT NULL,
    sv_state VARCHAR(16) NOT NULL,
    state_code VARCHAR(64) NOT NULL,
    profile_status VARCHAR(40) NOT NULL,
    reason_codes JSON NOT NULL,
    source_start DATETIME(6) NULL,
    calibration_end DATETIME(6) NULL,
    shadow_start DATETIME(6) NULL,
    shadow_end DATETIME(6) NULL,
    calibration_windows INT UNSIGNED NOT NULL DEFAULT 0,
    calibration_days SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    quarantined_windows INT UNSIGNED NOT NULL DEFAULT 0,
    quarantine_pct DOUBLE NULL,
    max_half_shift_rz DOUBLE NULL,
    shadow_windows INT UNSIGNED NOT NULL DEFAULT 0,
    shadow_days SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    shadow_flag_pct DOUBLE NULL,
    persistent_flag_pct DOUBLE NULL,
    statistics_json JSON NOT NULL,
    threshold_json JSON NOT NULL,
    validation_json JSON NOT NULL,
    source_digest CHAR(64) NOT NULL,
    reviewed_at TIMESTAMP(6) NULL,
    reviewer_id VARCHAR(128) NULL,
    review_note VARCHAR(1000) NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (profile_id),
    CONSTRAINT fk_calibration_profile_batch FOREIGN KEY (batch_id)
        REFERENCES ht9046mx_calibration_batch(batch_id),
    UNIQUE KEY uq_calibration_profile_batch_key (batch_id, machine_number, module, sv_state, state_code),
    KEY ix_calibration_profile_status (profile_status, created_at),
    KEY ix_calibration_profile_machine (machine_number, module, sv_state, state_code, created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ht9046mx_calibration_shadow_point (
    profile_id BIGINT UNSIGNED NOT NULL,
    event_time DATETIME(6) NOT NULL,
    deviation_score DOUBLE NULL,
    threshold_value DOUBLE NULL,
    raw_flag BOOLEAN NOT NULL DEFAULT FALSE,
    persistent_flag BOOLEAN NOT NULL DEFAULT FALSE,
    data_quality_status VARCHAR(64) NOT NULL,
    PRIMARY KEY (profile_id, event_time),
    CONSTRAINT fk_calibration_shadow_profile FOREIGN KEY (profile_id)
        REFERENCES ht9046mx_calibration_profile(profile_id),
    KEY ix_calibration_shadow_time (event_time)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ht9046mx_active_calibration_profile (
    machine_number VARCHAR(32) NOT NULL,
    module TINYINT UNSIGNED NOT NULL,
    sv_state VARCHAR(16) NOT NULL,
    state_code VARCHAR(64) NOT NULL,
    active_profile_id BIGINT UNSIGNED NOT NULL,
    rollback_mode VARCHAR(32) NOT NULL,
    rollback_profile_id BIGINT UNSIGNED NULL,
    activated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    activated_by VARCHAR(128) NOT NULL,
    PRIMARY KEY (machine_number, module, sv_state, state_code),
    CONSTRAINT fk_active_calibration_profile FOREIGN KEY (active_profile_id)
        REFERENCES ht9046mx_calibration_profile(profile_id),
    CONSTRAINT fk_active_calibration_rollback FOREIGN KEY (rollback_profile_id)
        REFERENCES ht9046mx_calibration_profile(profile_id),
    KEY ix_active_calibration_profile (active_profile_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ht9046mx_calibration_review (
    review_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    batch_id CHAR(36) NOT NULL,
    profile_id BIGINT UNSIGNED NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    decision VARCHAR(16) NOT NULL,
    review_note VARCHAR(1000) NULL,
    approver_id VARCHAR(128) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (review_id),
    CONSTRAINT fk_calibration_review_batch FOREIGN KEY (batch_id)
        REFERENCES ht9046mx_calibration_batch(batch_id),
    CONSTRAINT fk_calibration_review_profile FOREIGN KEY (profile_id)
        REFERENCES ht9046mx_calibration_profile(profile_id),
    UNIQUE KEY uq_calibration_review_idempotency (idempotency_key),
    KEY ix_calibration_review_batch (batch_id, created_at),
    KEY ix_calibration_review_profile (profile_id, created_at),
    CONSTRAINT chk_calibration_review_decision CHECK (decision IN ('APPROVE', 'REJECT'))
) ENGINE=InnoDB;

-- The first approved shadow profile may use the explicit, auditable
-- NO_ACTIVE_PROFILE_FAIL_CLOSED rollback mode. Later activations must point
-- to the exact preceding active profile. No profile can self-approve.
