"""
Pricing tiers for the marketplace listing, and the logic to turn a
month's actual usage into a bill. See Step 10 of the PDF guide for the
reasoning behind these numbers - they're a starting structure to
validate with a real pilot customer, not fixed figures.
"""
from dataclasses import dataclass

@dataclass
class Plan:
    name: str
    monthly_fee: float
    included_transactions: int
    overage_rate: float  # per transaction, beyond the included amount


PLANS = {
    "starter": Plan(
        name="Starter (pay-as-you-go)",
        monthly_fee=0.0,
        included_transactions=0,
        overage_rate=0.002,
    ),
    "growth": Plan(
        name="Growth",
        monthly_fee=249.0,
        included_transactions=250_000,
        overage_rate=0.001,
    ),
    # Enterprise is custom/negotiated - not modeled here as a formula.
}


def calculate_bill(plan_key: str, transactions_this_month: int) -> dict:
    if plan_key not in PLANS:
        raise ValueError(f"Unknown plan '{plan_key}' - enterprise plans are negotiated, not calculated")

    plan = PLANS[plan_key]
    billable_overage = max(0, transactions_this_month - plan.included_transactions)
    overage_cost = billable_overage * plan.overage_rate
    total = plan.monthly_fee + overage_cost

    return {
        "plan": plan.name,
        "transactions_this_month": transactions_this_month,
        "included_transactions": plan.included_transactions,
        "billable_overage": billable_overage,
        "monthly_fee": plan.monthly_fee,
        "overage_cost": round(overage_cost, 2),
        "total": round(total, 2),
    }


if __name__ == "__main__":
    # Quick sanity check of both tiers at a few volumes
    for plan_key in ["starter", "growth"]:
        for volume in [1_000, 250_000, 400_000]:
            print(plan_key, volume, "->", calculate_bill(plan_key, volume))