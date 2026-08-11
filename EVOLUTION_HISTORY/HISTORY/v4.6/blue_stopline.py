def detect_blue_line(hsv, img_h):
    low = np.array([95, 120, 80]); high = np.array([130, 255, 255])
    roi = hsv[int(img_h * 0.7):, :]
    return cv2.countNonZero(cv2.inRange(roi, low, high)) > 800