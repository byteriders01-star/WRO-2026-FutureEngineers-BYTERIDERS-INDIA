import numpy as np
import time
import math
import logging
from scipy.linalg import cholesky

class UltraPrecisionUKF:
    """
    Layer 3: Ultra-Precision 6-DoF Unscented Kalman Filter (UKF)
    Tracks 6D State Vector: [x, y, theta, v, omega, gyro_bias_z]
    Uses the Unscented Transform to propagate nonlinear state and measurement models.
    Fuses:
     - MPU6050 Gyro & Accelerometer
     - VL53L1X Front & VL53L0X Left/Right Range Measurements
     - Single-Servo 4WS Kinematic Model
    Features automatic yaw drift reset when driving parallel to straight walls.
    """
    def __init__(self, config: dict):
        self.config = config
        
        # State dimension L = 6
        self.L = 6
        
        # 6D State Vector: [x, y, theta, v, omega, gyro_bias_z]
        # x, y in mm, theta in rad, v in mm/s, omega in rad/s, bias in rad/s
        self.x = np.zeros((6, 1))
        
        # State Covariance Matrix P (6x6)
        self.P = np.diag([10.0, 10.0, 0.001, 100.0, 0.001, 0.0001])
        
        # Process Noise Covariance Matrix Q (6x6)
        self.Q = np.diag([
            5.0,      # x position noise (mm^2)
            5.0,      # y position noise (mm^2)
            0.00005,  # theta noise (rad^2)
            10.0,     # velocity noise (mm/s)^2
            0.0005,   # yaw rate noise (rad/s)^2
            0.000001  # gyro bias drift
        ])
        
        # Measurement Noise Covariances R
        self.R_vl53 = np.diag([9.0, 9.0, 16.0]) # [left_mm, right_mm, front_mm] variances
        self.R_imu  = np.diag([0.0004, 100.0])   # [gyro_z rad/s, accel_x mm/s^2] variances
        
        # UKF Parameters (alpha, beta, kappa)
        self.alpha = 1e-3
        self.beta = 2.0
        self.kappa = 0.0
        self.lamb = (self.alpha ** 2) * (self.L + self.kappa) - self.L
        
        # Compute UKF weights
        self.w_m = np.zeros(2 * self.L + 1)
        self.w_c = np.zeros(2 * self.L + 1)
        self.w_m[0] = self.lamb / (self.L + self.lamb)
        self.w_c[0] = self.lamb / (self.L + self.lamb) + (1.0 - self.alpha**2 + self.beta)
        for i in range(1, 2 * self.L + 1):
            self.w_m[i] = 1.0 / (2.0 * (self.L + self.lamb))
            self.w_c[i] = 1.0 / (2.0 * (self.L + self.lamb))
            
        self.wheelbase = config.get("kinematics_4ws", {}).get("wheelbase_mm", 160.0)
        self.track_width = config.get("kinematics_4ws", {}).get("track_width_mm", 130.0)
        
        # History for yaw-drift reset checking
        self.sensor_history = []
        self.max_history_len = 20

    def generate_sigma_points(self):
        """Generates 2L+1 sigma points based on state and covariance."""
        sigmas = np.zeros((self.L, 2 * self.L + 1))
        sigmas[:, 0] = self.x[:, 0]
        
        try:
            # P is symmetric positive-definite, compute matrix square root via Cholesky
            # (L + lamb) * P
            sqrt_P = cholesky((self.L + self.lamb) * self.P, lower=True)
            for i in range(self.L):
                sigmas[:, i + 1]          = self.x[:, 0] + sqrt_P[:, i]
                sigmas[:, i + 1 + self.L] = self.x[:, 0] - sqrt_P[:, i]
        except np.linalg.LinAlgError:
            # Fallback if P becomes semi-definite due to numerical issues
            logging.warning("[UKF] Covariance matrix is not positive-definite. Using diagonal fallback.")
            sqrt_P = np.sqrt(np.maximum(0.0, (self.L + self.lamb) * np.diag(self.P)))
            for i in range(self.L):
                offset = np.zeros(self.L)
                offset[i] = sqrt_P[i]
                sigmas[:, i + 1]          = self.x[:, 0] + offset
                sigmas[:, i + 1 + self.L] = self.x[:, 0] - offset
                
        return sigmas

    def predict(self, dt: float, commanded_speed: float, commanded_steering_rad: float):
        """UKF State and Covariance Prediction step."""
        # 1. Generate sigma points at time t-1
        sigmas = self.generate_sigma_points()
        
        # 2. Propagate each sigma point through the nonlinear transition function f(x)
        sigmas_pred = np.zeros_like(sigmas)
        rear_ratio = self.config.get("kinematics_4ws", {}).get("rear_to_front_ratio", 0.85)
        
        for i in range(2 * self.L + 1):
            theta = sigmas[2, i]
            v = sigmas[3, i]
            omega = sigmas[4, i]
            bias = sigmas[5, i]
            
            # Kinematic yaw rate contribution
            tan_delta_f = (2.0 * math.tan(commanded_steering_rad)) / (1.0 + rear_ratio)
            delta_f_rad = math.atan(tan_delta_f)
            delta_r_rad = -rear_ratio * delta_f_rad
            kinematic_omega = (v / self.wheelbase) * (math.tan(delta_f_rad) - math.tan(delta_r_rad))
            
            # Propagated values
            x_next = sigmas[0, i] + v * math.cos(theta) * dt
            y_next = sigmas[1, i] + v * math.sin(theta) * dt
            theta_next = theta + omega * dt
            # Normalize angle to [-pi, pi]
            theta_next = math.atan2(math.sin(theta_next), math.cos(theta_next))
            
            v_next = 0.90 * v + 0.10 * (commanded_speed * 10.0)
            omega_next = 0.80 * omega + 0.20 * kinematic_omega
            bias_next = bias # Bias evolves as a random walk, predicted mean is unchanged
            
            sigmas_pred[:, i] = [x_next, y_next, theta_next, v_next, omega_next, bias_next]
            
        # 3. Reconstruct mean state from predicted sigma points
        x_pred = np.zeros((self.L, 1))
        # Non-angular mean
        for i in [0, 1, 3, 4, 5]:
            x_pred[i, 0] = np.sum(self.w_m * sigmas_pred[i, :])
            
        # Angular mean (average of circular quantities using sine/cosine components)
        sum_sin = np.sum(self.w_m * np.sin(sigmas_pred[2, :]))
        sum_cos = np.sum(self.w_m * np.cos(sigmas_pred[2, :]))
        x_pred[2, 0] = math.atan2(sum_sin, sum_cos)
        
        # 4. Reconstruct covariance from predicted sigma points
        P_pred = np.zeros((self.L, self.L))
        for i in range(2 * self.L + 1):
            diff = sigmas_pred[:, i:i+1] - x_pred
            # Wrap heading angle difference
            diff[2, 0] = math.atan2(math.sin(diff[2, 0]), math.cos(diff[2, 0]))
            P_pred += self.w_c[i] * (diff @ diff.T)
            
        # Add process noise
        self.P = P_pred + self.Q * dt
        self.x = x_pred

    def update_imu(self, gyro_z_rad_s: float, accel_x_mm_s2: float):
        """UKF Update step for IMU data."""
        # Measurement z = [gyro_z, accel_x]^T
        z = np.array([[gyro_z_rad_s], [accel_x_mm_s2]])
        
        # Generate sigma points from current predicted state
        sigmas = self.generate_sigma_points()
        
        # Predict measurements for each sigma point: h(x)
        # z_1 = omega + gyro_bias
        # z_2 = accel_x (dv/dt approximation)
        Z_sigmas = np.zeros((2, 2 * self.L + 1))
        for i in range(2 * self.L + 1):
            omega = sigmas[4, i]
            bias = sigmas[5, i]
            v = sigmas[3, i]
            Z_sigmas[0, i] = omega + bias
            Z_sigmas[1, i] = v * 0.5 # linear speed approximation
            
        # Mean predicted measurement
        z_pred = np.zeros((2, 1))
        z_pred[0, 0] = np.sum(self.w_m * Z_sigmas[0, :])
        z_pred[1, 0] = np.sum(self.w_m * Z_sigmas[1, :])
        
        # Measurement covariance S and cross-covariance Pxz
        S = np.zeros((2, 2))
        Pxz = np.zeros((self.L, 2))
        
        for i in range(2 * self.L + 1):
            diff_z = Z_sigmas[:, i:i+1] - z_pred
            diff_x = sigmas[:, i:i+1] - self.x
            diff_x[2, 0] = math.atan2(math.sin(diff_x[2, 0]), math.cos(diff_x[2, 0]))
            
            S += self.w_c[i] * (diff_z @ diff_z.T)
            Pxz += self.w_c[i] * (diff_x @ diff_z.T)
            
        S += self.R_imu
        
        # Innovation and Mahalanobis Gating
        y = z - z_pred
        try:
            inv_S = np.linalg.inv(S)
            d_mahalanobis = float(y.T @ inv_S @ y)
            if d_mahalanobis > 12.0: # Outlier rejection
                return
                
            K = Pxz @ inv_S
            self.x = self.x + K @ y
            # Ensure heading remains normalized
            self.x[2, 0] = math.atan2(math.sin(self.x[2, 0]), math.cos(self.x[2, 0]))
            self.P = self.P - K @ S @ K.T
        except np.linalg.LinAlgError:
            pass

    def update_vl53_landmarks(self, left_mm: float, right_mm: float, front_mm: float):
        """UKF Update step for VL53 range data with wall geometry constraints."""
        if left_mm <= 0 and right_mm <= 0 and front_mm <= 0:
            return
            
        z = np.array([[left_mm], [right_mm], [front_mm]])
        sigmas = self.generate_sigma_points()
        
        # Predict measurements for each sigma point: h(x)
        Z_sigmas = np.zeros((3, 2 * self.L + 1))
        for i in range(2 * self.L + 1):
            x_pos = sigmas[0, i]
            y_pos = sigmas[1, i]
            
            # Simple geometry mapping: left/right are wall distances, front is forward wall
            h_left  = max(10.0, 300.0 + y_pos)
            h_right = max(10.0, 300.0 - y_pos)
            h_front = max(10.0, 1000.0 - x_pos)
            Z_sigmas[:, i] = [h_left, h_right, h_front]
            
        # Reconstruct mean measurement
        z_pred = np.zeros((3, 1))
        for j in range(3):
            z_pred[j, 0] = np.sum(self.w_m * Z_sigmas[j, :])
            
        S = np.zeros((3, 3))
        Pxz = np.zeros((self.L, 3))
        for i in range(2 * self.L + 1):
            diff_z = Z_sigmas[:, i:i+1] - z_pred
            diff_x = sigmas[:, i:i+1] - self.x
            diff_x[2, 0] = math.atan2(math.sin(diff_x[2, 0]), math.cos(diff_x[2, 0]))
            
            S += self.w_c[i] * (diff_z @ diff_z.T)
            Pxz += self.w_c[i] * (diff_x @ diff_z.T)
            
        S += self.R_vl53
        y = z - z_pred
        
        try:
            inv_S = np.linalg.inv(S)
            d_mahalanobis = float(y.T @ inv_S @ y)
            if d_mahalanobis < 16.0: # Mahalanobis gate
                K = Pxz @ inv_S
                self.x = self.x + K @ y
                self.x[2, 0] = math.atan2(math.sin(self.x[2, 0]), math.cos(self.x[2, 0]))
                self.P = self.P - K @ S @ K.T
        except np.linalg.LinAlgError:
            pass

    def check_and_reset_yaw_drift(self, left_mm: float, right_mm: float):
        """
        Dynamically detects when the robot is driving parallel to a straight wall.
        If ToF readings sum is stable and variance is low, resets yaw bias and drift.
        """
        if left_mm <= 0 or right_mm <= 0:
            return
            
        # Add to history
        self.sensor_history.append((left_mm, right_mm))
        if len(self.sensor_history) > self.max_history_len:
            self.sensor_history.pop(0)
            
        if len(self.sensor_history) < self.max_history_len:
            return
            
        # Calculate sum and variances
        sums = [l + r for l, r in self.sensor_history]
        mean_sum = sum(sums) / len(sums)
        variance_sum = sum((s - mean_sum) ** 2 for s in sums) / len(sums)
        
        # Expected lane width: Left + Right + Vehicle Width (160mm)
        # Standard lane is 600mm. Let's make it robust.
        expected_lane_sum = mean_sum  # Use current mean sum as reference
        
        left_vars = np.var([l for l, r in self.sensor_history])
        right_vars = np.var([r for l, r in self.sensor_history])
        
        # If variances are very small, we are driving parallel to straight walls
        if left_vars < 4.0 and right_vars < 4.0 and variance_sum < 3.0:
            # Calculate nearest orthogonal angle (parallel to walls: 0, 90, 180, 270 degrees)
            curr_heading_deg = math.degrees(self.x[2, 0])
            nearest_orth_deg = round(curr_heading_deg / 90.0) * 90.0
            nearest_orth_rad = math.radians(nearest_orth_deg)
            nearest_orth_rad = math.atan2(math.sin(nearest_orth_rad), math.cos(nearest_orth_rad))
            
            heading_diff = math.atan2(math.sin(nearest_orth_rad - self.x[2, 0]), math.cos(nearest_orth_rad - self.x[2, 0]))
            
            # If drift is minor (less than 15 deg), reset it
            if abs(heading_diff) < math.radians(15.0):
                # Reset theta to exact orthogonal direction
                logging.info(f"[UKF] Yaw Drift Reset Triggered! Resetting heading from {curr_heading_deg:.2f}° to {nearest_orth_deg:.2f}° (Diff: {math.degrees(heading_diff):.2f}°)")
                self.x[2, 0] = nearest_orth_rad
                # Reduce covariance for theta and bias
                self.P[2, 2] = 0.00001
                self.P[5, 5] = 0.000001
                # Adjust gyro bias based on difference to stabilize future prediction
                self.x[5, 0] = 0.9 * self.x[5, 0] + 0.1 * (heading_diff / 0.01) # smooth adjustment

    def get_state(self) -> dict:
        return {
            "x_mm": float(round(self.x[0, 0], 2)),
            "y_mm": float(round(self.x[1, 0], 2)),
            "heading_rad": float(round(self.x[2, 0], 4)),
            "heading_deg": float(round(math.degrees(self.x[2, 0]), 2)),
            "velocity_mm_s": float(round(self.x[3, 0], 2)),
            "yaw_rate_rad_s": float(round(self.x[4, 0], 4)),
            "gyro_bias": float(round(self.x[5, 0], 6)),
            "covariance_trace": float(round(np.trace(self.P), 4))
        }

