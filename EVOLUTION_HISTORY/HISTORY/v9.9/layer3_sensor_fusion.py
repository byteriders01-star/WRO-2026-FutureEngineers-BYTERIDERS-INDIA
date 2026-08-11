import numpy as np
import time
import math
import logging

class UltraPrecisionUKF:
    """
    Layer 3: Ultra-Precision Unscented Kalman Filter (UKF)
    Tracks 6D State Vector: [x, y, theta, v, omega, gyro_bias_z]
    Uses Van der Merwe Sigma Point Transformation for superior non-linear fusion.
    """
    def __init__(self, config: dict):
        self.config = config
        self.n = 6  # State dimension
        self.k = 0.0 # Scaling parameter
        self.alpha = 0.001
        self.beta = 2.0
        self.lamb = self.alpha**2 * (self.n + self.k) - self.n

        # State Vector [x, y, theta, v, omega, bias]
        self.x = np.zeros((self.n, 1))
        self.P = np.diag([10.0, 10.0, 0.01, 100.0, 0.01, 0.001])
        self.Q = np.diag([2.0, 2.0, 0.0001, 50.0, 0.002, 0.00001])

        # Measurement Noise
        self.R_imu = np.diag([0.0004, 80.0]) # [gyro, accel]
        self.R_vl53 = np.diag([12.0, 12.0, 20.0]) # [left, right, front]

        # Weights for mean and covariance
        self.Wm = np.full(2 * self.n + 1, 1.0 / (2 * (self.n + self.lamb)))
        self.Wc = np.full(2 * self.n + 1, 1.0 / (2 * (self.n + self.lamb)))
        self.Wm[0] = self.lamb / (self.n + self.lamb)
        self.Wc[0] = self.lamb / (self.n + self.lamb) + (1 - self.alpha**2 + self.beta)

        self.wheelbase = config.get("kinematics_4ws", {}).get("wheelbase_mm", 230.0)

    def _generate_sigma_points(self, x, P):
        sigma = np.zeros((self.n, 2 * self.n + 1))
        sigma[:, 0] = x.flatten()
        U = np.linalg.cholesky((self.n + self.lamb) * P)
        for i in range(self.n):
            sigma[:, i + 1] = x.flatten() + U[:, i]
            sigma[:, i + self.n + 1] = x.flatten() - U[:, i]
        return sigma

    def predict(self, dt, commanded_speed, commanded_steering_rad):
        # Generate sigma points
        sigmas = self._generate_sigma_points(self.x, self.P)
        sigmas_out = np.zeros_like(sigmas)

        # Propagate each sigma point through the motion model
        for i in range(2 * self.n + 1):
            s = sigmas[:, i]
            theta, v, omega = s[2], s[3], s[4]
            
            # Kinematic 4WS prediction
            rear_ratio = self.config.get("kinematics_4ws", {}).get("rear_to_front_ratio", 0.85)
            tan_delta_f = (2.0 * math.tan(commanded_steering_rad)) / (1.0 + rear_ratio)
            delta_f = math.atan(tan_delta_f)
            delta_r = -rear_ratio * delta_f
            kin_omega = (v / self.wheelbase) * (math.tan(delta_f) - math.tan(delta_r))

            # State transition f(s)
            s_new = np.copy(s)
            s_new[0] += v * math.cos(theta) * dt
            s_new[1] += v * math.sin(theta) * dt
            s_new[2] += omega * dt
            s_new[2] = math.atan2(math.sin(s_new[2]), math.cos(s_new[2]))
            s_new[3] = 0.85 * v + 0.15 * (commanded_speed * 10.0) # speed integration
            s_new[4] = 0.70 * omega + 0.30 * kin_omega
            sigmas_out[:, i] = s_new

        # Recombine sigmas into predicted mean and covariance
        self.x = np.sum(self.Wm * sigmas_out, axis=1).reshape(-1, 1)
        self.P = np.zeros((self.n, self.n))
        for i in range(2 * self.n + 1):
            diff = (sigmas_out[:, i].reshape(-1, 1) - self.x)
            self.P += self.Wc[i] * (diff @ diff.T)
        self.P += self.Q * dt

    def update_imu(self, gyro_z, accel_x):
        # Observation model for IMU: [omega + bias, a_x]
        # accel_x is treated as dv/dt integration check
        sigmas = self._generate_sigma_points(self.x, self.P)
        z_sigmas = np.zeros((2, 2 * self.n + 1))
        
        for i in range(2 * self.n + 1):
            s = sigmas[:, i]
            z_sigmas[0, i] = s[4] + s[5] # omega + bias
            z_sigmas[1, i] = s[3] * 0.1  # pseudo-accel check

        # Unscented Transform of measurement
        zp = np.sum(self.Wm * z_sigmas, axis=1).reshape(-1, 1)
        Sz = np.zeros((2, 2))
        Pxz = np.zeros((self.n, 2))
        for i in range(2 * self.n + 1):
            dz = z_sigmas[:, i].reshape(-1, 1) - zp
            dx = sigmas[:, i].reshape(-1, 1) - self.x
            Sz += self.Wc[i] * (dz @ dz.T)
            Pxz += self.Wc[i] * (dx @ dz.T)
        Sz += self.R_imu

        # Kalman Gain
        z = np.array([[gyro_z], [accel_x]])
        try:
            K = Pxz @ np.linalg.inv(Sz)
            self.x = self.x + K @ (z - zp)
            self.P = self.P - K @ Sz @ K.T
        except np.linalg.LinAlgError:
            pass

    def update_vl53(self, left_mm, right_mm, front_mm):
        # Identify valid sensors
        valid_indices = []
        z_vals = []
        if left_mm > 0:
            valid_indices.append(0)
            z_vals.append(left_mm)
        if right_mm > 0:
            valid_indices.append(1)
            z_vals.append(right_mm)
        if front_mm > 0:
            valid_indices.append(2)
            z_vals.append(front_mm)

        if not valid_indices:
            return

        m = len(valid_indices)
        sigmas = self._generate_sigma_points(self.x, self.P)
        z_sigmas = np.zeros((m, 2 * self.n + 1))
        
        for i in range(2 * self.n + 1):
            s = sigmas[:, i]
            # Predicted wall distances
            idx = 0
            if 0 in valid_indices:
                z_sigmas[idx, i] = 300.0 + s[1] # predicted left
                idx += 1
            if 1 in valid_indices:
                z_sigmas[idx, i] = 300.0 - s[1] # predicted right
                idx += 1
            if 2 in valid_indices:
                z_sigmas[idx, i] = 1000.0 - s[0] # predicted front
                idx += 1

        zp = np.sum(self.Wm * z_sigmas, axis=1).reshape(-1, 1)
        Sz = np.zeros((m, m))
        Pxz = np.zeros((self.n, m))
        for i in range(2 * self.n + 1):
            dz = z_sigmas[:, i].reshape(-1, 1) - zp
            dx = sigmas[:, i].reshape(-1, 1) - self.x
            Sz += self.Wc[i] * (dz @ dz.T)
            Pxz += self.Wc[i] * (dx @ dz.T)
        
        # Sub-slice R matrix based on valid sensors
        R_sub = np.diag([self.R_vl53[i, i] for i in valid_indices])
        Sz += R_sub

        z = np.array(z_vals).reshape(-1, 1)
        try:
            K = Pxz @ np.linalg.inv(Sz)
            self.x = self.x + K @ (z - zp)
            self.P = self.P - K @ Sz @ K.T
        except np.linalg.LinAlgError:
            pass

    def get_state(self) -> dict:
        return {
            "x_mm": float(self.x[0, 0]),
            "y_mm": float(self.x[1, 0]),
            "heading_rad": float(self.x[2, 0]),
            "heading_deg": float(math.degrees(self.x[2, 0])),
            "velocity_mm_s": float(self.x[3, 0]),
            "yaw_rate_rad_s": float(self.x[4, 0]),
            "gyro_bias": float(self.x[5, 0])
        }

