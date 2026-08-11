import time, board, busio, csv
from mpu6050 import mpu6050
i2c = busio.I2C(board.SCL, board.SDA)
mpu = mpu6050(0x68)
time.sleep(1.0)
for _ in range(100):   # discard warmup garbage
    mpu.get_accel_data(); mpu.get_gyro_data()
with open("imu.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["t", "ax", "ay", "az", "gx", "gy", "gz"])
    t0 = time.time()
    while time.time() - t0 < 10:
        a = mpu.get_accel_data(); g = mpu.get_gyro_data()
        w.writerow([round(time.time() - t0, 3), a["x"], a["y"], a["z"], g["x"], g["y"], g["z"]])
        time.sleep(0.01)