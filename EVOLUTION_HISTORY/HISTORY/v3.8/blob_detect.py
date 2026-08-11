import cv2, numpy as np
def find_largest(mask, img_w, img_h):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return None
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    if area < 300: return None
    x, y, w, h = cv2.boundingRect(largest)
    cx = x + w // 2
    return {"normalized_x": (cx - img_w / 2) / (img_w / 2),
            "area": area, "bbox": (x, y, w, h)}