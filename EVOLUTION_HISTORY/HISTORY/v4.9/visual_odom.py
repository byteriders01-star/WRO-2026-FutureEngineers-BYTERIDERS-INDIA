import cv2, numpy as np
fast = cv2.FastFeatureDetector_create(threshold=20)
def track_motion(prev, curr):
    kp1 = fast.detect(prev, None)
    if not kp1: return 0.0
    pts1 = np.float32([p.pt for p in kp1]).reshape(-1, 1, 2)
    pts2, st, _ = cv2.calcOpticalFlowPyrLK(prev, curr, pts1, None)
    good = pts1[st == 1], pts2[st == 1]
    if len(good[0]) < 5: return 0.0
    return float(np.mean(good[1] - good[0]))