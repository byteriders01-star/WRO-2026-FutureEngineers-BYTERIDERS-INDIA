import cv2
import json
import os
import sys

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "robot_config.json")

def nothing(x):
    pass

def run_hsv_tuner():
    print("==================================================")
    print("       WRO 2026 PERCEPTION HSV CALIBRATOR         ")
    print("==================================================")
    print("Use GUI Trackbars to adjust HSV bounds for target color.")
    print("Press 's' to Save to robot_config.json | Press 'q' to Quit.")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Cannot access camera index 0")
        sys.exit(1)

    window_name = "HSV Tuner"
    cv2.namedWindow(window_name)

    cv2.createTrackbar("H Min", window_name, 0, 179, nothing)
    cv2.createTrackbar("H Max", window_name, 179, 179, nothing)
    cv2.createTrackbar("S Min", window_name, 100, 255, nothing)
    cv2.createTrackbar("S Max", window_name, 255, 255, nothing)
    cv2.createTrackbar("V Min", window_name, 70, 255, nothing)
    cv2.createTrackbar("V Max", window_name, 255, 255, nothing)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Failed to grab frame")
            break

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        h_min = cv2.getTrackbarPos("H Min", window_name)
        h_max = cv2.getTrackbarPos("H Max", window_name)
        s_min = cv2.getTrackbarPos("S Min", window_name)
        s_max = cv2.getTrackbarPos("S Max", window_name)
        v_min = cv2.getTrackbarPos("V Min", window_name)
        v_max = cv2.getTrackbarPos("V Max", window_name)

        lower_bound = (h_min, s_min, v_min)
        upper_bound = (h_max, s_max, v_max)

        mask = cv2.inRange(hsv, lower_bound, upper_bound)
        result = cv2.bitwise_and(frame, frame, mask=mask)

        cv2.imshow(window_name, result)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('s'):
            print(f"[INFO] Current HSV Bounds -> LOW: {lower_bound}, HIGH: {upper_bound}")
            try:
                with open(CONFIG_PATH, "r") as f:
                    config = json.load(f)
                config["camera"]["hsv_tuned"] = {
                    "low": list(lower_bound),
                    "high": list(upper_bound)
                }
                with open(CONFIG_PATH, "w") as f:
                    json.dump(config, f, indent=2)
                print("[SUCCESS] Saved tuned parameters to config/robot_config.json")
            except Exception as e:
                print(f"[ERROR] Failed to save config: {e}")

        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_hsv_tuner()
