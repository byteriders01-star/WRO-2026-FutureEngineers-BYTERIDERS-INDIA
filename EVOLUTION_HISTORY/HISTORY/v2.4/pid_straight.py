import serial, time
import board, busio
from mpu6050 import mpu6050
ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
i2c = busio.I2C(board.SCL, board.SDA)
mpu = mpu6050(0x68)
Kp, Ki, Kd = 1.2, 0.05, 0.1
integral = 0.0; last_err = 0.0; last_t = time.time()
def cmd(deg, spd):
    s = int(deg * 100); v = int(spd * 10)
    pkt = bytes([0xAA, 0x55, 0, 0x01, s >> 8 & 0xFF, s & 0xFF, v >> 8 & 0xFF, v & 0xFF, 0, 0x0D])
    ser.write(pkt)
start_yaw = mpu.get_gyro_data()['z']
yaw = 0.0
while True:
    dt = time.time() - last_t; last_t = time.time()
    yaw += mpu.get_gyro_data()['z'] * dt
    err = (start_yaw - yaw) * 57.3
    integral = max(-20, min(20, integral + err * dt))
    deriv = (err - last_err) / dt; last_err = err
    out = Kp * err + Ki * integral + Kd * deriv
    cmd(max(-35, min(35, out)), 40)
    time.sleep(0.01)