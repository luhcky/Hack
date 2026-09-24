import json
import os
import sys
from datetime import timedelta

import matplotlib.pyplot as plt
import networkx as nx
import ollama
import pandas as pd
import streamlit as st
from matplotlib.patches import Patch
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

st.set_page_config(
    page_title="FRDefense console",
    page_icon="frdefense_icon_64.png",
    layout="wide",
)

if "light_theme" not in st.session_state:
    st.session_state.light_theme = False
if "active_page" not in st.session_state:
    st.session_state.active_page = "Overview"


def _navigate_to(destination):
    st.session_state.active_page = destination

with st.sidebar:
    st.markdown("## FRDefense")
    st.caption("Fraud operations console")
    light_theme = st.toggle("Light theme", key="light_theme")
    st.divider()
    st.caption("WORKSPACE")
    for destination in ["Overview", "Escalation queue", "AI assistant", "Billing"]:
        st.button(
            destination,
            key=f"sidebar_nav_{destination.lower().replace(' ', '_')}",
            type="primary" if st.session_state.active_page == destination else "secondary",
            use_container_width=True,
            on_click=_navigate_to,
            args=(destination,),
        )
    page = st.session_state.active_page

inject_theme("light" if light_theme else "dark")


def _decode_json(value, default):
    if value is None or value == "":
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _risk_color(risk_level, light_theme=False):
    risk = str(risk_level).lower()
    palette = {
        "high": "#b42318" if light_theme else "#ff8b82",
        "medium": "#9a6700" if light_theme else "#f6c85f",
        "low": "#087443" if light_theme else "#5eead4",
    }
    return palette.get(risk, "#667085" if light_theme else "#aab7c4")


def _risk_badge(risk_level, light_theme):
    risk = str(risk_level).lower()
    label = {"high": "High risk", "medium": "Medium risk", "low": "Low risk"}.get(
        risk, str(risk_level).title()
    )
    color = _risk_color(risk, light_theme)
    st.markdown(
        f'<span class="risk-pill" style="--risk-color:{color}">{label}</span>',
        unsafe_allow_html=True,
    )


