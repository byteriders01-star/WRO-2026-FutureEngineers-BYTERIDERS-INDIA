import board, busio, json, time
from mpu6050 import mpu6050
i2c = busio.I2C(board.SCL, board.SDA)
mpu = mpu6050(0x68)
time.sleep(1.0)
for _ in range(100): mpu.get_gyro_data()
N = 200
gx = gy = gz = 0.0
for _ in range(N):
    g = mpu.get_gyro_data()
    gx += g["x"]; gy += g["y"]; gz += g["z"]
    time.sleep(0.005)
bias = {"x": gx / N, "y": gy / N, "z": gz / N}
print("Gyro bias:", bias)
with open("imu_bias.json", "w") as f:
    json.dump(bias, f, indent=2)