import time
import json
import os
from mpu6050 import mpu6050

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "robot_config.json")

def calibrate_mpu(num_samples=200):
    print("==================================================")
    print("        WRO 2026 MPU6050 IMU CALIBRATOR           ")
    print("==================================================")
    print("Place robot on a flat, motionless surface...")
    time.sleep(2)

    try:
        mpu = mpu6050(0x68)
    except Exception as e:
        print(f"[ERROR] Failed to connect to MPU6050 at 0x68: {e}")
        return

    gyro_x_sum, gyro_y_sum, gyro_z_sum = 0.0, 0.0, 0.0
    accel_x_sum, accel_y_sum, accel_z_sum = 0.0, 0.0, 0.0

    print(f"Collecting {num_samples} samples...")
    for i in range(num_samples):
        gyro = mpu.get_gyro_data()
        accel = mpu.get_accel_data()

        gyro_x_sum += gyro['x']
        gyro_y_sum += gyro['y']
        gyro_z_sum += gyro['z']

        accel_x_sum += accel['x']
        accel_y_sum += accel['y']
        accel_z_sum += accel['z']

        time.sleep(0.01)

    gyro_offsets = {
        'x': gyro_x_sum / num_samples,
        'y': gyro_y_sum / num_samples,
        'z': gyro_z_sum / num_samples
    }
    accel_offsets = {
        'x': accel_x_sum / num_samples,
        'y': accel_y_sum / num_samples,
        'z': (accel_z_sum / num_samples) - 9.81  # gravity subtracted
    }

    print("--------------------------------------------------")
    print("Calculated Gyro Biases (deg/s):", gyro_offsets)
    print("Calculated Accel Biases (m/s^2):", accel_offsets)
    print("--------------------------------------------------")

    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
        config["sensors"]["mpu6050_offsets"] = {
            "gyro": gyro_offsets,
            "accel": accel_offsets
        }
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        print("[SUCCESS] Saved IMU calibration biases to robot_config.json")
    except Exception as e:
        print(f"[ERROR] Failed to write calibration to config: {e}")

if __name__ == "__main__":
    calibrate_mpu()
