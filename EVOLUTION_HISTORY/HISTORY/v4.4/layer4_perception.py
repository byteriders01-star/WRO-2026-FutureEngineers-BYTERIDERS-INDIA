import time
import logging
import threading
import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logging.warning("[LAYER 4] OpenCV not available.")

class ThreadedCameraManager:
    """
    Layer 4: Async Multi-Threaded Camera Ingestion & Perception Engine
    Spawns background thread to continuously capture frames at 30 FPS.
    Main control loop accesses perception results instantly without blocking!
    """
    def __init__(self, config: dict):
        self.config = config
        self.cam_config = config.get("camera", {})
        
        self.lock = threading.Lock()
        self.running = False
        self.worker_thread = None

        self.cap = None
        self.latest_perception = {
            "red_pillar": None,
            "green_pillar": None,
            "magenta_marker": None,
            "blue_marker": False,
            "frame_processed": False,
            "camera_ok": False
        }

        if CV2_AVAILABLE:
            self._init_camera()
            self.start_thread()

    def _init_camera(self):
        try:
            device_idx = self.cam_config.get("device_index", 0)
            self.cap = cv2.VideoCapture(device_idx)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cam_config.get("frame_width", 640))
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cam_config.get("frame_height", 480))
            self.cap.set(cv2.CAP_PROP_FPS, self.cam_config.get("fps", 30))
            
            if self.cap.isOpened():
                logging.info("[LAYER 4] OpenCV Camera Ingestion Active.")
                self.latest_perception["camera_ok"] = True
        except Exception as e:
            logging.error(f"[LAYER 4] Camera Init Error: {e}")

    def start_thread(self):
        if self.cap and self.cap.isOpened():
            self.running = True
            self.worker_thread = threading.Thread(target=self._async_camera_loop, daemon=True)
            self.worker_thread.start()
            logging.info("[LAYER 4] Async Perception Thread Spawned.")

    def _async_camera_loop(self):
        """Background Thread: Image processing loop @ 30 FPS."""
        while self.running:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                time.sleep(0.02)
                continue

            perception_res = self._process_frame_internal(frame)
            perception_res["camera_ok"] = True

            with self.lock:
                self.latest_perception = perception_res

            time.sleep(0.01)

    def _process_frame_internal(self, frame) -> dict:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        img_h, img_w = frame.shape[:2]

        # 1. Red Pillars
        r1_low = np.array(self.cam_config.get("hsv_red1", {}).get("low", [0, 120, 70]))
        r1_high = np.array(self.cam_config.get("hsv_red1", {}).get("high", [10, 255, 255]))
        r2_low = np.array(self.cam_config.get("hsv_red2", {}).get("low", [170, 120, 70]))
        r2_high = np.array(self.cam_config.get("hsv_red2", {}).get("high", [180, 255, 255]))

        mask_r1 = cv2.inRange(hsv, r1_low, r1_high)
        mask_r2 = cv2.inRange(hsv, r2_low, r2_high)
        mask_red = cv2.bitwise_or(mask_r1, mask_r2)
        red_res = self._find_largest_contour(mask_red, img_w, img_h)

        # 2. Green Pillars
        g_low = np.array(self.cam_config.get("hsv_green", {}).get("low", [36, 100, 80]))
        g_high = np.array(self.cam_config.get("hsv_green", {}).get("high", [85, 255, 255]))
        mask_green = cv2.inRange(hsv, g_low, g_high)
        green_res = self._find_largest_contour(mask_green, img_w, img_h)

        # 3. Magenta Parking Markers
        m_low = np.array(self.cam_config.get("hsv_magenta", {}).get("low", [135, 80, 50]))
        m_high = np.array(self.cam_config.get("hsv_magenta", {}).get("high", [165, 255, 255]))
        mask_magenta = cv2.inRange(hsv, m_low, m_high)
        magenta_res = self._find_largest_contour(mask_magenta, img_w, img_h)

        # 4. Blue Stop-and-Go Marker
        b_low = np.array(self.cam_config.get("hsv_blue", {}).get("low", [95, 120, 80]))
        b_high = np.array(self.cam_config.get("hsv_blue", {}).get("high", [130, 255, 255]))
        mask_blue = cv2.inRange(hsv[int(img_h * 0.7):, :], b_low, b_high)
        blue_marker = (cv2.countNonZero(mask_blue) > 800)

        return {
            "red_pillar": red_res,
            "green_pillar": green_res,
            "magenta_marker": magenta_res,
            "blue_marker": blue_marker,
            "frame_processed": True
        }

    def _find_largest_contour(self, mask, img_w, img_h) -> dict:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        if area < 300:
            return None

        x, y, w, h = cv2.boundingRect(largest)
        cx = x + (w // 2)
        dist_est_mm = (img_h * 150.0) / float(h) if h > 0 else 9999.0

        return {
            "center_x": cx,
            "normalized_x": (cx - (img_w / 2.0)) / (img_w / 2.0),
            "area": area,
            "bbox": (x, y, w, h),
            "distance_est_mm": round(dist_est_mm, 1)
        }

    def generate_ascii_preview(self) -> str:
        """Converts mask detections into a low-res ASCII string for SSH terminal calibration."""
        with self.lock:
            # We use a very small grid (20x10) for terminal performance
            res = []
            res.append("-" * 22)
            # This is a simplified proxy based on latest perception results
            p = self.latest_perception
            
            grid = [[" " for _ in range(20)] for _ in range(10)]
            
            # Map detected objects to grid cells
            for key, char in [("red_pillar", "R"), ("green_pillar", "G"), ("magenta_marker", "M")]:
                obj = p.get(key)
                if obj:
                    nx = obj["normalized_x"] # [-1, 1]
                    col = int((nx + 1.0) * 9.5)
                    row = 5 # fixed middle row for simplicity
                    grid[row][min(19, max(0, col))] = char
            
            if p.get("blue_marker"):
                grid[9] = ["B"] * 20 # Bottom row for blue stop line
            
            for row in grid:
                res.append("|" + "".join(row) + "|")
            res.append("-" * 22)
            return "\n".join(res)

    def draw_telemetry_hud(self, frame, mission_data: dict, localization: dict):
        """Draws pro-level diagnostic HUD overlay on the video frame."""
        if not CV2_AVAILABLE: return frame
        
        h, w = frame.shape[:2]
        # 1. Semi-transparent overlay box
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (220, 160), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # 2. HUD Text
        font = cv2.FONT_HERSHEY_SIMPLEX
        state = mission_data.get("state", "UNKNOWN")
        lap = mission_data.get("lap_count", 0)
        x = localization.get("x_mm", 0)
        y = localization.get("y_mm", 0)
        
        cv2.putText(frame, f"STATE: {state}", (10, 25), font, 0.6, (255, 255, 255), 1)
        cv2.putText(frame, f"LAP: {lap}/3", (10, 50), font, 0.6, (0, 255, 255), 1)
        cv2.putText(frame, f"POS: {int(x)},{int(y)}", (10, 75), font, 0.5, (200, 200, 200), 1)
        
        # 3. Draw bounding boxes for detected objects
        with self.lock:
            p = self.latest_perception
            for key, color in [("red_pillar", (0, 0, 255)), ("green_pillar", (0, 255, 0)), ("magenta_marker", (255, 0, 255))]:
                obj = p.get(key)
                if obj:
                    bx, by, bw, bh = obj["bbox"]
                    cv2.rectangle(frame, (bx, by), (bx+bw, by+bh), color, 2)
                    cv2.putText(frame, f"{int(obj['distance_est_mm'])}mm", (bx, by-5), font, 0.4, color, 1)

        return frame

    def process_frame(self, frame=None) -> dict:
        """Instant lock-free access to latest background perception data."""
        with self.lock:
            return dict(self.latest_perception)

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()


class PerceptionLayer(ThreadedCameraManager):
    """Layer 4 Interface backwards compatibility alias."""
    pass
