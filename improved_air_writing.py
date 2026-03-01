import cv2
import mediapipe as mp
import numpy as np
import math

# --- Configuration & Constants ---
SMOOTHING_FACTOR = 0.5  # EMA factor: lower = smoother but more lag, higher = more responsive
PINCH_THRESHOLD = 40    # Distance in pixels between thumb and index to trigger "Pen Down"
LINE_COLOR = (255, 255, 255)
LINE_THICKNESS = 8
CURSOR_COLOR = (0, 255, 0) # Green for "Move", will change to Red/White for "Draw"
CANVAS_ALPHA = 0.6      # Transparency level for the canvas overlay

# --- Initialize MediaPipe Hand Tracking ---
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)
mp_draw = mp.solutions.drawing_utils

# --- Smoothing State ---
class EMASmoother:
    def __init__(self, alpha=0.5):
        self.alpha = alpha
        self.val = None

    def update(self, new_val):
        if self.val is None:
            self.val = new_val
        else:
            self.val = self.alpha * np.array(new_val) + (1 - self.alpha) * self.val
        return self.val

# Initialize smoothers for X and Y
x_smooth = EMASmoother(alpha=SMOOTHING_FACTOR)
y_smooth = EMASmoother(alpha=SMOOTHING_FACTOR)

# --- App State ---
canvas = None
prev_x, prev_y = None, None
is_drawing = False

def get_distance(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

cap = cv2.VideoCapture(0)

print("--- SmartyBee Improved Air Writing ---")
print("Controls:")
print("  - Pinch Thumb and Index finger to DRAW")
print("  - Release pinch to MOVE")
print("  - Press 'c' to CLEAR canvas")
print("  - Press 'q' to QUIT")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break

    # 1. Image Preprocessing
    frame = cv2.flip(frame, 1)  # Mirror effect
    h, w, c = frame.shape
    
    if canvas is None:
        canvas = np.zeros((h, w, 3), dtype="uint8")

    # 2. Hand Tracking
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_frame)

    current_x, current_y = None, None
    gesture_detected = False

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            # Landmark 8: Index Finger Tip
            # Landmark 4: Thumb Tip
            landmarks = hand_landmarks.landmark
            
            # Raw coordinates
            raw_idx_x = landmarks[8].x * w
            raw_idx_y = landmarks[8].y * h
            
            # 3. Apply EMA Smoothing
            current_x = int(x_smooth.update(raw_idx_x))
            current_y = int(y_smooth.update(raw_idx_y))
            
            # 4. Gesture Detection: Pinch to Draw
            # Calculate distance between thumb tip and index tip in pixel space
            thumb_tip = landmarks[4]
            index_tip = landmarks[8]
            
            # Convert to pixel distance for thresholding
            dist_px = math.sqrt(((thumb_tip.x - index_tip.x) * w)**2 + 
                                ((thumb_tip.y - index_tip.y) * h)**2)
            
            is_drawing = dist_px < PINCH_THRESHOLD
            
            # 5. Drawing Logic
            if is_drawing:
                if prev_x is not None and prev_y is not None:
                    cv2.line(canvas, (prev_x, prev_y), (current_x, current_y), LINE_COLOR, LINE_THICKNESS)
                prev_x, prev_y = current_x, current_y
                status_color = (0, 0, 255) # Red for Drawing
                status_text = "WRITING"
            else:
                prev_x, prev_y = None, None # Reset line start
                status_color = (0, 255, 0) # Green for Moving
                status_text = "MOVING"

            # Draw visual feedback on the frame
            cv2.circle(frame, (current_x, current_y), 10, status_color, -1)
            cv2.putText(frame, status_text, (current_x + 10, current_y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
            
            # Optional: draw landmarks for debugging
            # mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

    # 6. Composite Canvas and Frame
    # Create mask where canvas has content
    canvas_gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(canvas_gray, 10, 255, cv2.THRESH_BINARY)
    mask_inv = cv2.bitwise_not(mask)
    
    # Black out the area of the line in the frame
    img_bg = cv2.bitwise_and(frame, frame, mask=mask_inv)
    # Take only region of line from canvas
    img_fg = cv2.bitwise_and(canvas, canvas, mask=mask)
    
    # Combine (with alpha blending to see camera through drawing slightly if desired)
    # Here we just overlay the white lines solidly for clarity
    combined = cv2.add(img_bg, img_fg)

    # Add UI Overlay
    cv2.putText(combined, "SmartyBee Air-Write", (20, 40), cv2.FONT_HERSHEY_DUPLEX, 1, (255, 100, 0), 2)
    cv2.putText(combined, "'c' to clear | 'q' to quit", (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    cv2.imshow('SmartyBee - Smooth Air Writing', combined)

    # 7. Key Controls
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('c'):
        canvas = np.zeros((h, w, 3), dtype="uint8")

cap.release()
cv2.destroyAllWindows()
