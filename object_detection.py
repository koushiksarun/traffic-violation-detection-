import cv2
import time
import winsound
from ultralytics import YOLO

# Load YOLOv8 pretrained model
model = YOLO("yolov8n.pt")

# Open webcam
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Cannot access camera")
    exit()

print("Starting Distraction Monitor... Press 'q' to exit.")

# --- Configuration ---
DISTRACTION_THRESHOLD = 5.0  # Seconds before the alert triggers
# COCO class IDs: 0 = person, 67 = cell phone
TARGET_CLASSES = [0, 67] 
# ---------------------

phone_detected_start = None
is_distracted = False

while True:
    # Read frame from webcam
    ret, frame = cap.read()

    if not ret:
        print("Failed to grab frame")
        break

    # Run YOLO object detection, filtering only for person and cell phone
    results = model(frame, classes=TARGET_CLASSES, conf=0.5)
    
    phone_in_frame = False
    
    # Check if a cell phone is currently detected
    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            if cls_id == 67: # Cell phone detected
                phone_in_frame = True
                break

    # --- Distraction Logic ---
    if phone_in_frame:
        if phone_detected_start is None:
            # First frame seeing the phone, start the timer
            phone_detected_start = time.time()
        else:
            # Check how long it's been in the frame
            elapsed_time = time.time() - phone_detected_start
            if elapsed_time > DISTRACTION_THRESHOLD:
                is_distracted = True
    else:
        # Phone went away, reset timer and alert
        phone_detected_start = None
        is_distracted = False

    # Draw bounding boxes on frame
    annotated_frame = results[0].plot()

    # --- Alert UI & Sound ---
    if is_distracted:
        # Draw huge red text
        cv2.putText(annotated_frame, "PUT THE PHONE DOWN!", (50, 100), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)
        
        # Play a system beep (Frequency: 1000Hz, Duration: 200ms)
        # Note: winsound only works on Windows
        winsound.Beep(1000, 200)

    # Show frame
    cv2.imshow("Distraction Monitor", annotated_frame)

    # Exit when 'q' key is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release camera
cap.release()
cv2.destroyAllWindows()