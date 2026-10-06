-- Analytics only. Compiled minute snapshots; no source/Active/Alert change.
CREATE TABLE IF NOT EXISTS ht9046mx_qualified_day_cache (
    day_key CHAR(64) NOT NULL,
    module INT NOT NULL,
    checked_at DATETIME(6) NOT NULL,
    payload LONGBLOB NOT NULL,
    source_revision VARCHAR(128) NOT NULL,
    PRIMARY KEY (day_key,module),
    INDEX ix_qualified_cache_age (checked_at)
) ENGINE=InnoDB;
