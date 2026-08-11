import time, board, busio
from digitalio import DigitalInOut, Direction
import adafruit_vl53l1x, adafruit_vl53l0x
i2c = busio.I2C(board.SCL, board.SDA)
front = DigitalInOut(board.D22); left = DigitalInOut(board.D17); right = DigitalInOut(board.D27)
for p in (front, left, right): p.direction = Direction.OUTPUT; p.value = False
def read_front():
    front.value = True; time.sleep(0.02)
    s = adafruit_vl53l1x.VL53L1X(i2c); s.timing_budget = 33
    s.start_ranging(); time.sleep(0.035)
    cm = s.distance if s.data_ready else None
    s.stop_ranging(); front.value = False
    return cm * 10.0 if cm and cm > 0 else -1.0
def read_side(pin):
    pin.value = True; time.sleep(0.02)
    mm = adafruit_vl53l0x.VL53L0X(i2c).range
    pin.value = False
    return mm if mm and mm > 0 else -1.0
while True:
    print("F", read_front(), "L", read_side(left), "R", read_side(right))
    time.sleep(0.1)