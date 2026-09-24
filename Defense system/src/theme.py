import streamlit as st


def inject_theme():
    """Call once, first, before any other st.* calls."""
    st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #071018 0%, #0E2530 50%, #081418 100%);
    }
    div[data-testid="stMetric"] {
        background: rgba(94,234,212,0.05);
        backdrop-filter: blur(14px);
        border: 1px solid rgba(94,234,212,0.18);
        border-radius: 16px;
        padding: 16px;
    }
    div[data-testid="stMetricValue"] { color: #E4FBF7; }
    div[data-testid="stMetricLabel"] { color: #6FA69B; }
    .stButton > button {
        background: rgba(94,234,212,0.1);
        color: #B7F2E6;
        border: 1px solid rgba(94,234,212,0.25);
        border-radius: 8px;
    }
    .stSelectbox > div > div {
        background: rgba(94,234,212,0.06);
        color: #DFFBF4;
        border: 1px solid rgba(94,234,212,0.22);
        border-radius: 8px;
    }
    h1, h2, h3, p, span, label { color: #E4FBF7 !important; }
    </style>
    """, unsafe_allow_html=True)