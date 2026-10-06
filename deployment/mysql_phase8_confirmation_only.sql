-- Phase 8 prospective technician confirmation only.
-- Apply after mysql_shadow_schema.sql and only after DBA review.
-- This creates no PLC/control path and does not activate a profile or model.
-- New deployments must use this migration instead of mysql_phase8_label_loop.sql.

CREATE TABLE IF NOT EXISTS ht9046mx_technician_confirmation (
    confirmation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    alert_id BIGINT UNSIGNED NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    confirmation_status VARCHAR(32) NOT NULL,
    technician_note TEXT NULL,
    technician_id VARCHAR(128) NOT NULL,
    label_status VARCHAR(32) NOT NULL DEFAULT 'PENDING_QA',
    feedback_policy_version VARCHAR(64) NOT NULL DEFAULT 'prospective-binary-v1',
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (confirmation_id),
    UNIQUE KEY uq_technician_confirmation_idempotency (idempotency_key),
    KEY ix_technician_confirmation_alert (alert_id, created_at),
    KEY ix_technician_confirmation_label (label_status, created_at),
    CONSTRAINT fk_confirmation_alert FOREIGN KEY (alert_id)
        REFERENCES ht9046mx_shadow_alert_episode(alert_id),
    CONSTRAINT chk_confirmation_status CHECK (
        confirmation_status IN (
            'EQUIPMENT_ANOMALY',
            'NO_EQUIPMENT_ANOMALY',
            'UNRESOLVED'
        )
    )
) ENGINE=InnoDB;

-- Training contract:
-- 1. Only alerts detected on/after HT9046MX_TECHNICIAN_FEEDBACK_START_AT
--    are accepted by the API.
-- 2. Only EQUIPMENT_ANOMALY and NO_EQUIPMENT_ANOMALY rows with a later
--    label_status approved by Label QA may enter a binary supervised dataset.
-- 3. UNRESOLVED and every free-text technician_note remain out of model targets.
