-- HONTECH HT9046-MX analytics schema: append-only shadow outputs.
-- Apply in a dedicated MySQL schema after review by the server/database owner.

CREATE TABLE IF NOT EXISTS ht9046mx_shadow_score (
    score_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    machine_number VARCHAR(32) NOT NULL,
    module TINYINT UNSIGNED NOT NULL,
    event_time DATETIME(6) NOT NULL,
    source_timezone VARCHAR(64) NOT NULL,
    state_code VARCHAR(64) NOT NULL,
    sv_state VARCHAR(16) NOT NULL,
    data_quality_status VARCHAR(64) NOT NULL,
    anomaly_score DOUBLE NULL,
    threshold_value DOUBLE NULL,
    raw_flag BOOLEAN NOT NULL DEFAULT FALSE,
    persistent_flag BOOLEAN NOT NULL DEFAULT FALSE,
    model_version VARCHAR(128) NOT NULL,
    profile_version VARCHAR(128) NOT NULL,
    feature_version VARCHAR(128) NOT NULL,
    threshold_version VARCHAR(128) NOT NULL,
    replay_version VARCHAR(128) NOT NULL,
    evidence_json JSON NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (score_id),
    UNIQUE KEY uq_shadow_score_release (
        machine_number, module, event_time, model_version,
        profile_version, feature_version, threshold_version
    ),
    KEY ix_shadow_score_latest (machine_number, module, event_time),
    KEY ix_shadow_score_status (data_quality_status, event_time)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ht9046mx_shadow_alert_episode (
    alert_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    machine_number VARCHAR(32) NOT NULL,
    module TINYINT UNSIGNED NOT NULL,
    episode_start DATETIME(6) NOT NULL,
    detected_at DATETIME(6) NOT NULL,
    last_observed_at DATETIME(6) NULL,
    alert_status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    severity VARCHAR(32) NOT NULL DEFAULT 'INVESTIGATE',
    claim_level VARCHAR(64) NOT NULL DEFAULT 'PERSISTENT_PATTERN',
    release_version VARCHAR(128) NOT NULL,
    evidence_json JSON NOT NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (alert_id),
    UNIQUE KEY uq_shadow_alert_release (
        machine_number, module, episode_start, release_version
    ),
    KEY ix_shadow_alert_open (alert_status, detected_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ht9046mx_shadow_audit_event (
    audit_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    event_time TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    component VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    result_status VARCHAR(64) NOT NULL,
    release_version VARCHAR(128) NULL,
    detail_json JSON NULL,
    PRIMARY KEY (audit_id),
    KEY ix_shadow_audit_time (event_time),
    KEY ix_shadow_audit_result (result_status, event_time)
) ENGINE=InnoDB;

-- Technician outcomes must be entered from verified maintenance evidence.
CREATE TABLE IF NOT EXISTS ht9046mx_maintenance_outcome (
    outcome_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    machine_number VARCHAR(32) NOT NULL,
    module TINYINT UNSIGNED NULL,
    inspection_started_at DATETIME(6) NOT NULL,
    inspection_completed_at DATETIME(6) NULL,
    suspected_cause VARCHAR(255) NULL,
    confirmed_cause VARCHAR(255) NULL,
    action_taken VARCHAR(255) NULL,
    refrigerant_amount DECIMAL(12,4) NULL,
    refrigerant_unit VARCHAR(32) NULL,
    technician_id VARCHAR(128) NOT NULL,
    evidence_reference VARCHAR(512) NOT NULL,
    label_status VARCHAR(32) NOT NULL DEFAULT 'UNVERIFIED',
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (outcome_id),
    KEY ix_maintenance_machine_time (machine_number, inspection_started_at)
) ENGINE=InnoDB;
