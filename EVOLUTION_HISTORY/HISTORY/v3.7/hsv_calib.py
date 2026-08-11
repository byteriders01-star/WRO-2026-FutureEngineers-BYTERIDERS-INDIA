import cv2, numpy as np
cap = cv2.VideoCapture(0)
def track(name):
    cv2.createTrackbar(f"{name} H lo", "cal", 0, 180, lambda x: None)
cv2.namedWindow("cal")
while True:
    ret, f = cap.read()
    if not ret: continue
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    cv2.imshow("cal", hsv)
    if cv2.waitKey(1) & 0xFF == ord("q"): break
cap.release()