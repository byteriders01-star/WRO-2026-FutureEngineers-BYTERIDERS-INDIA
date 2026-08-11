import cv2, time
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
time.sleep(2.0)
ret, frame = cap.read()
print("Camera OK" if ret else "Camera FAIL", frame.shape if ret else "")
cap.release()