class SensorFusionLayer:
    """
    Layer 3 Interface wrapping UltraPrecisionUKF
    """
    def __init__(self, config: dict):
        self.ukf = UltraPrecisionUKF(config)
        self.last_time = time.time()

    def update(self, synced_frame: dict, commanded_speed: float, commanded_steering_rad: float) -> dict:
        now = time.time()
        dt = now - self.last_time
        if dt <= 0 or dt > 0.5:
            dt = 0.01
        self.last_time = now

        sensors = synced_frame.get("sensors", {})
        gyro = sensors.get("gyro", {})
        accel = sensors.get("accel", {})

        gyro_z_rad_s = math.radians(gyro.get('z', 0.0))
        accel_x_mm_s2 = accel.get('x', 0.0) * 1000.0

        left_mm  = sensors.get("left_mm", -1)
        right_mm = sensors.get("right_mm", -1)
        front_mm = sensors.get("front_mm", -1)

        # 1. UKF Prediction step
        self.ukf.predict(dt, commanded_speed, commanded_steering_rad)

        # 2. UKF IMU Update step
        self.ukf.update_imu(gyro_z_rad_s, accel_x_mm_s2)

        # 3. UKF Range Sensor Update step
        self.ukf.update_vl53_landmarks(left_mm, right_mm, front_mm)

        # 4. Check & Reset Yaw Drift when driving parallel to straight wall
        self.ukf.check_and_reset_yaw_drift(left_mm, right_mm)

        return self.ukf.get_state()
