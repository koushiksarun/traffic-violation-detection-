import os
from datetime import datetime

RUNTIME_DIR = os.path.join(os.getcwd(), ".runtime")
STREAMLIT_HOME = os.path.join(RUNTIME_DIR, "home")
STREAMLIT_CONFIG = os.path.join(STREAMLIT_HOME, ".streamlit")
os.makedirs(STREAMLIT_CONFIG, exist_ok=True)

os.environ.setdefault("HOME", STREAMLIT_HOME)
os.environ.setdefault("USERPROFILE", STREAMLIT_HOME)
os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

import streamlit as st
import pandas as pd
import psycopg2

# --- Configuration ---
DATABASE_URL = "postgresql://postgres.uralhonzyplrhtfysiab:PlIKKuiPMmTTNGgA@aws-1-us-east-1.pooler.supabase.com:6543/postgres"

# --- Page Config ---
st.set_page_config(
    page_title="AI Traffic Command",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Integrated Theme CSS ---
st.markdown("""
<style>
    :root{
      --bg: #070b14;
      --panel: rgba(15, 22, 38, 0.85);
      --border: rgba(92, 114, 154, 0.2);
      --text: #eef4ff;
      --muted: #9fb0d0;
      --cyan: #22e3ff;
      --blue: #56a8ff;
      --red: #ff4d5a;
      --green: #39d98a;
      --shadow: 0 12px 40px rgba(0, 0, 0, 0.35);
    }

    .stApp {
        background: radial-gradient(circle at top left, rgba(34,227,255,0.10), transparent 28%),
                    linear-gradient(180deg, #050913 0%, #060b14 45%, #08101b 100%);
    }

    /* Custom Components */
    .glow-card {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 22px;
        padding: 22px;
        box-shadow: var(--shadow);
        position: relative;
        overflow: hidden;
    }
    
    .glow-card::after {
        content: "";
        position: absolute;
        inset: -1px;
        border-radius: inherit;
        pointer-events: none;
        box-shadow: 0 0 0 1px rgba(34,227,255,0.10), 0 0 25px rgba(34,227,255,0.05);
    }

    .stat-value {
        font-size: 34px;
        font-weight: 900;
        letter-spacing: -0.02em;
        margin: 10px 0;
    }

    .alert-box {
        background: linear-gradient(180deg, rgba(96, 28, 37, 0.25), rgba(57, 16, 22, 0.32));
        border: 1px solid rgba(255,77,90,0.24);
        border-radius: 18px;
        padding: 16px;
        margin-bottom: 12px;
    }

    /* Override Streamlit Elements */
    .stTabs [data-baseweb="tab-list"] { gap: 12px; }
    .stTabs [data-baseweb="tab"] {
        padding: 12px 20px;
        border-radius: 14px;
        background: rgba(255,255,255,0.03);
        border: 1px solid var(--border);
        color: var(--muted);
        font-weight: 700;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, rgba(34,227,255,0.14), rgba(86,168,255,0.08)) !important;
        border-color: var(--cyan) !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Data Engine ---
@st.cache_data(ttl=2)
def fetch_live_data():
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vehicles ORDER BY last_seen DESC")
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(cursor.fetchall(), columns=columns)
        conn.close()
        return df, "Connected"
    except Exception as e:
        return pd.DataFrame(), str(e)

df, status = fetch_live_data()

# --- Sidebar (Operational Hub) ---
with st.sidebar:
    st.markdown(f"""
        <div style="display:flex; align-items:center; gap:14px; margin-bottom:28px;">
            <div style="font-size:32px;">🚦</div>
            <div>
                <h2 style="font-size:18px; margin:0;">Operational Hub</h2>
                <span style="color:var(--muted); font-size:12px;">AI Traffic Intelligence</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    if not df.empty:
        total_v = len(df)
        total_violation = len(df[df['violations'].fillna('').str.len() > 0])
        
        st.markdown(f"""
            <div class="glow-card" style="margin-bottom:20px;">
                <h4 style="color:var(--muted); font-size:11px; text-transform:uppercase;">Active Tracks</h4>
                <div class="stat-value">{total_v}</div>
                <div style="color:var(--green); font-size:12px; font-weight:700;">↑ SYNCED</div>
            </div>
            
            <div class="glow-card" style="margin-bottom:20px;">
                <h4 style="color:var(--muted); font-size:11px; text-transform:uppercase;">Total Violations</h4>
                <div class="stat-value" style="color:var(--red);">{total_violation}</div>
                <div style="color:var(--red); font-size:12px; font-weight:700;">⚠ ACTION REQ</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='color:var(--muted); font-size:12px; text-transform:uppercase; margin:24px 0 12px;'>Recent Alerts</div>", unsafe_allow_html=True)
        recent = df[df['violations'].fillna('').str.len() > 0].head(3)
        for _, row in recent.iterrows():
            st.markdown(f"""
                <div class="alert-box">
                    <h5 style="font-size:13px; margin-bottom:4px;">ID: {row['track_id']} — {row['vehicle_type']}</h5>
                    <p style="color:#ffb5bc; font-size:12px; margin:0;">⚠ {row['violations']}</p>
                </div>
            """, unsafe_allow_html=True)

# --- Main Dashboard ---
if status != "Connected":
    st.error(f"🛑 DATABASE OFFLINE: {status}")
    st.stop()

# Header
col_title, col_actions = st.columns([3, 1])
with col_title:
    st.markdown(f"""
        <h1 style="font-size:46px; font-weight:900; letter-spacing:-0.04em; color:var(--cyan); margin:0;">AI TRAFFIC COMMAND</h1>
        <p style="color:var(--muted); margin-bottom:24px;">Real-time surveillance & violation analysis dashboard</p>
    """, unsafe_allow_html=True)

# Top Metrics
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f'<div class="glow-card"><h4>Total Vehicles</h4><div class="stat-value">{len(df)}</div></div>', unsafe_allow_html=True)
with m2:
    v_count = len(df[df['violations'].fillna('').str.len() > 0])
    st.markdown(f'<div class="glow-card"><h4>Open Violations</h4><div class="stat-value" style="color:var(--red);">{v_count}</div></div>', unsafe_allow_html=True)
with m3:
    avg_speed = df['max_speed'].mean() if not df.empty else 0
    st.markdown(f'<div class="glow-card"><h4>Avg Speed</h4><div class="stat-value">{avg_speed:.1f}<span style="font-size:14px; color:var(--muted);"> km/h</span></div></div>', unsafe_allow_html=True)
with m4:
    st.markdown(f'<div class="glow-card"><h4>System Health</h4><div class="stat-value" style="color:var(--green);">98%</div></div>', unsafe_allow_html=True)

st.write("") # Spacer

# Tabs
tab_analytics, tab_ledger, tab_vault = st.tabs(["📉 SYSTEM ANALYTICS", "📋 VIOLATION LEDGER", "🗃 EVIDENCE VAULT"])

with tab_analytics:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="glow-card"><h3>Vehicle Composition</h3>', unsafe_allow_html=True)
        st.bar_chart(df['vehicle_type'].value_counts(), color="#56a8ff")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="glow-card"><h3>Violation Distribution</h3>', unsafe_allow_html=True)
        all_v = df['violations'].dropna().str.split(', ').explode()
        all_v = all_v[all_v != ""]
        if not all_v.empty:
            st.bar_chart(all_v.value_counts(), color="#ff4d5a")
        else:
            st.info("No violations logged.")
        st.markdown('</div>', unsafe_allow_html=True)

with tab_ledger:
    st.markdown('<div class="glow-card">', unsafe_allow_html=True)
    st.dataframe(
        df[['track_id', 'vehicle_type', 'license_plate', 'violations', 'max_speed', 'last_seen']],
        width='stretch',
        column_config={
            "track_id": "Track ID",
            "last_seen": "Detected At",
            "max_speed": st.column_config.NumberColumn("Speed", format="%.1f km/h")
        }
    )
    st.markdown('</div>', unsafe_allow_html=True)

with tab_vault:
    st.markdown('<div class="glow-card">', unsafe_allow_html=True)
    violators = df[df['violations'].fillna('').str.len() > 0]
    if not violators.empty:
        grid = st.columns(4)
        for i, (_, row) in enumerate(violators.iterrows()):
            with grid[i % 4]:
                img = row['image_path']
                caption = f"ID:{row['track_id']} | {row['license_plate'] or 'SCANNING...'}"

                # Robust type check to handle NaN/Float/None
                if isinstance(img, str) and img.strip():
                    if img.startswith("http") or os.path.exists(img):
                        st.image(img, caption=caption, use_container_width=True)
                    else:
                        st.warning(f"ID {row['track_id']} Syncing...")
                else:
                    st.info(f"ID {row['track_id']} Scanning...")

    else:
        st.info("Evidence vault is empty.")
    st.markdown('</div>', unsafe_allow_html=True)
