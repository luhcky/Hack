import streamlit as st
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import ollama
import json
import sys
import os
from datetime import timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from theme import inject_theme

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "db"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "billing"))
from db.db import set_status
from billing.pricing import calculate_bill

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)

DB_URL = os.environ.get("DB_CONNECTION_STRING")
engine = create_engine(DB_URL)

st.set_page_config(page_title="FRDefense console", page_icon="frdefense_icon_64.png",layout="wide")
inject_theme()
st.title("FRDefense operations console")

tab_overview, tab_queue, tab_assistant, tab_billing = st.tabs(
    ["Overview", "Escalation queue", "AI assistant", "Billing"]
)

# ---------------- Overview ----------------
with tab_overview:
    @st.fragment(run_every=timedelta(seconds=5))
    def live_overview():
        with engine.connect() as conn:
            kpis = pd.read_sql(
                text("""
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN LOWER(risk_level) = 'low' THEN 1 ELSE 0 END) AS allowed,
                        SUM(CASE WHEN LOWER(risk_level) IN ('medium', 'high') THEN 1 ELSE 0 END) AS flagged,
                        SUM(CASE WHEN status = 'pending_sms' THEN 1 ELSE 0 END) AS pending_confirm,
                        SUM(CASE WHEN in_flagged_ring = 1 THEN 1 ELSE 0 END) AS ring_flagged
                    FROM flagged_transactions
                    WHERE scored_at >= NOW() - INTERVAL 1 DAY
                """),
                conn,
            ).iloc[0]

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Transactions today", int(kpis["total"] or 0))
        c2.metric("Allowed", int(kpis["allowed"] or 0))
        c3.metric("Flagged", int(kpis["flagged"] or 0))
        c4.metric("Pending SMS confirm", int(kpis["pending_confirm"] or 0))
        c5.metric("Ring-flagged accounts", int(kpis["ring_flagged"] or 0))

        st.subheader("Live transaction stream")
        with engine.connect() as conn:
            stream = pd.read_sql(
                text(
                    "SELECT * FROM flagged_transactions "
                    "ORDER BY scored_at DESC LIMIT 20"
                ),
                conn,
            )

        TIER_LABELS = {
            "low": "Allowed",
            "Low": "Allowed",
            "LOW": "Allowed",
            "medium": "USSD challenge",
            "Medium": "USSD challenge",
            "high": "Pending SMS confirm",
            "High": "Pending SMS confirm",
        }

        if not stream.empty:
            stream["tier"] = (
                stream["risk_level"].map(TIER_LABELS).fillna(stream["risk_level"])
            )
            st.dataframe(
                stream[["phone_number", "amount", "fraud_score", "tier", "status"]],
                use_container_width=True,
            )
        else:
            st.info("No transactions scored yet.")

        st.caption(
            f"Live view · last updated {pd.Timestamp.now().strftime('%H:%M:%S')}"
        )

    live_overview()

    st.subheader("Fraud ring network (most recent flagged cluster)")
    with engine.connect() as conn:
        cluster = conn.execute(
            text("""
                SELECT id FROM flagged_clusters
                ORDER BY id DESC
                LIMIT 1
            """)
        ).mappings().first()

    if not cluster:
        st.info(
            "No fraud ring clusters detected yet. "
            "The graph will appear after ring detection writes to "
            "flagged_clusters / ring_edges."
        )
    else:
        with engine.connect() as conn:
            ring_edges = pd.read_sql(
                text("""
                    SELECT sender_id, device_id, dest_account
                    FROM ring_edges
                    WHERE cluster_id = :cid
                """),
                conn,
                params={"cid": cluster["id"]},
            )

        if ring_edges.empty:
            st.warning(
                f"Cluster {cluster['id']} exists but has no edges in ring_edges."
            )
        else:
            G = nx.Graph()
            for _, row in ring_edges.iterrows():
                G.add_edge(
                    f"s_{row['sender_id']}",
                    f"d_{row['device_id']}",
                )
                G.add_edge(
                    f"s_{row['sender_id']}",
                    f"t_{row['dest_account']}",
                )

            fig, ax = plt.subplots(figsize=(3.2, 2.4), dpi=100)
            pos = nx.spring_layout(G, seed=42)
            nx.draw(
                G,
                pos,
                with_labels=True,
                node_size=180,
                font_size=5,
                width=0.8,
                ax=ax,
            )
            ax.set_axis_off()
            fig.tight_layout(pad=0.1)

            left, center, right = st.columns([1, 1.2, 1])
            with center:
                st.pyplot(fig, use_container_width=True)
            plt.close(fig)

