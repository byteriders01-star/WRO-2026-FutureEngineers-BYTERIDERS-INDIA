# Noise matrices measured from 10-minute log (v5.5)
Q = np.diag([2.0, 2.0, 0.0001, 50.0, 0.002, 0.00001])
R_imu = np.diag([0.0004, 80.0])
R_vl53 = np.diag([12.0, 12.0, 20.0])