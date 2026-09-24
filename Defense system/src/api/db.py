import json
import os
from datetime import datetime
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text

Raw_pass = '@Lucky02SQL!'
ED_pass = quote_plus(Raw_pass)
DB_URL = os.environ.get(
    "DB_CONNECTION_STRING",
    f"mysql+pymysql://root:{ED_pass}@localhost:3306/fraud_db",
)
engine = create_engine(DB_URL)


def insert_flagged_transaction(txn_id: str, phone_number: str, amount: float,
                                fraud_score: float, risk_level: str,
                                in_flagged_ring: bool, top_reasons: list,
                                features: dict, status: str, expires_at=None):
    # MySQL upsert syntax differs from Postgres: ON DUPLICATE KEY UPDATE
    # instead of ON CONFLICT ... DO UPDATE, and it references the new
    # values directly rather than via an EXCLUDED pseudo-table.
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO flagged_transactions
                (txn_id, phone_number, amount, fraud_score, risk_level,
                 in_flagged_ring, top_reasons, features_json, status, expires_at)
            VALUES
                (:txn_id, :phone_number, :amount, :fraud_score, :risk_level,
                 :in_flagged_ring, :top_reasons, :features_json, :status, :expires_at)
            ON DUPLICATE KEY UPDATE
                fraud_score = VALUES(fraud_score),
                risk_level = VALUES(risk_level),
                status = VALUES(status)
        """), {
            "txn_id": txn_id, "phone_number": phone_number, "amount": amount,
            "fraud_score": fraud_score, "risk_level": risk_level,
            "in_flagged_ring": in_flagged_ring,
            "top_reasons": json.dumps(top_reasons),
            "features_json": json.dumps(features),
            "status": status, "expires_at": expires_at,
        })


def set_status(txn_id: str, status: str, expires_at=None,
                resolution_method: str = None, resolution_note: str = None):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE flagged_transactions
            SET status = :status,
                expires_at = COALESCE(:expires_at, expires_at),
                resolution_method = COALESCE(:resolution_method, resolution_method),
                resolution_note = COALESCE(:resolution_note, resolution_note)
            WHERE txn_id = :txn_id
        """), {
            "txn_id": txn_id, "status": status, "expires_at": expires_at,
            "resolution_method": resolution_method, "resolution_note": resolution_note,
        })


def find_pending_by_phone(phone_number: str):
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT * FROM flagged_transactions
            WHERE phone_number = :phone AND status = 'pending_sms'
            ORDER BY scored_at DESC LIMIT 1
        """), {"phone": phone_number}).mappings().first()
    return dict(row) if row else None


def find_pending_past_deadline():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT * FROM flagged_transactions
            WHERE status = 'pending_sms' AND expires_at < :now
        """), {"now": datetime.now()}).mappings().all()
    return [dict(r) for r in rows]


def freeze_account(phone_number: str, txn_id: str = None):
    """Logs a freeze request rather than calling a real core-banking
    API directly - that integration is telecom/partner-specific and
    out of scope for this demo. Wire this to the actual account system
    in production."""
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO account_actions (phone_number, action, txn_id)
            VALUES (:phone, 'freeze_requested', :txn_id)
        """), {"phone": phone_number, "txn_id": txn_id})


def write_ring_cluster(sender_count: int, edges: list):
    """edges: list of (sender_id, device_id, dest_account) tuples for
    one detected cluster. Called from network_features.py after ring
    detection, so the dashboard's network graph has real data to show."""
    with engine.begin() as conn:
        # MySQL has no RETURNING clause - the auto-increment ID comes
        # back via the result's lastrowid instead.
        result = conn.execute(text("""
            INSERT INTO flagged_clusters (sender_count) VALUES (:n)
        """), {"n": sender_count})
        cluster_id = result.lastrowid
        for sender_id, device_id, dest_account in edges:
            conn.execute(text("""
                INSERT INTO ring_edges (cluster_id, sender_id, device_id, dest_account)
                VALUES (:cid, :sender, :device, :dest)
            """), {"cid": cluster_id, "sender": sender_id, "device": device_id, "dest": dest_account})
    return cluster_id

