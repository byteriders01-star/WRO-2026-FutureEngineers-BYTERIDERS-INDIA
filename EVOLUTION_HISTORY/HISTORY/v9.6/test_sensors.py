"""
======================================================================================
         VL53L1X TIMING BUDGET FIX & 50mm OFFSET CALIBRATION
======================================================================================
"""
import time
import sys

try:
    import board
    import busio
    from digitalio import DigitalInOut, Direction
    import adafruit_vl53l1x
    import adafruit_vl53l0x
    from mpu6050 import mpu6050
except ImportError as e:
    print(f"[ERROR] Missing hardware libraries: {e}")
    sys.exit(1)


# Setup I2C Bus
i2c = busio.I2C(board.SCL, board.SDA)

# Setup XSHUT Pins
front_pin = DigitalInOut(board.D22)
left_pin  = DigitalInOut(board.D17)
right_pin = DigitalInOut(board.D27)

for p in (front_pin, left_pin, right_pin):
    p.direction = Direction.OUTPUT
    p.value = False

time.sleep(0.125)

# 50mm (5cm) Calibration Offset Subtraction for Left/Right
OFFSET_LR_MM = 50.0

# Setup MPU6050
try:
    mpu = mpu6050(0x68)
except Exception:
    mpu = None


def read_front_sensor():
    """Turn ON Front (GPIO 22), read VL53L1X distance in mm."""
    dist = -1.0
    front_pin.value = True
    left_pin.value = False
    right_pin.value = False
    time.sleep(0.05)

    try:
        sensor = adafruit_vl53l1x.VL53L1X(i2c)
        try:
            sensor.timing_budget = 50 # 50ms budget for fast accurate ranging
        except Exception:
            pass

        sensor.start_ranging()
        time.sleep(0.06)

        # Poll for ready sample
        for _ in range(5):
            if sensor.data_ready:
                raw_cm = sensor.distance
                sensor.clear_interrupt()
                if raw_cm is not None and raw_cm > 0:
                    dist = float(raw_cm * 10.0) # adafruit_vl53l1x returns cm -> convert to mm
                break
            time.sleep(0.01)

        sensor.stop_ranging()
    except Exception:
        dist = -1.0

    front_pin.value = False
    return dist


def read_left_sensor():
    """Turn ON Left (GPIO 17), read VL53L0X distance in mm with -50mm (-5cm) calibration offset."""
    dist = -1.0
    front_pin.value = False
    left_pin.value = True
    right_pin.value = False
    time.sleep(0.04)

    try:
        sensor = adafruit_vl53l0x.VL53L0X(i2c)
        raw_mm = sensor.range
        if raw_mm is not None and raw_mm > 0:
            dist = max(0.0, float(raw_mm) - OFFSET_LR_MM) # Subtract 5cm (50mm) error offset
    except Exception:
        dist = -1.0

    left_pin.value = False
    return dist


def read_right_sensor():
    """Turn ON Right (GPIO 27), read VL53L0X distance in mm with -50mm (-5cm) calibration offset."""
    dist = -1.0
    front_pin.value = False
    left_pin.value = False
    right_pin.value = True
    time.sleep(0.04)

    try:
        sensor = adafruit_vl53l0x.VL53L0X(i2c)
        raw_mm = sensor.range
        if raw_mm is not None and raw_mm > 0:
            dist = max(0.0, float(raw_mm) - OFFSET_LR_MM) # Subtract 5cm (50mm) error offset
    except Exception:
        dist = -1.0

    right_pin.value = False
    return dist


print("==================================================")
print("  VL53L1X ACCURACY FIX & -5cm CALIBRATED STREAM   ")
print("==================================================")

try:
    while True:
        f = read_front_sensor()
        l = read_left_sensor()
        r = read_right_sensor()

        accel = mpu.get_accel_data() if mpu else {'x': 0, 'y': 0, 'z': 9.81}
        gyro  = mpu.get_gyro_data()  if mpu else {'x': 0, 'y': 0, 'z': 0}

        print("----------------")
        print(f"Front : {f:6.1f} mm")
        print(f"Left  : {l:6.1f} mm (-5cm offset applied)")
        print(f"Right : {r:6.1f} mm (-5cm offset applied)")
        print("ACC   :", accel)
        print("GYRO  :", gyro)

        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n[INFO] Sensor test stopped.")
