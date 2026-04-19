import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv
import yt_dlp
import time
import psycopg2
from datetime import datetime
import easyocr
import os
import requests

# --- Configuration ---
YOUTUBE_URL = "https://www.youtube.com/watch?v=wqctLW0Hb_0"
MODEL_PATH = "yolov8n.pt"
DATABASE_URL = "postgresql://postgres.uralhonzyplrhtfysiab:PlIKKuiPMmTTNGgA@aws-1-us-east-1.pooler.supabase.com:6543/postgres"

# Supabase API Details (Required for Image Uploads)
SUPABASE_URL = "https://uralhonzyplrhtfysiab.supabase.co"
SUPABASE_KEY = "YOUR_SUPABASE_ANON_KEY_HERE" # <--- PASTE YOUR ANON KEY HERE

# Detection Settings
PROCESS_WIDTH = 640
STOP_LINE_Y = 500
TARGET_CLASSES = [2, 3, 5, 7, 9]
CLASS_NAMES = {2: "Car", 3: "Motorcycle", 5: "Bus", 7: "Truck", 9: "Traffic Light"}

# Initialize OCR & Annotators
reader = easyocr.Reader(['en'], gpu=True)
box_annotator_safe = sv.BoxAnnotator(color=sv.Color.GREEN, thickness=2)
box_annotator_violation = sv.BoxAnnotator(color=sv.Color.RED, thickness=4)
label_annotator = sv.LabelAnnotator(text_scale=0.5, text_thickness=1)

def init_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicles (
                id SERIAL PRIMARY KEY,
                track_id INTEGER UNIQUE,
                vehicle_type TEXT,
                license_plate TEXT,
                first_seen TIMESTAMP,
                last_seen TIMESTAMP,
                violations TEXT,
                max_speed REAL,
                image_path TEXT,
                lane_id TEXT
            )
        ''')
        conn.commit()
        return conn
    except Exception as e:
        print(f"DB Error: {e}")
        return None

def upload_image(file_path, file_name):
    """Uploads local image to Supabase Storage and returns the public URL"""
    if SUPABASE_KEY == "YOUR_SUPABASE_ANON_KEY_HERE":
        return file_path # Fallback to local path if key not set
    
    url = f"{SUPABASE_URL}/storage/v1/object/violations/{file_name}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
        "Content-Type": "image/jpeg"
    }
    
    try:
        with open(file_path, "rb") as f:
            response = requests.post(url, headers=headers, data=f)
            if response.status_code == 200:
                # Construct public URL
                return f"{SUPABASE_URL}/storage/v1/object/public/violations/{file_name}"
            else:
                print(f"Upload failed: {response.text}")
                return file_path
    except Exception as e:
        print(f"Upload error: {e}")
        return file_path

def upsert_vehicle(conn, data):
    if conn is None: return
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO vehicles (track_id, vehicle_type, license_plate, first_seen, last_seen, violations, max_speed, image_path, lane_id)
            VALUES (%(track_id)s, %(type)s, %(plate)s, %(now)s, %(now)s, %(violations)s, %(speed)s, %(img)s, %(lane)s)
            ON CONFLICT (track_id) DO UPDATE SET
                last_seen = EXCLUDED.last_seen,
                violations = CASE 
                    WHEN vehicles.violations IS NULL OR vehicles.violations = '' THEN EXCLUDED.violations
                    WHEN EXCLUDED.violations IS NULL OR EXCLUDED.violations = '' THEN vehicles.violations
                    ELSE vehicles.violations || ', ' || EXCLUDED.violations END,
                max_speed = GREATEST(vehicles.max_speed, EXCLUDED.max_speed),
                license_plate = COALESCE(EXCLUDED.license_plate, vehicles.license_plate),
                image_path = COALESCE(EXCLUDED.image_path, vehicles.image_path),
                lane_id = EXCLUDED.lane_id
        ''', data)
        conn.commit()
    except Exception as e:
        conn.rollback()

