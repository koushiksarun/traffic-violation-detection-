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

# --- Configuration & ROIs ---
YOUTUBE_URL = "https://www.youtube.com/watch?v=wqctLW0Hb_0"
MODEL_PATH = "yolov8n.pt"
DATABASE_URL = "postgresql://postgres.uralhonzyplrhtfysiab:[PlIKKuiPMmTTNGgA]@aws-1-us-east-1.pooler.supabase.com:6543/postgres?pgbouncer=true"

# 1. Perspective Correction Points (Source -> Destination)
# These should be 4 points forming a rectangle in the real world (e.g., a patch of road)
SOURCE_POINTS = np.array([[460, 400], [820, 400], [200, 700], [1080, 700]], dtype=np.float32)
DEST_POINTS = np.array([[0, 0], [400, 0], [0, 800], [400, 800]], dtype=np.float32)
M = cv2.getPerspectiveTransform(SOURCE_POINTS, DEST_POINTS)

# 2. Lane Definitions (Polygons)
LANES = {
    "Lane_1": np.array([[400, 400], [640, 400], [300, 720], [0, 720]]),
    "Lane_2": np.array([[640, 400], [880, 400], [1280, 720], [300, 720]])
}

STOP_LINE_Y = 500
TARGET_CLASSES = [2, 3, 5, 7, 9]
CLASS_NAMES = {2: "Car", 3: "Motorcycle", 5: "Bus", 7: "Truck", 9: "Traffic Light"}

# Initialize OCR
reader = easyocr.Reader(['en'], gpu=True)

# --- Database & Storage Logic ---

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

# --- Core Logic ---

def get_birdseye_pos(x, y):
    point = np.array([[[x, y]]], dtype=np.float32)
    transformed = cv2.perspectiveTransform(point, M)
    return transformed[0][0]

def get_lane(x, y):
    point = (x, y)
    for lane_id, poly in LANES.items():
        if cv2.pointPolygonTest(poly, point, False) >= 0:
            return lane_id
    return "Unknown"

def get_license_plate(frame, box):
    x1, y1, x2, y2 = map(int, box)
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0: return None
    results = reader.readtext(roi)
    if results:
        # Return the text with highest confidence
        return max(results, key=lambda x: x[2])[1]
    return None

def main():
    ydl_opts = {'format': 'best', 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        stream_url = ydl.extract_info(YOUTUBE_URL, download=False)['url']

    conn = init_db()
    model = YOLO(MODEL_PATH)
    cap = cv2.VideoCapture(stream_url)
    
    vehicle_history = {} # track_id: {prev_pos, prev_time, ...}
    traffic_light_state = "GREEN"

    if not os.path.exists("violations"): os.makedirs("violations")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        
        results = model.track(frame, persist=True, classes=TARGET_CLASSES, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(results)
        
        now = datetime.now()

        for i, (xyxy, track_id, class_id) in enumerate(zip(detections.xyxy, detections.tracker_id, detections.class_id)):
            if track_id is None: continue
            
            x1, y1, x2, y2 = xyxy
            cx, cy = (x1+x2)/2, (y1+y2)/2
            v_type = CLASS_NAMES.get(int(class_id), "Unknown")
            
            # 1. Perspective Corrected Speed
            be_pos = get_birdseye_pos(cx, cy)
            current_time = time.time()
            
            speed = 0.0
            if track_id in vehicle_history:
                hist = vehicle_history[track_id]
                dist = np.linalg.norm(be_pos - hist['be_pos'])
                dt = current_time - hist['time']
                if dt > 0:
                    speed = (dist / dt) * 0.5  # Calibration factor
                hist['be_pos'], hist['time'] = be_pos, current_time
            else:
                vehicle_history[track_id] = {'be_pos': be_pos, 'time': current_time, 'start_y': cy, 'violations': set()}
                hist = vehicle_history[track_id]

            # 2. Lane & Violation Logic
            lane_id = get_lane(cx, cy)
            new_violation = None
            
            if traffic_light_state == "RED" and cy > STOP_LINE_Y and hist['start_y'] <= STOP_LINE_Y:
                new_violation = "RED LIGHT"
            elif speed > 80:
                new_violation = "SPEEDING"
            
            # 3. Evidence Capture (OCR & Image)
            plate = None
            img_path = None
            if new_violation and new_violation not in hist['violations']:
                hist['violations'].add(new_violation)
                plate = get_license_plate(frame, xyxy)
                img_path = f"violations/id_{track_id}_{new_violation.replace(' ', '_')}.jpg"
                cv2.imwrite(img_path, frame[int(y1):int(y2), int(x1):int(x2)])
            
            # 4. DB Sync
            upsert_vehicle(conn, {
                'track_id': int(track_id),
                'type': v_type,
                'plate': plate,
                'now': now,
                'violations': new_violation,
                'speed': float(speed),
                'img': img_path,
                'lane': lane_id
            })

        # Visualization
        for lane_id, poly in LANES.items():
            cv2.polylines(frame, [poly.astype(np.int32)], True, (255, 255, 0), 2)
        
        cv2.imshow("Smart Traffic System", cv2.resize(frame, (1280, 720)))
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__": main()
