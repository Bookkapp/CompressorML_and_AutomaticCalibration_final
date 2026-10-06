-- Run explicitly against the ANALYTICS schema after mysql_phase6_calibration_registry.sql.
-- No source telemetry / Active Profile / PM Alert tables are altered.
CREATE TABLE IF NOT EXISTS ht9046mx_reference_review_job (
    job_id CHAR(36) NOT NULL PRIMARY KEY,
    idempotency_key VARCHAR(100) NOT NULL UNIQUE,
    request_digest CHAR(64) NOT NULL,
    actor_id VARCHAR(100) NOT NULL,
    machine_number VARCHAR(40) NOT NULL,
    module INT NOT NULL,
    status VARCHAR(30) NOT NULL,
    request_json LONGTEXT NOT NULL,
    selection_json LONGTEXT NULL,
    preview_json LONGTEXT NULL,
    source_digest CHAR(64) NULL,
    result_json LONGTEXT NULL,
    error_code VARCHAR(100) NULL,
    progress_message VARCHAR(160) NULL,
    lease_owner CHAR(36) NULL,
    lease_until DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    INDEX ix_reference_status (status, lease_until),
    INDEX ix_reference_context (machine_number, module, created_at)
) ENGINE=InnoDB;