class SensorFusionLayer:
    def __init__(self, config: dict):
        self.ukf = UltraPrecisionUKF(config)
        self.last_time = time.time()

    def update(self, synced_frame: dict, commanded_speed: float, commanded_steering_rad: float) -> dict:
        now = time.time()
        dt = now - self.last_time
        if dt <= 0 or dt > 0.5: dt = 0.01
        self.last_time = now

        sensors = synced_frame.get("sensors", {})
        gyro_z = math.radians(sensors.get("gyro", {}).get('z', 0.0))
        accel = sensors.get("accel", {'x': 0.0, 'y': 0.0, 'z': 9.81})
        accel_x_raw = accel.get('x', 0.0) * 1000.0
        
        # 1. IMU Tilt Compensation (Calculated here to keep Layer 1 "Perfect")
        # ax, ay, az are in m/s^2. We calculate vehicle orientation relative to gravity.
        ax, ay, az = accel.get('x', 0.0), accel.get('y', 0.0), accel.get('z', 9.81)
        roll_rad  = math.atan2(ay, az) if az != 0 else 0.0
        pitch_rad = math.atan2(-ax, math.sqrt(ay**2 + az**2))

        # Correct raw distances using trig projection
        raw_left  = sensors.get("left_mm", -1.0)
        raw_right = sensors.get("right_mm", -1.0)
        raw_front = sensors.get("front_mm", -1.0)

        corr_left  = raw_left * math.cos(roll_rad) if raw_left > 0 else -1.0
        corr_right = raw_right * math.cos(roll_rad) if raw_right > 0 else -1.0
        corr_front = raw_front * math.cos(pitch_rad) if raw_front > 0 else -1.0
        
        # 2. Perform UKF Cycle
        self.ukf.predict(dt, commanded_speed, commanded_steering_rad)
        self.ukf.update_imu(gyro_z, accel_x_raw)
        self.ukf.update_vl53(corr_left, corr_right, corr_front)

        return self.ukf.get_state()
