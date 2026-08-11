import time, board, busio, math
from mpu6050 import mpu6050
i2c = busio.I2C(board.SCL, board.SDA)
mpu = mpu6050(0x68)
for _ in range(100): mpu.get_gyro_data()
yaw = 0.0; last = time.time()
while True:
    dt = time.time() - last; last = time.time()
    yaw += math.radians(mpu.get_gyro_data()["z"]) * dt
    yaw = math.atan2(math.sin(yaw), math.cos(yaw))
    print(f"heading={math.degrees(yaw):.1f} deg")
    time.sleep(0.01)