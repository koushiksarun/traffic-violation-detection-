import streamlit as st
import pandas as pd
import psycopg2
import os

# Database Connection
DATABASE_URL = "postgresql://postgres.uralhonzyplrhtfysiab:[PlIKKuiPMmTTNGgA]@aws-1-us-east-1.pooler.supabase.com:6543/postgres?pgbouncer=true"

def get_data():
    conn = psycopg2.connect(DATABASE_URL)
    query = "SELECT * FROM vehicles ORDER BY last_seen DESC"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

st.set_page_config(page_title="Smart Traffic Dashboard", layout="wide")
st.title("🚦 Smart Traffic Violation Control Room")

# Sidebar - Stats
df = get_data()
st.sidebar.header("Real-time Stats")
st.sidebar.metric("Total Vehicles", len(df))
st.sidebar.metric("Violations Detected", len(df[df['violations'] != ""]))

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
        # Split combined violations and count
        all_v = df['violations'].str.split(', ').explode()
        all_v = all_v[all_v != ""]
        if not all_v.empty:
            st.bar_chart(all_v.value_counts())

with tab2:
    st.header("Live Violation Feed")
    st.dataframe(df[['track_id', 'vehicle_type', 'license_plate', 'violations', 'max_speed', 'lane_id', 'last_seen']], use_container_width=True)

with tab3:
    st.header("Evidence Gallery")
    violators = df[df['violations'] != ""]
    cols = st.columns(3)
    for i, (_, row) in enumerate(violators.iterrows()):
        with cols[i % 3]:
            if row['image_path'] and os.path.exists(row['image_path']):
                st.image(row['image_path'], caption=f"ID: {row['track_id']} | Plate: {row['license_plate']} | {row['violations']}")
            else:
                st.info(f"ID: {row['track_id']} - Image pending upload")

# Auto-refresh
if st.button('🔄 Refresh Data'):
    st.rerun()
