"""The development-only runner must not grant production write routes."""
import pytest
from notebooks.support.reference_review_mysql_experiment import is_experiment_write, select_only

@pytest.mark.parametrize("path", ["/api/v1/calibration/run", "/api/v1/calibration/machines/MX080/approve_all",
    "/api/v1/calibration/profiles/21/review", "/api/v1/incidents/simulate_prospective",
    "/api/v1/incidents/1/confirmations", "/arbitrary/build"])
def test_write_routes_blocked(path):
    assert not is_experiment_write("POST", path)

def test_only_named_reference_write_paths():
    assert is_experiment_write("POST", "/api/v1/calibration/reference/preview")
    assert is_experiment_write("POST", "/api/v1/calibration/reference/jobs/12345678-1234-1234-1234-123456789abc/build")
    assert not is_experiment_write("DELETE", "/api/v1/calibration/reference/preview")

@pytest.mark.parametrize("sql", ["INSERT INTO source VALUES(1)", "UPDATE source SET x=1", "DELETE FROM source", "CREATE TABLE x (id INT)"])
def test_source_guard_blocks_mutations(sql):
    with pytest.raises(RuntimeError):
        select_only(None, None, sql, {}, None, False)

def test_source_guard_allows_bounded_reads():
    select_only(None, None, "SELECT recorded_at FROM source LIMIT 10", {}, None, False)
