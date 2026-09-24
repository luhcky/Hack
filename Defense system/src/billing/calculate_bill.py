"""
Run with:
    python calculate_bill.py starter
    python calculate_bill.py growth
"""
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "db"))

from sqlalchemy import text
from db import engine
from pricing import calculate_bill


def transactions_this_month() -> int:
    with engine.connect() as conn:
        count = conn.execute(text("""
            SELECT COUNT(*) FROM flagged_transactions
            WHERE scored_at >= DATE_FORMAT(NOW(), '%Y-%m-01')
        """)).scalar()
    return count or 0


if __name__ == "__main__":
    plan_key = sys.argv[1] if len(sys.argv) > 1 else "starter"
    volume = transactions_this_month()
    bill = calculate_bill(plan_key, volume)
    for k, v in bill.items():
        print(f"{k}: {v}")