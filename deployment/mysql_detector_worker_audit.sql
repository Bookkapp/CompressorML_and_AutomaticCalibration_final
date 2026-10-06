-- Standalone scheduler audit; no legacy cause taxonomy or model release tables.
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
