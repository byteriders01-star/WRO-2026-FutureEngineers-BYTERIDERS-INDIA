def detect_magenta(hsv):
    low = np.array([135, 80, 50]); high = np.array([165, 255, 255])
    mask = cv2.inRange(hsv, low, high)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return None
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    if area < 1500: return None
    x, y, w, h = cv2.boundingRect(largest)
    return {"area": area, "center_x": x + w // 2}