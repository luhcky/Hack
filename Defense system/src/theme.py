import streamlit as st


def inject_theme(mode="dark"):
    """Apply the dashboard's dark teal or light operations-console theme."""
    light = mode == "light"
    colors = {
        "background": "#f3f6f8" if light else "#081216",
        "surface": "#ffffff" if light else "#102127",
        "surface_alt": "#eef3f5" if light else "#142a30",
        "border": "#d7e0e4" if light else "#244047",
        "text": "#172b32" if light else "#e5f1ef",
        "muted": "#52666d" if light else "#a5bbb8",
        "accent": "#087e8b" if light else "#5eead4",
        "accent_text": "#ffffff" if light else "#09201f",
        "sidebar_glass": "rgba(255,255,255,0.62)" if light else "rgba(94,234,212,0.055)",
        "sidebar_glass_hover": "rgba(255,255,255,0.92)" if light else "rgba(94,234,212,0.12)",
        "sidebar_glass_active": "rgba(8,126,139,0.12)" if light else "rgba(94,234,212,0.14)",
        "sidebar_glass_border": "rgba(8,126,139,0.20)" if light else "rgba(148,255,239,0.16)",
        "sidebar_control": "#ffffff" if light else "#102127",
        "sidebar_control_text": "#087e8b" if light else "#5eead4",
        "sidebar_surface": "rgba(247,251,252,0.94)" if light else "rgba(13,31,37,0.90)",
    }
    st.markdown(
        f"""
        <style>
        :root {{ color-scheme: {'light' if light else 'dark'}; }}
        .stApp {{ background: {colors['background']}; color: {colors['text']}; }}
        [data-testid="stHeader"] {{ background: transparent; }}
        [data-testid="stSidebar"] {{
            background: {colors['sidebar_surface']};
            border-right: 1px solid {colors['border']};
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
        }}
        [data-testid="stSidebar"] .stButton > button {{
            display: flex; align-items: center; justify-content: flex-start;
            box-sizing: border-box; width: 100%; min-height: 2.85rem;
            margin: 0.28rem 0; padding: 0.7rem 0.9rem;
            text-align: left; border-radius: 12px;
            border: 1px solid {colors['sidebar_glass_border']};
            background: {colors['sidebar_glass']};
            color: {colors['text']} !important;
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.08),
                        0 5px 16px rgba(0,0,0,0.045);
            transition: background 150ms ease, border-color 150ms ease,
                        transform 150ms ease, box-shadow 150ms ease;
        }}
        [data-testid="stSidebar"] .stButton > button span,
        [data-testid="stSidebar"] .stButton > button p {{
            color: inherit !important; font-weight: 600;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
            background: {colors['sidebar_glass_hover']};
            border-color: {colors['accent']}; transform: translateX(2px);
        }}
        [data-testid="stSidebar"] .stButton > button[kind="primary"] {{
            background: linear-gradient(115deg, {colors['sidebar_glass_active']}, {colors['sidebar_glass']});
            border: 1px solid {colors['accent']};
            color: {colors['accent']} !important;
            box-shadow: inset 3px 0 0 {colors['accent']},
                        0 7px 20px rgba(0,0,0,0.08);
        }}
        [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {{
            background: linear-gradient(115deg, {colors['sidebar_glass_hover']}, {colors['sidebar_glass_active']});
            border-color: {colors['accent']}; color: {colors['accent']} !important;
        }}
        [data-testid="stSidebar"] .stButton > button:focus-visible {{
            outline: 3px solid {colors['accent']}; outline-offset: 2px;
        }}
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="stSidebarCollapsedControl"] button,
        button[data-testid="stSidebarCollapsedControl"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stSidebarCollapseButton"] button {{
            width: 2.55rem; height: 2.55rem; min-width: 2.55rem;
            display: inline-flex; align-items: center; justify-content: center;
            background: {colors['sidebar_control']} !important;
            color: {colors['sidebar_control_text']} !important;
            border: 1px solid {colors['accent']} !important;
            border-radius: 11px !important;
            opacity: 1 !important; visibility: visible !important;
            box-shadow: 0 5px 16px rgba(0,0,0,0.12);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            z-index: 1001;
        }}
        [data-testid="stSidebarCollapseButton"] *,
        [data-testid="stSidebarCollapsedControl"] *,
        button[data-testid="stSidebarCollapsedControl"] * {{
            color: {colors['sidebar_control_text']} !important;
            fill: {colors['sidebar_control_text']} !important;
            stroke: {colors['sidebar_control_text']} !important;
            opacity: 1 !important; visibility: visible !important;
        }}
        [data-testid="stSidebarCollapsedControl"]:hover,
        [data-testid="stSidebarCollapsedControl"] button:hover,
        button[data-testid="stSidebarCollapsedControl"]:hover,
        [data-testid="stSidebarCollapseButton"]:hover,
        [data-testid="stSidebarCollapseButton"] button:hover {{
            border-color: {colors['accent']} !important;
            color: {colors['accent']} !important;
        }}
        [data-testid="stSidebarCollapsedControl"] svg,
        [data-testid="stSidebarCollapsedControl"] button svg,
        button[data-testid="stSidebarCollapsedControl"] svg,
        [data-testid="stSidebarCollapseButton"] svg,
        [data-testid="stSidebarCollapseButton"] button svg {{
            color: {colors['sidebar_control_text']} !important;
            fill: currentColor !important;
            opacity: 1 !important;
        }}
        [data-testid="stAppViewContainer"] button[kind="header"] {{
            color: {colors['sidebar_control_text']} !important;
            opacity: 1 !important;
        }}
        [data-testid="stAppViewContainer"] button[kind="header"] svg {{
            color: {colors['sidebar_control_text']} !important;
            fill: {colors['sidebar_control_text']} !important;
            opacity: 1 !important;
        }}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
            color: {colors['muted']};
        }}
        [data-testid="stMetric"] {{
            background: {colors['surface']};
            border: 1px solid {colors['border']};
            border-radius: 14px;
            padding: 16px 18px;
        }}
        [data-testid="stMetricLabel"] {{ color: {colors['muted']}; }}
        [data-testid="stMetricValue"] {{ color: {colors['text']}; }}
        [data-testid="stMetricDelta"] {{ font-size: 0.78rem; }}
        .stApp h1, .stApp h2, .stApp h3, .stApp h4 {{
            color: {colors['text']}; letter-spacing: -0.02em;
        }}
        .stApp p, .stApp label, .stApp [data-testid="stMarkdownContainer"] {{
            color: {colors['text']};
        }}
        .stApp [data-testid="stCaptionContainer"] p {{ color: {colors['muted']}; }}
        .stButton > button {{
            border-radius: 9px;
            border: 1px solid {colors['border']};
            background: {colors['surface_alt']};
            color: {colors['text']};
            min-height: 2.55rem;
        }}
        .stButton > button:hover {{ border-color: {colors['accent']}; color: {colors['accent']}; }}
        .stButton > button[kind="primary"] {{
            background: {colors['accent']}; color: {colors['accent_text']};
            border-color: {colors['accent']};
        }}
        [data-baseweb="select"] > div, .stTextInput input {{
            background: {colors['surface']};
            border-color: {colors['border']};
            color: {colors['text']};
            border-radius: 9px;
        }}
        input[type="checkbox"], input[type="radio"] {{ accent-color: {colors['accent']}; }}
        [data-testid="stSidebar"] [role="switch"][aria-checked="true"] {{
            background-color: {colors['accent']} !important;
        }}
        [data-testid="stDataFrame"] {{
            border: 1px solid {colors['border']}; border-radius: 12px; overflow: hidden;
        }}
        [data-testid="stExpander"] {{
            border: 1px solid {colors['border']}; border-radius: 12px;
        }}
        [data-testid="stVerticalBlockBorderWrapper"] {{
            border-color: {colors['border']}; border-radius: 14px;
            background: {colors['surface']};
        }}
        .risk-pill {{
            display: inline-block; padding: 0.25rem 0.65rem; border-radius: 999px;
            border: 1px solid var(--risk-color); color: var(--risk-color);
            font-size: 0.82rem; font-weight: 700; line-height: 1.2;
            background: color-mix(in srgb, var(--risk-color) 12%, transparent);
        }}
        @media (max-width: 600px) {{
            [data-testid="stHorizontalBlock"] {{
                flex-wrap: wrap !important; gap: 0.5rem !important;
            }}
            [data-testid="stHorizontalBlock"] > [data-testid="column"] {{
                flex: 1 1 44% !important; min-width: 44% !important;
            }}
            [data-testid="stMetric"] {{ padding: 12px; }}
            [data-testid="stMetricValue"] {{ font-size: 1.35rem; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
