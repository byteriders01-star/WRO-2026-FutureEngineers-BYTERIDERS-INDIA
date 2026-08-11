import board, busio, time
from digitalio import DigitalInOut, Direction
import adafruit_vl53l1x, adafruit_vl53l0x
i2c = busio.I2C(board.SCL, board.SDA)
front = DigitalInOut(board.D22); left = DigitalInOut(board.D17); right = DigitalInOut(board.D27)
for p in (front, left, right): p.direction = Direction.OUTPUT; p.value = False
time.sleep(0.1)
def read_front():
    front.value = True; time.sleep(0.02)
    s = adafruit_vl53l1x.VL53L1X(i2c); s.timing_budget = 33
    s.start_ranging(); time.sleep(0.035)
    d = s.distance if s.data_ready else -1
    s.stop_ranging(); front.value = False
    return d
def read_side(pin):
    pin.value = True; time.sleep(0.02)
    d = adafruit_vl53l0x.VL53L0X(i2c).range
    pin.value = False
    return d
while True:
    print("F", read_front(), "L", read_side(left), "R", read_side(right))
    time.sleep(0.1)