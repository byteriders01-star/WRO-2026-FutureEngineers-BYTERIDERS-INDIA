import time, board, busio, math
from mpu6050 import mpu6050
i2c = busio.I2C(board.SCL, board.SDA)
mpu = mpu6050(0x68)
ALPHA = 0.92
roll = pitch = 0.0
last = time.time()
for _ in range(100): mpu.get_accel_data(); mpu.get_gyro_data()
while True:
    dt = time.time() - last; last = time.time()
    a = mpu.get_accel_data(); g = mpu.get_gyro_data()
    roll_a = math.atan2(a["y"], a["z"])
    pitch_a = math.atan2(-a["x"], math.sqrt(a["y"]**2 + a["z"]**2))
    roll = ALPHA * (roll + math.radians(g["x"]) * dt) + (1 - ALPHA) * roll_a
    pitch = ALPHA * (pitch + math.radians(g["y"]) * dt) + (1 - ALPHA) * pitch_a
    print(f"roll={math.degrees(roll):.1f} pitch={math.degrees(pitch):.1f}")
    time.sleep(0.01)