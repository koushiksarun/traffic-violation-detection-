import streamlit as st
import pandas as pd
import psycopg2
import os
from datetime import datetime

# --- Configuration ---
DATABASE_URL = "postgresql://postgres.uralhonzyplrhtfysiab:PlIKKuiPMmTTNGgA@aws-1-us-east-1.pooler.supabase.com:6543/postgres"

# --- Page Config ---
st.set_page_config(
    page_title="AI Traffic Command",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS for "Themeful" Interface ---
st.markdown("""
    <style>
    /* Main Background */
    .stApp {
        background-color: #0e1117;
        color: #e0e0e0;
    }
    
    /* Custom Header */
    .main-header {
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        letter-spacing: -1px;
        background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        margin-bottom: 1rem;
    }
    
    /* Glassmorphism Cards */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        backdrop-filter: blur(4px);
    }
    
    /* Violator Alert Card */
    .violation-card {
        background: rgba(255, 75, 75, 0.1);
        border-left: 5px solid #ff4b4b;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    
    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 10px 10px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(79, 172, 254, 0.2) !important;
        border-bottom: 2px solid #4facfe !important;
    }
    
    /* Evidence Wall Images */
    .evidence-img {
        border-radius: 12px;
        border: 2px solid rgba(255, 255, 255, 0.1);
        transition: transform 0.3s ease;
    }
    .evidence-img:hover {
        transform: scale(1.05);
        border-color: #ff4b4b;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Data Engine ---
@st.cache_data(ttl=2)
def fetch_live_data():
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        df = pd.read_sql("SELECT * FROM vehicles ORDER BY last_seen DESC", conn)
        conn.close()
        return df, "Connected"
    except Exception as e:
        return pd.DataFrame(), str(e)

# --- Layout ---
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown('<h1 class="main-header">AI TRAFFIC COMMAND</h1>', unsafe_allow_html=True)

df, status = fetch_live_data()

if status != "Connected":
    st.error(f"🛑 DATABASE CONNECTION FAILED: {status}")
    st.info("""
        ### 🛠️ How to fix this:
        1. **Supabase Network Settings**: Go to Supabase -> Settings -> Network. Allow `0.0.0.0/0`.
        2. **Database Password**: Ensure the password in `dashboard.py` is correct.
        3. **Port**: Make sure port `6543` (Pooler) or `5432` (Direct) is accessible.
    """)
    st.stop()

if not df.empty:
    # --- Sidebar Overview ---
    st.sidebar.image("https://img.icons8.com/fluency/96/000000/traffic-light.png", width=80)
    st.sidebar.title("Operational Hub")
    
    total_v = len(df)
    total_violation = len(df[df['violations'].fillna('').str.len() > 0])
    v_rate = (total_violation / total_v * 100) if total_v > 0 else 0
    
    st.sidebar.metric("ACTIVE TRACKS", total_v, delta=f"+{len(df[df['last_seen'] > pd.Timestamp.now() - pd.Timedelta(minutes=5)])} fresh")
    st.sidebar.metric("TOTAL VIOLATIONS", total_violation, delta=f"{v_rate:.1f}% rate", delta_color="inverse")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Recent Alerts")
    recent_violators = df[df['violations'].fillna('').str.len() > 0].head(3)
    for _, v in recent_violators.iterrows():
        st.sidebar.markdown(f"""
            <div class="violation-card">
                <b>ID: {v['track_id']}</b><br>
                Type: {v['vehicle_type']}<br>
                <span style="color:#ff4b4b">⚠ {v['violations']}</span>
            </div>
        """, unsafe_allow_html=True)

    # --- Main Dashboard Tabs ---
    tab_vis, tab_data, tab_wall = st.tabs(["📉 SYSTEM ANALYTICS", "📝 VIOLATION LEDGER", "📸 EVIDENCE VAULT"])

    with tab_vis:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Vehicle Composition")
            type_counts = df['vehicle_type'].value_counts()
            st.bar_chart(type_counts, color="#4facfe")
            
        with c2:
            st.subheader("Violation Distribution")
            all_v = df['violations'].dropna().str.split(', ').explode()
            all_v = all_v[all_v != ""]
            if not all_v.empty:
                st.bar_chart(all_v.value_counts(), color="#ff4b4b")
            else:
                st.info("System monitoring... No violations currently logged.")

        st.markdown("---")
        st.subheader("Speed Heatmap (Estimated)")
        st.line_chart(df.set_index('last_seen')['max_speed'].head(50), color="#00f2fe")

    with tab_data:
        st.subheader("Complete Traffic Records")
        st.dataframe(
            df[['track_id', 'vehicle_type', 'license_plate', 'violations', 'max_speed', 'lane_id', 'last_seen']],
            width='stretch',
            column_config={
                "track_id": "ID",
                "violations": st.column_config.TextColumn("Violation Status", width="medium"),
                "max_speed": st.column_config.NumberColumn("Speed (km/h)", format="%.1f"),
                "last_seen": "Timestamp"
            }
        )

    with tab_wall:
        st.subheader("High-Resolution Evidence")
        violators = df[df['violations'].fillna('').str.len() > 0]
        if not violators.empty:
            grid = st.columns(4)
            for i, (_, row) in enumerate(violators.iterrows()):
                with grid[i % 4]:
                    img_path = row['image_path']
                    caption = f"ID:{row['track_id']} | {row['license_plate'] or 'NO PLATE'}"

                    # Robust path check to prevent AttributeError
                    if isinstance(img_path, str) and img_path.strip():
                        if img_path.startswith("http"):
                            st.image(img_path, caption=caption, use_container_width=True)
                        elif os.path.exists(img_path):
                            st.image(img_path, caption=caption, use_container_width=True)
                        else:
                            st.warning(f"ID {row['track_id']}: Image missing")
                    else:
                        st.info(f"ID {row['track_id']}: Syncing...")
        else:
            st.info("Evidence vault is currently empty. System is securing the perimeter.")


else:
    st.error("SYSTEM OFFLINE: No connection to Supabase detected.")
    st.info("Check your DATABASE_URL and ensure the local detector script is active.")