def _render_shap_reasons(raw_reasons, light_theme):
    reasons = _decode_json(raw_reasons, [])
    if not isinstance(reasons, list) or not reasons:
        st.info("No SHAP reasons are stored for this transaction.")
        return

    reasons = [r for r in reasons if isinstance(r, dict) and "feature" in r]
    if not reasons:
        st.info("No SHAP reasons are stored for this transaction.")
        return

    for reason in reasons[:3]:
        feature = str(reason.get("feature", "Unknown feature")).replace("_", " ")
        try:
            contribution = float(reason.get("contribution", 0))
        except (TypeError, ValueError):
            contribution = 0.0
        direction = "increased" if contribution > 0 else "decreased"
        st.write(
            f"**{feature.title()}** {direction} the model's fraud score "
            f"by {abs(contribution) * 100:.1f} percentage points."
        )

    shap_df = pd.DataFrame(reasons[:3])
    shap_df["feature"] = shap_df["feature"].astype(str).str.replace("_", " ")
    shap_df["contribution"] = pd.to_numeric(
        shap_df["contribution"], errors="coerce"
    ).fillna(0.0)
    shap_df = shap_df.sort_values("contribution", key=lambda values: values.abs())

    text_color = "#344054" if light_theme else "#d7e5e4"
    grid_color = "#d0d5dd" if light_theme else "#31434d"
    positive = "#b42318" if light_theme else "#f08a76"
    negative = "#087e8b" if light_theme else "#5ed6cb"

    fig, ax = plt.subplots(figsize=(8, 2.8), dpi=120)
    background = "#ffffff" if light_theme else "#0c1b20"
    fig.patch.set_facecolor(background)
    ax.set_facecolor(background)
    colors = [positive if value > 0 else negative for value in shap_df["contribution"]]
    bars = ax.barh(
        shap_df["feature"],
        shap_df["contribution"],
        color=colors,
        height=0.56,
        zorder=3,
    )
    ax.axvline(0, color=grid_color, linewidth=1, zorder=2)
    for bar, value in zip(bars, shap_df["contribution"]):
        ax.text(
            bar.get_width() + (0.012 if value >= 0 else -0.012),
            bar.get_y() + bar.get_height() / 2,
            f"{value:+.3f}",
            va="center",
            ha="left" if value >= 0 else "right",
            color=text_color,
            fontsize=8,
        )
    ax.set_xlabel("Impact on fraud score", color=text_color)
    ax.tick_params(colors=text_color, labelsize=9)
    ax.grid(axis="x", color=grid_color, linestyle="--", linewidth=0.6, zorder=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def _render_transaction_details(row, light_theme):
    st.markdown("#### Transaction details")
    top = st.columns([1.5, 1, 1, 1])
    with top[0]:
        st.write("**Transaction ID**")
        st.code(str(row["txn_id"]), language=None)
    with top[1]:
        st.write("**Fraud score**")
        st.metric("Score", f"{float(row['fraud_score']):.1%}", label_visibility="collapsed")
    with top[2]:
        st.write("**Risk**")
        _risk_badge(row["risk_level"], light_theme)
    with top[3]:
        st.write("**Status**")
        st.write(str(row["status"]).replace("_", " ").title())

    info = st.columns(4)
    info[0].write(f"**Phone**\n\n{row['phone_number']}")
    info[1].write(f"**Amount**\n\n{float(row['amount']):,.2f}")
    info[2].write(f"**Scored**\n\n{row['scored_at']}")
    info[3].write(
        "**Flagged ring**\n\n" + ("Yes" if bool(row["in_flagged_ring"]) else "No")
    )

    st.markdown("#### Why it was flagged")
    _render_shap_reasons(row.get("top_reasons"), light_theme)
    with st.expander("Full feature snapshot"):
        features = _decode_json(row.get("features_json"), {})
        st.json(features if isinstance(features, dict) else {})


@st.fragment(run_every=timedelta(seconds=5))
def _render_overview(light_theme):
    st.title("Operations overview")
    st.caption("A live view of scored transactions and fraud activity.")

    with engine.connect() as conn:
        metrics = conn.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN scored_at >= NOW() - INTERVAL 24 HOUR
                        THEN 1 ELSE 0 END), 0) AS total_now,
                    COALESCE(SUM(CASE WHEN scored_at >= NOW() - INTERVAL 48 HOUR
                        AND scored_at < NOW() - INTERVAL 24 HOUR
                        THEN 1 ELSE 0 END), 0) AS total_prev,
                    COALESCE(SUM(CASE WHEN scored_at >= NOW() - INTERVAL 24 HOUR
                        AND LOWER(risk_level) = 'low' THEN 1 ELSE 0 END), 0) AS allowed_now,
                    COALESCE(SUM(CASE WHEN scored_at >= NOW() - INTERVAL 48 HOUR
                        AND scored_at < NOW() - INTERVAL 24 HOUR
                        AND LOWER(risk_level) = 'low' THEN 1 ELSE 0 END), 0) AS allowed_prev,
                    COALESCE(SUM(CASE WHEN scored_at >= NOW() - INTERVAL 24 HOUR
                        AND LOWER(risk_level) IN ('medium', 'high') THEN 1 ELSE 0 END), 0) AS flagged_now,
                    COALESCE(SUM(CASE WHEN scored_at >= NOW() - INTERVAL 48 HOUR
                        AND scored_at < NOW() - INTERVAL 24 HOUR
                        AND LOWER(risk_level) IN ('medium', 'high') THEN 1 ELSE 0 END), 0) AS flagged_prev,
                    COALESCE(SUM(CASE WHEN scored_at >= NOW() - INTERVAL 24 HOUR
                        AND status = 'pending_sms' THEN 1 ELSE 0 END), 0) AS pending_now,
                    COALESCE(SUM(CASE WHEN scored_at >= NOW() - INTERVAL 48 HOUR
                        AND scored_at < NOW() - INTERVAL 24 HOUR
                        AND status = 'pending_sms' THEN 1 ELSE 0 END), 0) AS pending_prev,
                    COALESCE(SUM(CASE WHEN scored_at >= NOW() - INTERVAL 24 HOUR
                        AND in_flagged_ring = 1 THEN 1 ELSE 0 END), 0) AS ring_now,
                    COALESCE(SUM(CASE WHEN scored_at >= NOW() - INTERVAL 48 HOUR
                        AND scored_at < NOW() - INTERVAL 24 HOUR
                        AND in_flagged_ring = 1 THEN 1 ELSE 0 END), 0) AS ring_prev
                FROM flagged_transactions
                WHERE scored_at >= NOW() - INTERVAL 48 HOUR
                """
            ),
        ).mappings().one()

    metric_specs = [
        ("Transactions", "total_now", "total_prev", "normal"),
        ("Allowed", "allowed_now", "allowed_prev", "normal"),
        ("Flagged", "flagged_now", "flagged_prev", "inverse"),
        ("Pending SMS", "pending_now", "pending_prev", "inverse"),
        ("Ring flagged", "ring_now", "ring_prev", "inverse"),
    ]
    cols = st.columns(5)
    for col, (label, current_key, previous_key, delta_color) in zip(cols, metric_specs):
        current = int(metrics[current_key] or 0)
        previous = int(metrics[previous_key] or 0)
        change = current - previous
        col.metric(
            label,
            current,
            delta=f"{change:+d} vs prior 24h",
            delta_color=delta_color,
        )

    st.markdown("### Live transaction stream")
    st.caption("Filter the latest activity, then select a transaction to inspect it.")

    with engine.connect() as conn:
        status_values = conn.execute(
            text("SELECT DISTINCT status FROM flagged_transactions ORDER BY status")
        ).scalars().all()

    filter_cols = st.columns([2, 1.2, 1, 1.2, 1])
    search = filter_cols[0].text_input(
        "Search phone or transaction ID",
        placeholder="e.g. +2547… or txn ID",
        help="Press Enter to apply the search.",
    )
    time_range = filter_cols[1].selectbox(
        "Time range", ["Last 24 hours", "Last 7 days", "Last 30 days", "All history"]
    )
    risk_filter = filter_cols[2].selectbox(
        "Risk", ["All risk", "Low", "Medium", "High"]
    )
    status_filter = filter_cols[3].selectbox("Status", ["All statuses", *status_values])
    ring_filter = filter_cols[4].selectbox(
        "Ring", ["Any", "Flagged ring", "Not in ring"]
    )

    where = []
    params = {}
    intervals = {
        "Last 24 hours": 1,
        "Last 7 days": 7,
        "Last 30 days": 30,
    }
    if time_range in intervals:
        where.append("scored_at >= NOW() - INTERVAL :days DAY")
        params["days"] = intervals[time_range]
    if search.strip():
        where.append("(phone_number LIKE :search OR txn_id LIKE :search)")
        params["search"] = f"%{search.strip()}%"
    if risk_filter != "All risk":
        where.append("LOWER(risk_level) = :risk")
        params["risk"] = risk_filter.lower()
    if status_filter != "All statuses":
        where.append("status = :status")
        params["status"] = status_filter
    if ring_filter == "Flagged ring":
        where.append("in_flagged_ring = 1")
    elif ring_filter == "Not in ring":
        where.append("in_flagged_ring = 0")

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    query = text(
        f"SELECT txn_id, phone_number, amount, fraud_score, risk_level, status, "
        f"in_flagged_ring, scored_at, top_reasons, features_json "
        f"FROM flagged_transactions {where_sql} "
        "ORDER BY scored_at DESC LIMIT 201"
    )
    with engine.connect() as conn:
        transactions = pd.read_sql(query, conn, params=params)

    has_more = len(transactions) > 200
    transactions = transactions.head(200).copy()
    if has_more:
        st.info("Showing the newest 200 matching transactions. Narrow the filters to see a specific case.")

    if transactions.empty:
        st.info("No transactions match these filters. Try a wider time range or clear a filter.")
    else:
        display = transactions[
            [
                "txn_id",
                "phone_number",
                "amount",
                "fraud_score",
                "risk_level",
                "status",
                "in_flagged_ring",
                "scored_at",
            ]
        ].rename(
            columns={
                "txn_id": "Transaction ID",
                "phone_number": "Phone",
                "amount": "Amount",
                "fraud_score": "Fraud score",
                "risk_level": "Risk",
                "status": "Status",
                "in_flagged_ring": "Flagged ring",
                "scored_at": "Scored at",
            }
        )
        display["Fraud score"] = (
            pd.to_numeric(display["Fraud score"], errors="coerce") * 100
        )
        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Fraud score": st.column_config.ProgressColumn(
                    "Fraud score", min_value=0, max_value=100, format="%.0f%%"
                ),
                "Flagged ring": st.column_config.CheckboxColumn("Flagged ring"),
            },
        )

        selected_id = st.selectbox(
            "Inspect transaction",
            transactions["txn_id"].astype(str).tolist(),
            format_func=lambda txn_id: (
                f"{txn_id} · {transactions.loc[transactions['txn_id'].astype(str) == txn_id, 'phone_number'].iloc[0]}"
            ),
        )
        selected = transactions.loc[
            transactions["txn_id"].astype(str) == selected_id
        ].iloc[0]
        with st.expander("Transaction details", expanded=True):
            _render_transaction_details(selected, light_theme)

    st.caption(f"Live view · last updated {pd.Timestamp.now().strftime('%H:%M:%S')}")
    st.divider()
    st.markdown("### Fraud ring network")
    with engine.connect() as conn:
        cluster = conn.execute(
            text("SELECT id FROM flagged_clusters ORDER BY id DESC LIMIT 1")
        ).mappings().first()

    if not cluster:
        st.info("No fraud ring clusters have been detected yet. The graph will appear when ring data is available.")
        return

    with engine.connect() as conn:
        ring_edges = pd.read_sql(
            text(
                """SELECT sender_id, device_id, dest_account FROM ring_edges
                   WHERE cluster_id = :cid"""
            ),
            conn,
            params={"cid": cluster["id"]},
        )
    if ring_edges.empty:
        st.info(f"Cluster {cluster['id']} has no network edges to display yet.")
        return

    graph = nx.Graph()
    node_colors = {}
    for _, edge in ring_edges.iterrows():
        sender = f"Sender · {edge['sender_id']}"
        device = f"Device · {edge['device_id']}"
        recipient = f"Recipient · {edge['dest_account']}"
        graph.add_edge(sender, device)
        graph.add_edge(sender, recipient)
        node_colors[sender] = "#7b61ff" if light_theme else "#9c8cff"
        node_colors[device] = "#008a91" if light_theme else "#59d3ca"
        node_colors[recipient] = "#d17b00" if light_theme else "#f4bb64"

    fig, ax = plt.subplots(figsize=(10, 5), dpi=110)
    background = "#ffffff" if light_theme else "#0c1b20"
    fig.patch.set_facecolor(background)
    ax.set_facecolor(background)
    positions = nx.spring_layout(graph, seed=42)
    nx.draw_networkx_edges(graph, positions, ax=ax, alpha=0.5, width=1.2, edge_color="#91a4b0")
    nx.draw_networkx_nodes(
        graph,
        positions,
        ax=ax,
        node_color=[node_colors.get(node, "#91a4b0") for node in graph.nodes],
        node_size=900,
        edgecolors=background,
        linewidths=1.5,
    )
    nx.draw_networkx_labels(
        graph,
        positions,
        ax=ax,
        font_size=8,
        font_color="#24313a" if light_theme else "#f1f5f5",
    )
    ax.set_axis_off()
    legend = [
        Patch(facecolor="#7b61ff" if light_theme else "#9c8cff", label="Sender"),
        Patch(facecolor="#008a91" if light_theme else "#59d3ca", label="Device"),
        Patch(facecolor="#d17b00" if light_theme else "#f4bb64", label="Recipient"),
    ]
    ax.legend(handles=legend, loc="upper left", frameon=False, labelcolor="#344054" if light_theme else "#d7e5e4")
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def _render_escalation_queue(light_theme):
    st.title("Escalation queue")
    st.caption("Review cases with no subscriber response and record an operator decision.")

    notice = st.session_state.pop("queue_notice", None)
    if notice:
        st.success(notice)

    verification_methods = [
        "",
        "Phone call - subscriber reachable",
        "SIM-port log checked",
        "Cross-referenced other fraud signals",
        "Other",
    ]
    with engine.connect() as conn:
        escalated = pd.read_sql(
            text(
                """SELECT * FROM flagged_transactions
                   WHERE status IN ('escalate_no_response', 'escalated_no_response')
                   ORDER BY fraud_score DESC, expires_at ASC"""
            ),
            conn,
        )

    if escalated.empty:
        st.success("All clear — there are no escalated cases waiting for review.")
        return

    st.caption(f"{len(escalated)} case{'s' if len(escalated) != 1 else ''} awaiting review")
    for _, row in escalated.iterrows():
        with st.container(border=True):
            head = st.columns([2, 1, 1, 1])
            head[0].write("**Subscriber**")
            head[0].write(str(row["phone_number"]))
            head[1].write("**Risk**")
            head[1].markdown(
                f'<span class="risk-pill" style="--risk-color:{_risk_color(row["risk_level"], light_theme)}">'
                f'{str(row["risk_level"]).title()} risk</span>',
                unsafe_allow_html=True,
            )
            head[2].write("**Amount**")
            head[2].write(f"{float(row['amount']):,.2f}")
            head[3].write("**Fraud score**")
            head[3].write(f"{float(row['fraud_score']):.0%}")

            try:
                scored_at = pd.Timestamp(row["scored_at"])
                waiting = max(pd.Timedelta(0), pd.Timestamp.now() - scored_at)
                waiting_text = f"Waiting {int(waiting.total_seconds() // 60)} min"
            except (TypeError, ValueError):
                waiting_text = "Waiting time unavailable"
            deadline = row.get("expires_at")
            if pd.notna(deadline):
                try:
                    overdue = max(pd.Timedelta(0), pd.Timestamp.now() - pd.Timestamp(deadline))
                    deadline_text = f"Overdue by {int(overdue.total_seconds() // 60)} min"
                except (TypeError, ValueError):
                    deadline_text = "Response deadline passed"
            else:
                deadline_text = "No response within 5 minutes"
            st.caption(f"{waiting_text} · {deadline_text} · Scored {row['scored_at']}")

            col1, col2, col3 = st.columns([1.5, 1.5, 1])
            method = col1.selectbox(
                "Verification method",
                verification_methods,
                key=f"m_{row['id']}",
            )
            detail = col2.text_input("Resolution note (optional)", key=f"d_{row['id']}")
            with col3:
                st.write("**Decision**")
                confirm = st.button("Confirm fraud", key=f"f_{row['id']}", use_container_width=True)
                clear = st.button("Clear case", key=f"c_{row['id']}", use_container_width=True)

            with st.expander("Review signals and feature snapshot"):
                st.write(f"**In flagged ring:** {'Yes' if bool(row['in_flagged_ring']) else 'No'}")
                st.markdown("#### Risk drivers")
                _render_shap_reasons(row.get("top_reasons"), light_theme)
                with st.expander("Full feature snapshot"):
                    features = _decode_json(row.get("features_json"), {})
                    st.json(features if isinstance(features, dict) else {})

            if confirm or clear:
                if not method:
                    st.error("Choose a verification method before recording this decision.")
                else:
                    next_status = "confirmed_by_ops" if confirm else "cleared_by_ops"
                    set_status(
                        row["txn_id"],
                        status=next_status,
                        resolution_method=method,
                        resolution_note=detail,
                    )
                    decision = "confirmed as fraud" if confirm else "cleared"
                    st.session_state.queue_notice = f"Case {row['txn_id']} was {decision}."
                    st.rerun()


def _render_assistant():
    st.title("AI assistant")
    st.caption("Powered by local Llama 3.2 via Ollama. The assistant needs Ollama and llama3.2:3b running locally.")
    question = st.text_input("Ask about fraud patterns, trends, or system behavior")
    if st.button("Ask", type="primary", disabled=not question.strip()):
        with st.spinner("Preparing a summary and generating an answer…"):
            try:
                with engine.connect() as conn:
                    summary = pd.read_sql(
                        text(
                            """SELECT risk_level, COUNT(*) AS count,
                                      AVG(fraud_score) AS avg_score
                               FROM flagged_transactions
                               WHERE scored_at >= NOW() - INTERVAL 7 DAY
                               GROUP BY risk_level"""
                        ),
                        conn,
                    )
                prompt = (
                    "You are a fraud-analytics assistant. Given this weekly summary:\n"
                    f"{summary.to_dict()}\n"
                    f"Answer the question in 2-3 sentences: {question}"
                )
                response = ollama.chat(
                    model="llama3.2:3b",
                    messages=[{"role": "user", "content": prompt}],
                )
                st.markdown("#### Answer")
                st.write(response["message"]["content"])
            except Exception as exc:
                st.error(f"The assistant is unavailable right now. Check that Ollama is running with llama3.2:3b. ({exc})")


def _render_billing():
    st.title("Billing")
    st.caption("Estimated bill for the current calendar month, based on recorded usage.")
    plan_key = st.selectbox("Plan", ["starter", "growth"])
    with engine.connect() as conn:
        volume = (
            conn.execute(
                text(
                    """SELECT COUNT(*) FROM flagged_transactions
                       WHERE scored_at >= DATE_FORMAT(NOW(), '%Y-%m-01')"""
                )
            ).scalar()
            or 0
        )
    bill = calculate_bill(plan_key, volume)
    cols = st.columns(3)
    cols[0].metric("Transactions this month", bill["transactions_this_month"])
    cols[1].metric("Overage cost", f"${bill['overage_cost']:.2f}")
    cols[2].metric("Estimated total", f"${bill['total']:.2f}")
    st.caption(f"Plan: {bill['plan']} · Included transactions: {bill['included_transactions']:,}")


if page == "Overview":
    _render_overview(light_theme)
elif page == "Escalation queue":
    _render_escalation_queue(light_theme)
elif page == "AI assistant":
    _render_assistant()
else:
    _render_billing()
