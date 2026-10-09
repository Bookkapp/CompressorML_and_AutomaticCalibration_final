-- Additive widening for an existing Server detector table; preserve all rows.
ALTER TABLE ht9046mx_detector_stream MODIFY checkpoint_json LONGTEXT NOT NULL;
