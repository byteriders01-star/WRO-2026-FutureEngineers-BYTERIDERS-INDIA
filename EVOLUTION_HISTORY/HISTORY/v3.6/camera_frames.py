import cv2, threading, time
class Cam:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.frame = None
        threading.Thread(target=self._loop, daemon=True).start()
    def _loop(self):
        time.sleep(2.0)  # warmup
        while True:
            ret, f = self.cap.read()
            if ret: self.frame = f
            time.sleep(0.01)
cam = Cam()
time.sleep(3.0)
print("frame ready:", cam.frame is not None)