# ---------------- Escalation queue ----------------
with tab_queue:
    st.write(
        "Only cases where the subscriber never responded to the SMS (after 5 minutes)."
    )

    st.markdown(
        """
        <style>
        .escalation-card {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 16px;
            padding: 1.1rem 1.25rem;
            margin-bottom: 0.75rem;
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
        }
        .escalation-card h4 {
            margin: 0 0 0.35rem 0;
            font-size: 1.05rem;
        }
        .escalation-meta {
            opacity: 0.85;
            font-size: 0.92rem;
            margin-bottom: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    VERIFICATION_METHODS = [
        "",
        "Phone call - subscriber reachable",
        "SIM-port log checked",
        "Cross-referenced other fraud signals",
        "Other",
    ]

    with engine.connect() as conn:
        escalated = pd.read_sql(
            text("""
                SELECT * FROM flagged_transactions
                WHERE status IN ('escalate_no_response', 'escalated_no_response')
                ORDER BY fraud_score DESC
            """),
            conn,
        )

    if escalated.empty:
        st.info("No escalated cases right now.")
    else:
        for _, row in escalated.iterrows():
            st.markdown(
                f"""
                <div class="escalation-card">
                    <h4>{row['phone_number']}</h4>
                    <div class="escalation-meta">
                        Amount: <b>{row['amount']:,.0f}</b> &nbsp;·&nbsp;
                        Fraud score: <b>{row['fraud_score']:.0%}</b> &nbsp;·&nbsp;
                        No reply after 5 min
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            col1, col2, col3 = st.columns([1.6, 1.6, 1.2])
            method = col1.selectbox(
                "Verification method",
                VERIFICATION_METHODS,
                key=f"m_{row['id']}",
            )
            detail = col2.text_input("Detail (optional)", key=f"d_{row['id']}")

            with col3:
                confirm = st.button("Confirmed fraud", key=f"f_{row['id']}")
                clear = st.button("Cleared", key=f"c_{row['id']}")

            with st.expander(f"View details — {row['phone_number']}"):
                m1, m2, m3 = st.columns(3)
                m1.metric("Fraud score", f"{row['fraud_score']:.1%}")
                m2.metric(
                    "In flagged ring",
                    "Yes" if row["in_flagged_ring"] else "No",
                )
                m3.write(f"**Scored at**\n\n{row['scored_at']}")

                st.write("**Top SHAP Drivers**")
                try:
                    top_reasons = (
                        json.loads(row["top_reasons"]) if row["top_reasons"] else []
                    )
                except Exception:
                    top_reasons = []

                if not top_reasons:
                    st.info("No SHAP reasons stored for this transaction.")
                else:
                    shap_df = pd.DataFrame(top_reasons)
                    shap_df["feature"] = (
                        shap_df["feature"].astype(str).str.replace("_", " ")
                    )
                    shap_df["abs_val"] = shap_df["contribution"].abs()
                    shap_df = shap_df.sort_values("abs_val", ascending=True)

                    # Short natural-language summary (like the reference UI)
                    parts = []
                    for _, r in shap_df.sort_values(
                        "abs_val", ascending=False
                    ).iterrows():
                        direction = (
                            "increased" if r["contribution"] > 0 else "decreased"
                        )
                        parts.append(
                            f"{r['feature']} {direction} fraud probability by "
                            f"{abs(r['contribution']) * 100:.1f} percentage points."
                        )
                    st.caption(" ".join(parts[:3]))

                    # Chart styled like the reference image
                    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=140)
                    fig.patch.set_facecolor("#0f1a2b")
                    ax.set_facecolor("#0f1a2b")

                    colors = [
                        "#e8a06a" if v > 0 else "#3ecfcf"
                        for v in shap_df["contribution"]
                    ]

                    bars = ax.barh(
                        shap_df["feature"],
                        shap_df["contribution"],
                        color=colors,
                        height=0.55,
                        edgecolor="none",
                        zorder=3,
                    )

                    ax.axvline(0, color="#8a97a8", linewidth=1, zorder=2)

                    for bar, val in zip(bars, shap_df["contribution"]):
                        width = bar.get_width()
                        ax.text(
                            width + (0.02 if width >= 0 else -0.02),
                            bar.get_y() + bar.get_height() / 2,
                            f"{val:+.3f}",
                            va="center",
                            ha="left" if width >= 0 else "right",
                            color="white",
                            fontsize=8,
                            fontweight="bold",
                        )

                    ax.set_xlabel(
                        "SHAP value  →  impact on fraud probability",
                        color="#c5d0dc",
                        fontsize=9,
                    )
                    ax.set_title(
                        "Top SHAP Drivers",
                        color="white",
                        fontsize=13,
                        pad=10,
                    )

                    ax.tick_params(colors="#c5d0dc", labelsize=8)
                    for spine in ax.spines.values():
                        spine.set_color("#2a3b52")
                    ax.spines["top"].set_visible(False)
                    ax.spines["right"].set_visible(False)
                    ax.grid(
                        axis="x",
                        color="#243247",
                        linestyle="--",
                        linewidth=0.6,
                        zorder=0,
                    )

                    legend_items = [
                        Patch(
                            facecolor="#e8a06a",
                            label="Gold = increases fraud risk",
                        ),
                        Patch(
                            facecolor="#3ecfcf",
                            label="Teal = decreases fraud risk",
                        ),
                    ]
                    ax.legend(
                        handles=legend_items,
                        loc="lower right",
                        frameon=False,
                        fontsize=8,
                        labelcolor="#c5d0dc",
                    )

                    fig.tight_layout()
                    st.pyplot(fig, use_container_width=True)
                    plt.close(fig)

                with st.popover("Full feature snapshot at scoring time"):
                    try:
                        features = (
                            json.loads(row["features_json"])
                            if row["features_json"]
                            else {}
                        )
                    except Exception:
                        features = {}
                    st.json(features)

            if confirm:
                if not method:
                    st.error("Select a verification method before confirming.")
                else:
                    set_status(
                        row["txn_id"],
                        status="confirmed_by_ops",
                        resolution_method=method,
                        resolution_note=detail,
                    )
                    st.rerun()

            if clear:
                if not method:
                    st.error("Select a verification method before clearing.")
                else:
                    set_status(
                        row["txn_id"],
                        status="cleared_by_ops",
                        resolution_method=method,
                        resolution_note=detail,
                    )
                    st.rerun()

            st.markdown(
                "<div style='height:0.6rem'></div>",
                unsafe_allow_html=True,
            )

