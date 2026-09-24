"""
Demo tool - simulates a live transaction stream by POSTing a curated
set of transactions to the scoring API at intervals, so the dashboard
has something to react to during a demo.

In production, this POST call is made by the telecom/fintech's own
transaction-processing system (synchronously in the transaction path,
or via a Kafka consumer) - this script exists only because that real
integration doesn't exist in this project. Say so if asked.

Run with the scoring API already running:
    python demo/stream_simulator.py
"""
import time
import uuid
import requests

API_URL = "http://localhost:8000/score"

# Hand-picked labeled scenarios so the demo reliably shows:
# allowed, SIM-swap, airtime burst, credential takeover, agent kiosk,
# and multiple fraud-ring patterns.
DEMO_TRANSACTIONS = [
    # ---------- Allowed / low risk ----------
    {
        "label": "Ordinary transaction - should be allowed",
        "amount": 800, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.02, "hour_of_day": 14, "dest_is_merchant": 1,
        "txn_velocity": 1, "device_changed_recently": 0,
        "days_since_last_sim_activity": 220, "geo_jump_km": 2,
        "receipient_fan_in": 3, "device_cluster_ratio": 2, "in_flagged_ring": 0,
        "receipient_is_new": 0, "transfer_burst_count": 0, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 95,
        "phone_number": "+254700000001",
    },
    {
        "label": "Normal salary-style transfer - allowed",
        "amount": 15000, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.15, "hour_of_day": 10, "dest_is_merchant": 0,
        "txn_velocity": 1, "device_changed_recently": 0,
        "days_since_last_sim_activity": 400, "geo_jump_km": 4,
        "receipient_fan_in": 2, "device_cluster_ratio": 1, "in_flagged_ring": 0,
        "receipient_is_new": 0, "transfer_burst_count": 0, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 120,
        "phone_number": "+254700000006",
    },
    {
        "label": "Small merchant payment - allowed",
        "amount": 250, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.01, "hour_of_day": 16, "dest_is_merchant": 1,
        "txn_velocity": 2, "device_changed_recently": 0,
        "days_since_last_sim_activity": 150, "geo_jump_km": 1,
        "receipient_fan_in": 8, "device_cluster_ratio": 3, "in_flagged_ring": 0,
        "receipient_is_new": 0, "transfer_burst_count": 0, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 40,
        "phone_number": "+254700000007",
    },
    {
        "label": "Family transfer afternoon - allowed",
        "amount": 1200, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.05, "hour_of_day": 15, "dest_is_merchant": 0,
        "txn_velocity": 1, "device_changed_recently": 0,
        "days_since_last_sim_activity": 90, "geo_jump_km": 8,
        "receipient_fan_in": 2, "device_cluster_ratio": 1, "in_flagged_ring": 0,
        "receipient_is_new": 0, "transfer_burst_count": 0, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 60,
        "phone_number": "+254700000008",
    },
    {
        "label": "Busy agent kiosk - should NOT be flagged as a ring",
        "amount": 500, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.1, "hour_of_day": 11, "dest_is_merchant": 1,
        "txn_velocity": 1, "device_changed_recently": 0,
        "days_since_last_sim_activity": 300, "geo_jump_km": 1,
        "receipient_fan_in": 40, "device_cluster_ratio": 40, "in_flagged_ring": 0,
        "receipient_is_new": 0, "transfer_burst_count": 0, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 30,
        "phone_number": "+254700000005",
    },

    # ---------- SIM-swap / device change ----------
    {
        "label": "SIM-swap pattern - recent device change, large amount",
        "amount": 48200, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.91, "hour_of_day": 2, "dest_is_merchant": 0,
        "txn_velocity": 4, "device_changed_recently": 1,
        "days_since_last_sim_activity": 0.08, "geo_jump_km": 640,
        "receipient_fan_in": 6, "device_cluster_ratio": 5, "in_flagged_ring": 1,
        "receipient_is_new": 1, "transfer_burst_count": 1, "is_airtime_transfer": 0,
        "login_new_device": 1, "failed_logins_recent": 0, "minutes_since_login": 4,
        "phone_number": "+254700000002",
    },
    {
        "label": "SIM-swap follow-up drain - same victim pattern",
        "amount": 35000, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.88, "hour_of_day": 3, "dest_is_merchant": 0,
        "txn_velocity": 5, "device_changed_recently": 1,
        "days_since_last_sim_activity": 0.2, "geo_jump_km": 520,
        "receipient_fan_in": 7, "device_cluster_ratio": 6, "in_flagged_ring": 1,
        "receipient_is_new": 1, "transfer_burst_count": 2, "is_airtime_transfer": 0,
        "login_new_device": 1, "failed_logins_recent": 1, "minutes_since_login": 2,
        "phone_number": "+254700000009",
    },
    {
        "label": "Overnight SIM activity spike",
        "amount": 21000, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.75, "hour_of_day": 1, "dest_is_merchant": 0,
        "txn_velocity": 3, "device_changed_recently": 1,
        "days_since_last_sim_activity": 0.5, "geo_jump_km": 300,
        "receipient_fan_in": 4, "device_cluster_ratio": 4, "in_flagged_ring": 0,
        "receipient_is_new": 1, "transfer_burst_count": 1, "is_airtime_transfer": 0,
        "login_new_device": 1, "failed_logins_recent": 0, "minutes_since_login": 6,
        "phone_number": "+254700000010",
    },

    # ---------- Airtime pumping ----------
    {
        "label": "Airtime-pumping burst - many first-time small transfers",
        "amount": 340, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.4, "hour_of_day": 3, "dest_is_merchant": 0,
        "txn_velocity": 5, "device_changed_recently": 0,
        "days_since_last_sim_activity": 12, "geo_jump_km": 5,
        "receipient_fan_in": 1, "device_cluster_ratio": 1, "in_flagged_ring": 0,
        "receipient_is_new": 1, "transfer_burst_count": 6, "is_airtime_transfer": 1,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 60,
        "phone_number": "+254700000003",
    },
    {
        "label": "Airtime burst #2 - rapid small sends",
        "amount": 200, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.35, "hour_of_day": 4, "dest_is_merchant": 0,
        "txn_velocity": 7, "device_changed_recently": 0,
        "days_since_last_sim_activity": 8, "geo_jump_km": 3,
        "receipient_fan_in": 1, "device_cluster_ratio": 1, "in_flagged_ring": 0,
        "receipient_is_new": 1, "transfer_burst_count": 8, "is_airtime_transfer": 1,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 25,
        "phone_number": "+254700000011",
    },
    {
        "label": "Airtime burst #3 - new recipients",
        "amount": 150, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.3, "hour_of_day": 2, "dest_is_merchant": 0,
        "txn_velocity": 6, "device_changed_recently": 0,
        "days_since_last_sim_activity": 20, "geo_jump_km": 6,
        "receipient_fan_in": 1, "device_cluster_ratio": 2, "in_flagged_ring": 0,
        "receipient_is_new": 1, "transfer_burst_count": 9, "is_airtime_transfer": 1,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 15,
        "phone_number": "+254700000012",
    },

    # ---------- Credential takeover ----------
    {
        "label": "Credential takeover - new device login, no SIM change",
        "amount": 29000, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.7, "hour_of_day": 1, "dest_is_merchant": 0,
        "txn_velocity": 2, "device_changed_recently": 0,
        "days_since_last_sim_activity": 180, "geo_jump_km": 3,
        "receipient_fan_in": 2, "device_cluster_ratio": 1, "in_flagged_ring": 0,
        "receipient_is_new": 1, "transfer_burst_count": 0, "is_airtime_transfer": 0,
        "login_new_device": 1, "failed_logins_recent": 4, "minutes_since_login": 1.2,
        "phone_number": "+254700000004",
    },
    {
        "label": "Credential takeover - failed logins then big transfer",
        "amount": 41000, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.82, "hour_of_day": 23, "dest_is_merchant": 0,
        "txn_velocity": 3, "device_changed_recently": 0,
        "days_since_last_sim_activity": 200, "geo_jump_km": 12,
        "receipient_fan_in": 3, "device_cluster_ratio": 2, "in_flagged_ring": 0,
        "receipient_is_new": 1, "transfer_burst_count": 1, "is_airtime_transfer": 0,
        "login_new_device": 1, "failed_logins_recent": 6, "minutes_since_login": 0.8,
        "phone_number": "+254700000013",
    },
    {
        "label": "Credential takeover - very fresh session",
        "amount": 18500, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.65, "hour_of_day": 0, "dest_is_merchant": 0,
        "txn_velocity": 2, "device_changed_recently": 0,
        "days_since_last_sim_activity": 95, "geo_jump_km": 9,
        "receipient_fan_in": 2, "device_cluster_ratio": 1, "in_flagged_ring": 0,
        "receipient_is_new": 1, "transfer_burst_count": 0, "is_airtime_transfer": 0,
        "login_new_device": 1, "failed_logins_recent": 3, "minutes_since_login": 0.5,
        "phone_number": "+254700000014",
    },

    # ---------- Fraud RING network members (in_flagged_ring = 1) ----------
    {
        "label": "Ring member A - shared device cluster, high fan-in dest",
        "amount": 9200, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.55, "hour_of_day": 2, "dest_is_merchant": 0,
        "txn_velocity": 4, "device_changed_recently": 1,
        "days_since_last_sim_activity": 3, "geo_jump_km": 40,
        "receipient_fan_in": 18, "device_cluster_ratio": 12, "in_flagged_ring": 1,
        "receipient_is_new": 1, "transfer_burst_count": 3, "is_airtime_transfer": 0,
        "login_new_device": 1, "failed_logins_recent": 1, "minutes_since_login": 5,
        "phone_number": "+254711100001",
    },
    {
        "label": "Ring member B - same device cluster as A",
        "amount": 8800, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.52, "hour_of_day": 2, "dest_is_merchant": 0,
        "txn_velocity": 4, "device_changed_recently": 1,
        "days_since_last_sim_activity": 2, "geo_jump_km": 38,
        "receipient_fan_in": 18, "device_cluster_ratio": 12, "in_flagged_ring": 1,
        "receipient_is_new": 1, "transfer_burst_count": 3, "is_airtime_transfer": 0,
        "login_new_device": 1, "failed_logins_recent": 0, "minutes_since_login": 7,
        "phone_number": "+254711100002",
    },
    {
        "label": "Ring member C - mule account receiving from ring",
        "amount": 15000, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.6, "hour_of_day": 3, "dest_is_merchant": 0,
        "txn_velocity": 5, "device_changed_recently": 0,
        "days_since_last_sim_activity": 5, "geo_jump_km": 25,
        "receipient_fan_in": 22, "device_cluster_ratio": 10, "in_flagged_ring": 1,
        "receipient_is_new": 0, "transfer_burst_count": 4, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 20,
        "phone_number": "+254711100003",
    },
    {
        "label": "Ring member D - shared destination sink",
        "amount": 11200, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.58, "hour_of_day": 4, "dest_is_merchant": 0,
        "txn_velocity": 3, "device_changed_recently": 1,
        "days_since_last_sim_activity": 1, "geo_jump_km": 55,
        "receipient_fan_in": 20, "device_cluster_ratio": 11, "in_flagged_ring": 1,
        "receipient_is_new": 1, "transfer_burst_count": 2, "is_airtime_transfer": 0,
        "login_new_device": 1, "failed_logins_recent": 2, "minutes_since_login": 3,
        "phone_number": "+254711100004",
    },
    {
        "label": "Ring member E - secondary hop in ring",
        "amount": 7600, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.48, "hour_of_day": 5, "dest_is_merchant": 0,
        "txn_velocity": 4, "device_changed_recently": 0,
        "days_since_last_sim_activity": 4, "geo_jump_km": 18,
        "receipient_fan_in": 16, "device_cluster_ratio": 9, "in_flagged_ring": 1,
        "receipient_is_new": 1, "transfer_burst_count": 2, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 12,
        "phone_number": "+254711100005",
    },
    {
        "label": "Ring member F - high velocity inside ring",
        "amount": 13400, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.7, "hour_of_day": 1, "dest_is_merchant": 0,
        "txn_velocity": 8, "device_changed_recently": 1,
        "days_since_last_sim_activity": 0.5, "geo_jump_km": 70,
        "receipient_fan_in": 19, "device_cluster_ratio": 13, "in_flagged_ring": 1,
        "receipient_is_new": 1, "transfer_burst_count": 5, "is_airtime_transfer": 0,
        "login_new_device": 1, "failed_logins_recent": 1, "minutes_since_login": 2,
        "phone_number": "+254711100006",
    },

    # ---------- More mixed / medium patterns ----------
    {
        "label": "Medium risk - elevated velocity only",
        "amount": 4500, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.25, "hour_of_day": 20, "dest_is_merchant": 0,
        "txn_velocity": 4, "device_changed_recently": 0,
        "days_since_last_sim_activity": 60, "geo_jump_km": 15,
        "receipient_fan_in": 5, "device_cluster_ratio": 3, "in_flagged_ring": 0,
        "receipient_is_new": 1, "transfer_burst_count": 1, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 45,
        "phone_number": "+254700000015",
    },
    {
        "label": "Medium risk - new recipient + mild geo jump",
        "amount": 6000, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.3, "hour_of_day": 19, "dest_is_merchant": 0,
        "txn_velocity": 2, "device_changed_recently": 0,
        "days_since_last_sim_activity": 40, "geo_jump_km": 90,
        "receipient_fan_in": 4, "device_cluster_ratio": 2, "in_flagged_ring": 0,
        "receipient_is_new": 1, "transfer_burst_count": 0, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 1, "minutes_since_login": 30,
        "phone_number": "+254700000016",
    },
    {
        "label": "High drain ratio evening transfer",
        "amount": 22000, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.85, "hour_of_day": 21, "dest_is_merchant": 0,
        "txn_velocity": 2, "device_changed_recently": 0,
        "days_since_last_sim_activity": 110, "geo_jump_km": 20,
        "receipient_fan_in": 3, "device_cluster_ratio": 2, "in_flagged_ring": 0,
        "receipient_is_new": 1, "transfer_burst_count": 1, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 18,
        "phone_number": "+254700000017",
    },
    {
        "label": "Geo jump + new device",
        "amount": 9800, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.4, "hour_of_day": 6, "dest_is_merchant": 0,
        "txn_velocity": 2, "device_changed_recently": 1,
        "days_since_last_sim_activity": 15, "geo_jump_km": 250,
        "receipient_fan_in": 3, "device_cluster_ratio": 4, "in_flagged_ring": 0,
        "receipient_is_new": 1, "transfer_burst_count": 0, "is_airtime_transfer": 0,
        "login_new_device": 1, "failed_logins_recent": 0, "minutes_since_login": 8,
        "phone_number": "+254700000018",
    },
    {
        "label": "Burst transfers to same new recipient",
        "amount": 3200, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.45, "hour_of_day": 22, "dest_is_merchant": 0,
        "txn_velocity": 6, "device_changed_recently": 0,
        "days_since_last_sim_activity": 25, "geo_jump_km": 10,
        "receipient_fan_in": 1, "device_cluster_ratio": 2, "in_flagged_ring": 0,
        "receipient_is_new": 1, "transfer_burst_count": 5, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 10,
        "phone_number": "+254700000019",
    },
    {
        "label": "Late-night large P2P",
        "amount": 27500, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.72, "hour_of_day": 2, "dest_is_merchant": 0,
        "txn_velocity": 1, "device_changed_recently": 0,
        "days_since_last_sim_activity": 70, "geo_jump_km": 5,
        "receipient_fan_in": 2, "device_cluster_ratio": 1, "in_flagged_ring": 0,
        "receipient_is_new": 1, "transfer_burst_count": 0, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 50,
        "phone_number": "+254700000020",
    },
    {
        "label": "Mild risk - slightly high velocity",
        "amount": 1800, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.12, "hour_of_day": 13, "dest_is_merchant": 0,
        "txn_velocity": 3, "device_changed_recently": 0,
        "days_since_last_sim_activity": 130, "geo_jump_km": 7,
        "receipient_fan_in": 3, "device_cluster_ratio": 2, "in_flagged_ring": 0,
        "receipient_is_new": 0, "transfer_burst_count": 1, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 70,
        "phone_number": "+254700000021",
    },
    {
        "label": "Merchant + new device (borderline)",
        "amount": 3000, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.2, "hour_of_day": 12, "dest_is_merchant": 1,
        "txn_velocity": 2, "device_changed_recently": 1,
        "days_since_last_sim_activity": 45, "geo_jump_km": 30,
        "receipient_fan_in": 10, "device_cluster_ratio": 5, "in_flagged_ring": 0,
        "receipient_is_new": 0, "transfer_burst_count": 0, "is_airtime_transfer": 0,
        "login_new_device": 1, "failed_logins_recent": 0, "minutes_since_login": 9,
        "phone_number": "+254700000022",
    },
    {
        "label": "Ring-linked airtime hop",
        "amount": 500, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.35, "hour_of_day": 3, "dest_is_merchant": 0,
        "txn_velocity": 5, "device_changed_recently": 0,
        "days_since_last_sim_activity": 6, "geo_jump_km": 12,
        "receipient_fan_in": 14, "device_cluster_ratio": 8, "in_flagged_ring": 1,
        "receipient_is_new": 1, "transfer_burst_count": 4, "is_airtime_transfer": 1,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 14,
        "phone_number": "+254711100007",
    },
    {
        "label": "Clean low-value P2P - allowed",
        "amount": 400, "orig_balance_delta": 0, "dest_balance_delta": 0,
        "drain_ratio": 0.03, "hour_of_day": 17, "dest_is_merchant": 0,
        "txn_velocity": 1, "device_changed_recently": 0,
        "days_since_last_sim_activity": 250, "geo_jump_km": 2,
        "receipient_fan_in": 2, "device_cluster_ratio": 1, "in_flagged_ring": 0,
        "receipient_is_new": 0, "transfer_burst_count": 0, "is_airtime_transfer": 0,
        "login_new_device": 0, "failed_logins_recent": 0, "minutes_since_login": 80,
        "phone_number": "+254700000023",
    },
    {"amount": 48200,
    "orig_balance_delta": -48200,
    "dest_balance_delta": 48200,
    "drain_ratio": 0.91,
    "hour_of_day": 2,
    "dest_is_merchant": 0,
    "txn_velocity": 6,
    "device_changed_recently": 1,
    "days_since_last_sim_activity": 0.08,
    "geo_jump_km": 640,
    "receipient_fan_in": 12,
    "device_cluster_ratio": 9,
    "in_flagged_ring": 1,
    "receipient_is_new": 1,
    "transfer_burst_count": 4,
    "is_airtime_transfer": 0,
    "login_new_device": 1,
    "failed_logins_recent": 3,
    "minutes_since_login": 1.5,
    "phone_number": "+254700009999",
    "txn_id": "SHAP-DEMO-001",},
]


def run(delay_seconds: float = 2.0):
    print(f"Sending {len(DEMO_TRANSACTIONS)} demo transactions to {API_URL}\n")

    for scenario in DEMO_TRANSACTIONS:
        # copy so we don't mutate the global list across reruns
        payload = dict(scenario)
        label = payload.pop("label")
        payload["txn_id"] = str(uuid.uuid4())

        print(f"--- {label} ---")
        try:
            response = requests.post(API_URL, json=payload, timeout=30)
            print(response.status_code, response.json())
        except Exception as e:
            print(f"Request failed: {e}")

        time.sleep(delay_seconds)

    print("\nDone.")


if __name__ == "__main__":
    run()