def get_license_plate(frame, box):
    x1, y1, x2, y2 = map(int, box)
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0: return None
    results = reader.readtext(roi)
    return max(results, key=lambda x: x[2])[1] if results else None

def main():
    ydl_opts = {'format': 'best', 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        stream_url = ydl.extract_info(YOUTUBE_URL, download=False)['url']

    conn = init_db()
    model = YOLO(MODEL_PATH)
    cap = cv2.VideoCapture(stream_url)
    
    vehicle_history = {} 
    traffic_light_state = "GREEN"
    if not os.path.exists("violations"): os.makedirs("violations")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        
        small_frame = cv2.resize(frame, (PROCESS_WIDTH, int(frame.shape[0] * (PROCESS_WIDTH / frame.shape[1]))))
        results = model.track(small_frame, persist=True, classes=TARGET_CLASSES, verbose=False, imgsz=PROCESS_WIDTH)[0]
        
        detections = sv.Detections.from_ultralytics(results)
        scale = frame.shape[1] / PROCESS_WIDTH
        detections.xyxy = detections.xyxy * scale

        now = datetime.now()
        violator_mask = []
        labels = []

        for i, (xyxy, track_id, class_id) in enumerate(zip(detections.xyxy, detections.tracker_id, detections.class_id)):
            if track_id is None: 
                violator_mask.append(False); labels.append("Unknown"); continue
            
            x1, y1, x2, y2 = xyxy
            cy = (y1 + y2) / 2
            v_type = CLASS_NAMES.get(int(class_id), "Unknown")
            
            if track_id not in vehicle_history:
                vehicle_history[track_id] = {'start_y': cy, 'violations': set(), 'evidence_done': False}
            
            hist = vehicle_history[track_id]
            is_violating = (traffic_light_state == "RED" and cy > STOP_LINE_Y and hist['start_y'] <= STOP_LINE_Y)
            
            plate, web_img_url = None, None
            if is_violating:
                hist['violations'].add("RED LIGHT")
                if not hist['evidence_done']:
                    # 1. Capture & Save Locally
                    file_name = f"id_{track_id}_redlight.jpg"
                    local_path = f"violations/{file_name}"
                    cv2.imwrite(local_path, frame[int(y1):int(y2), int(x1):int(x2)])
                    # 2. Upload to Cloud
                    print(f"📸 Capturing violation for ID: {track_id}...")
                    web_img_url = upload_image(local_path, file_name)
                    # 3. Get Plate
                    plate = get_license_plate(frame, xyxy)
                    hist['evidence_done'] = True

            violator_mask.append(is_violating or len(hist['violations']) > 0)
            status = ", ".join(hist['violations']) if hist['violations'] else "OK"
            labels.append(f"#{track_id} {v_type} [{status}]")

            upsert_vehicle(conn, {
                'track_id': int(track_id), 'type': v_type, 'plate': plate, 'now': now,
                'violations': status, 'speed': 0.0, 'img': web_img_url, 'lane': "Lane_1"
            })

        # Visualization
        violator_mask = np.array(violator_mask)
        annotated_frame = box_annotator_safe.annotate(scene=frame, detections=detections[~violator_mask])
        annotated_frame = box_annotator_violation.annotate(scene=annotated_frame, detections=detections[violator_mask])
        annotated_frame = label_annotator.annotate(scene=annotated_frame, detections=detections, labels=labels)
        
        cv2.line(annotated_frame, (0, int(STOP_LINE_Y)), (frame.shape[1], int(STOP_LINE_Y)), (0,0,255) if traffic_light_state == "RED" else (0,255,0), 3)
        cv2.imshow("Smart Traffic AI - Cloud Upload Enabled", cv2.resize(annotated_frame, (1280, 720)))
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release(); cv2.destroyAllWindows()

if __name__ == "__main__": main()
