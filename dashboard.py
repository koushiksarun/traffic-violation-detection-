import streamlit as st
import pandas as pd
import psycopg2
import os

# Database Connection
DATABASE_URL = "postgresql://postgres.uralhonzyplrhtfysiab:[PlIKKuiPMmTTNGgA]@aws-1-us-east-1.pooler.supabase.com:6543/postgres?pgbouncer=true"

@st.cache_data(ttl=5) # Cache data for 5 seconds
def get_data():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        query = "SELECT * FROM vehicles ORDER BY last_seen DESC"
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return pd.DataFrame()

st.set_page_config(page_title="Traffic Monitor Dashboard", layout="wide", page_icon="🚦")
st.title("🚦 Smart Traffic Violation Control Room")

# Fetch Data
df = get_data()

if not df.empty:
    # Sidebar - Stats
    st.sidebar.header("Real-time Stats")
    st.sidebar.metric("Total Vehicles", len(df))
    st.sidebar.metric("Violations Detected", len(df[df['violations'].fillna('').str.len() > 0]))

    # Main View - Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Analytics", "🚨 Violations Log", "🖼️ Evidence Wall"])

    with tab1:
        st.header("Traffic Trends")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Vehicle Types")
            type_counts = df['vehicle_type'].value_counts()
            st.bar_chart(type_counts)
        with col2:
            st.subheader("Violation Types")
            all_v = df['violations'].dropna().str.split(', ').explode()
            all_v = all_v[all_v != ""]
            if not all_v.empty:
                st.bar_chart(all_v.value_counts())
            else:
                st.info("No violations recorded yet.")

    with tab2:
        st.header("Live Violation Feed")
        st.dataframe(df[['track_id', 'vehicle_type', 'license_plate', 'violations', 'max_speed', 'lane_id', 'last_seen']], use_container_width=True)

    with tab3:
        st.header("Evidence Gallery")
        violators = df[df['violations'].fillna('').str.len() > 0]
        if not violators.empty:
            cols = st.columns(3)
            for i, (_, row) in enumerate(violators.iterrows()):
                with cols[i % 3]:
                    if row['image_path'] and os.path.exists(row['image_path']):
                        st.image(row['image_path'], caption=f"ID: {row['track_id']} | Plate: {row['license_plate']} | {row['violations']}")
                    else:
                        st.info(f"ID: {row['track_id']} - Image pending upload from detector.")
        else:
            st.info("No violation images captured yet.")
else:
    st.warning("No data found in database. Make sure the local detector script is running and connected to Supabase.")

# Auto-refresh helper
if st.button('🔄 Force Refresh'):
    st.rerun()