# ---------------- AI assistant (local Ollama) ----------------
with tab_assistant:
    st.caption(
        "Powered by local Llama 3.2 via Ollama - no data leaves this network"
    )
    question = st.text_input(
        "Ask about fraud patterns, trends, or system behavior"
    )

    if st.button("Ask") and question:
        with engine.connect() as conn:
            summary = pd.read_sql(
                text("""
                    SELECT risk_level, COUNT(*) AS count, AVG(fraud_score) AS avg_score
                    FROM flagged_transactions
                    WHERE scored_at >= NOW() - INTERVAL 7 DAY
                    GROUP BY risk_level
                """),
                conn,
            )

        prompt = f"""You are a fraud-analytics assistant. Given this weekly summary:
{summary.to_dict()}
Answer the question in 2-3 sentences: {question}"""

        response = ollama.chat(
            model="llama3.2:3b",
            messages=[{"role": "user", "content": prompt}],
        )
        st.write(response["message"]["content"])

# ---------------- Billing ----------------
with tab_billing:
    st.write(
        "Estimated bill for the current calendar month, based on real usage."
    )
    plan_key = st.selectbox("Plan", ["starter", "growth"])

    with engine.connect() as conn:
        volume = (
            conn.execute(
                text("""
                    SELECT COUNT(*) FROM flagged_transactions
                    WHERE scored_at >= DATE_FORMAT(NOW(), '%Y-%m-01')
                """)
            ).scalar()
            or 0
        )

    bill = calculate_bill(plan_key, volume)
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Transactions scored this month",
        bill["transactions_this_month"],
    )
    c2.metric("Overage cost", f"${bill['overage_cost']:.2f}")
    c3.metric("Total this month", f"${bill['total']:.2f}")