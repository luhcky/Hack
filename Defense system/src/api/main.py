import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, HTTPException
from pydantic import BaseModel
import joblib
import pandas as pd
import shap
import africastalking
from datetime import datetime, timedelta
import sys
import os


async def _escalation_worker():
    while True:
        try:
            await asyncio.to_thread(escalate_expired_cases)
        except Exception as exc:
            print(f"[escalation] Background check failed: {exc}")
        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(_app):
    worker = asyncio.create_task(_escalation_worker())
    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Fraud Detection API", lifespan=lifespan)

_bundle = joblib.load('fraud_model.joblib')
model = _bundle['model']
FEATURES = _bundle['FEATURES']

class Transaction(BaseModel):
    amount: float
    orig_balance_delta: float
    dest_balance_delta:float
    drain_ratio:float
    hour_of_day: int
    dest_is_merchant: int
    txn_velocity: float
    device_changed_recently: int
    days_since_last_sim_activity: float
    geo_jump_km: float
    receipient_fan_in : float
    device_cluster_ratio: float
    in_flagged_ring: int
    receipient_is_new: int
    transfer_burst_count: float
    is_airtime_transfer: int
    login_new_device: int
    failed_logins_recent: int
    minutes_since_login: float
    phone_number: str
    txn_id: str



@app.post("/score")
def score_transaction(txn: Transaction, dry_run: bool = False, escalate_demo: bool = False):
    if escalate_demo and not dry_run:
        raise HTTPException(
            status_code=400,
            detail="escalate_demo is available only when SMS delivery is disabled.",
        )
    row = pd.DataFrame([txn.dict()])[FEATURES]
    if list(row.columns) != list(FEATURES):
        raise ValueError("Transaction feature order does not match the loaded model.")
    # The bundled legacy XGBoost pickle reports the right feature list but
    # rejects pandas' names at prediction time. The API constructs the frame
    # in FEATURES order above, so disable only that redundant name check.
    prob = float(model.predict_proba(row, validate_features=False)[0][1])
    risk_level = 'High' if prob > 0.7 else 'Medium' if prob > 0.5 else 'LOW'

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(row)[0]
    contributions= sorted(
        zip(FEATURES, shap_values), key=lambda x: abs(x[1]), reverse=True)[:3]
    top_reasons = [
        {'feature':f, "contribution" :round(float(v), 3)} for f, v in contributions
    ]

    if risk_level in ('High', 'Medium'):
        status = 'pending_sms'
        expires_at = datetime.now() + timedelta(minutes=15)
    else:
        status = 'scored'
        expires_at = None

    insert_flagged_transaction(
        txn_id=txn.txn_id,
        phone_number=txn.phone_number,
        amount=txn.amount,
        fraud_score=prob,
        risk_level=risk_level,
        in_flagged_ring=bool(txn.in_flagged_ring),
        top_reasons=top_reasons,
        features=txn.dict(),
        status=status,
        expires_at=expires_at,
    )
    sms_sent = False
    if risk_level in ('High', 'Medium'):
        if dry_run:
            expires_at = datetime.now() + timedelta(minutes=5)
            if escalate_demo:
                expires_at = datetime.now() - timedelta(seconds=1)
            set_status(txn.txn_id, status='pending_sms', expires_at=expires_at)
            if escalate_demo:
                escalate_expired_cases()
        else:
            send_fraud_alert(txn.phone_number, txn.amount, top_reasons, txn.txn_id)
            sms_sent = True

    if dry_run and txn.in_flagged_ring:
        _ensure_demo_ring_cluster()

    return {
        "fraud_score": prob,
        "risk_level": risk_level,
        "top_reasons": top_reasons,
        "sms_sent": sms_sent,
        "status": 'escalate_no_response' if escalate_demo and risk_level in ('High', 'Medium') else status,
    }


#SMS confirmation

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'db'))
from db import (
    find_pending_by_phone,
    find_pending_past_deadline,
    insert_flagged_transaction,
    set_status,
    freeze_account,
    write_ring_cluster,
)

_demo_ring_cluster_seeded = False


def _ensure_demo_ring_cluster():
    global _demo_ring_cluster_seeded
    if _demo_ring_cluster_seeded:
        return
    write_ring_cluster(
        sender_count=4,
        edges=[
            ("demo-sender-01", "shared-device-a", "mule-account-a"),
            ("demo-sender-02", "shared-device-a", "mule-account-a"),
            ("demo-sender-03", "shared-device-b", "mule-account-a"),
            ("demo-sender-04", "shared-device-b", "mule-account-b"),
        ],
    )
    _demo_ring_cluster_seeded = True

africastalking.initialize(
    username= os.environ.get("AT_USERNAME"),
    api_key= os.environ.get("AT_API_KEY")
)

sms = africastalking.SMS
def send_fraud_alert(phone_number:str, amount:float, top_reasons: list, txn_id:str):
    reason_text = ', '.join (r['feature'].replace('_', ' ') for r in top_reasons)
    message =(f"ALERT: A transaction of ${amount} has been flagged as potentially fraudulent."
              f"on your account reason: {reason_text}.Reply YES if this was you, or NO if it wasn't."
    )
    sms.send(message, [phone_number])
    set_status(txn_id, status='pending_sms', expires_at = datetime.now() + timedelta(minutes=5))

#Automatic reply resolving

@app.post("/sms/incoming")
def handle__sms_reply(from_:  str = Form(alias="from"), text: str = Form()):
    txn = find_pending_by_phone(from_)
    if txn is None:
        return {"Status": "No pending transaction."}

    reply = text.strip().upper()
    if reply == 'YES':
        set_status(txn['txn_id'], status='confirmed_by_subscriber')

    elif reply == 'NO':
        set_status(txn['txn_id'], status='denied_by_subscriber')
        freeze_account(txn['phone_number'], txn['txn_id'])
    else:
        return {"status": "Invalid response"}
    return {"status": 'resolved'}

def escalate_expired_cases():
    for txn in find_pending_past_deadline():
        set_status(txn['txn_id'], status='escalate_no_response')

