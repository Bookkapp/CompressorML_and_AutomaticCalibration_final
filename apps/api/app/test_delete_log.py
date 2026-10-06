import json
import urllib.request

def test_maintenance_log_delete():
    login_url = "http://127.0.0.1:5001/api/auth/login"
    req = urllib.request.Request(login_url, data=json.dumps({"username": "ADIadmin", "password": "ADIIOT"}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as res:
        token = json.loads(res.read().decode())["token"]

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. Fetch logs
    req_logs = urllib.request.Request("http://127.0.0.1:5001/api/maintenance-logs?limit=10", headers=headers)
    with urllib.request.urlopen(req_logs) as res:
        logs = json.loads(res.read().decode())

    print(f"Total Maintenance Logs: {len(logs)}")

    # 2. Create a temporary log to test delete
    create_url = "http://127.0.0.1:5001/api/maintenance-logs"
    payload = {
        "device_id": logs[0]["device_id"] if logs else 399,
        "technician_name": "Test Tech",
        "log_type": "INSPECTION",
        "description": "Temporary test log for delete test",
        "action_taken": "Routine check",
        "status": "COMPLETED"
    }
    req_create = urllib.request.Request(create_url, data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(req_create) as res:
        temp_log = json.loads(res.read().decode())
    temp_id = temp_log["id"]
    print(f"Created temporary log #{temp_id}")

    # 3. Delete this log as Admin
    del_url = f"http://127.0.0.1:5001/api/maintenance-logs/{temp_id}"
    req_del = urllib.request.Request(del_url, headers=headers, method="DELETE")
    with urllib.request.urlopen(req_del) as res:
        del_res = json.loads(res.read().decode())
    print(f"Delete response: {del_res}")

    # 4. Confirm it is gone
    with urllib.request.urlopen(req_logs) as res:
        logs_after = json.loads(res.read().decode())
    exists = any(l["id"] == temp_id for l in logs_after)
    print(f"Temporary log #{temp_id} still exists in list: {exists}")
    assert not exists, f"Log #{temp_id} was not deleted!"
    print("Admin Delete Maintenance Log API verified 100% successfully!")

if __name__ == "__main__":
    test_maintenance_log_delete()
