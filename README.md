# Smart Traffic Violation Detection System

A comprehensive traffic monitoring solution that detects Red Light violations, Speeding, Wrong-Way driving, and Lane Discipline using YOLOv8, EasyOCR, and Supabase.

## 🚀 Features
- **Real-time Tracking**: Tracks vehicles using BoT-SORT/ByteTrack.
- **Violation Logic**: Red Light, Speeding, and Wrong-Way detection.
- **LPR**: Automatic License Plate Recognition on violations.
- **Cloud Dashboard**: Live Streamlit dashboard with evidence wall and analytics.
- **Supabase Integration**: Data persistence in a PostgreSQL cloud database.

## 🛠️ Setup
1.  **Clone the Repo**:
    `git clone <your-repo-url>`
2.  **Install Dependencies**:
    `pip install -r requirements.txt`
3.  **Run the Detector**:
    `python traffic_violation_detector.py`
4.  **Run the Dashboard**:
    `streamlit run dashboard.py`

## 📊 Deployment
The dashboard is designed for easy deployment to **Streamlit Cloud**:
1. Push this code to GitHub.
2. Connect your repo to Streamlit Cloud.
3. Your dashboard will be live on a public domain!
