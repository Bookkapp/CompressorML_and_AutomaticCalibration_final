import json
import urllib.request

def test_flow():
    # 1. Active profiles check
    url = "http://127.0.0.1:8000/api/v1/calibration/active_profiles"
    with urllib.request.urlopen(url) as res:
        data = json.loads(res.read().decode())
        mx100_profiles = [p for p in data if str(p.get("machine_number")) in ("100", "MX100", "HT9046MX-100")]
        print(f"Total active profiles across fleet: {len(data)}")
        print(f"MX100 active profiles: {len(mx100_profiles)}")
        for p in mx100_profiles:
            print(f"  Mod {p.get('module')}: profile_id={p.get('active_profile_id')}, status={p.get('profile_status')}, activated_by={p.get('activated_by')}")

    # 2. Run inference for MX100
    inf_url = "http://127.0.0.1:8000/api/v1/inference/run?machine_number=MX100&sync_to_pm=true&limit=200"
    req_inf = urllib.request.Request(inf_url, data=b"", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_inf) as res:
        inf_res = json.loads(res.read().decode())
        print("\n--- ML Inference Result for MX100 ---")
        print(json.dumps(inf_res, indent=2))

if __name__ == "__main__":
    test_flow()
