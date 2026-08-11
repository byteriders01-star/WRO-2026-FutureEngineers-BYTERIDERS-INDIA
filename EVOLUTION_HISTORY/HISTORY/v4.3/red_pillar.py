import numpy as np
def detect_red_pillar(hsv, img_w, img_h):
    r1 = np.array([0, 120, 70]); r1h = np.array([10, 255, 255])
    r2 = np.array([170, 120, 70]); r2h = np.array([180, 255, 255])
    mask = cv2.bitwise_or(cv2.inRange(hsv, r1, r1h), cv2.inRange(hsv, r2, r2h))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return None
    x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
    if w * h < 300 or h < w: return None   # aspect: pillar is tall
    return {"center_x": x + w // 2, "bbox": (x, y, w, h)}