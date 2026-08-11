# Autonomous 4WS Software Architecture - WRO Future Engineers 2026

Professional 10-Layer Software Architecture designed for Raspberry Pi 4B + ESP32-S3 + Single Servo Mechanical 4-Wheel Steering (4WS) vehicle competing in **WRO Future Engineers 2026**.

> **Documentation for judges:** [Engineering Documentation (design narrative)](ENGINEERING_DOCUMENTATION.md) · [Parameter Justification (every constant, with proof)](ENGINEERING_PARAMETER_JUSTIFICATION.md)

---

## 🏛️ System Architecture

```text
Raspberry Pi 4B (High-Level Perception, Navigation & Control)
  ├── Pi Camera (OpenCV Pillar & Marker Detection)
  ├── VL53L1X Front Distance Sensor (I2C: 0x30, XSHUT GPIO 22)
  ├── VL53L0X Left Distance Sensor (I2C: 0x31, XSHUT GPIO 17)
  ├── VL53L0X Right Distance Sensor (I2C: 0x32, XSHUT GPIO 27)
  ├── MPU6050 IMU Accelerometer + Gyroscope (I2C: 0x68)
  └── QMC5883L Magnetometer (Disabled per specification, modular placeholder)
        │
        │ USB Serial Packet Protocol (10-byte binary + CRC8 @ 100 Hz)
        ▼
ESP32-S3 Real-Time Motor Controller
  ├── MG995 4WS Steering Servo PWM (GPIO 18)
  └── TB6612FNG / L298N Motor Driver + Johnson DC Motor (GPIO 19, 20, 21, 22)
```

---

## 📂 Project File Structure

- [`main.py`](file:///C:/Users/VivoBook/.gemini/antigravity/scratch/wro_4ws_robot/main.py): Real-time entrypoint executing Layer 0 to Layer 10 at 100 Hz.
- [`test_sensors.py`](file:///C:/Users/VivoBook/.gemini/antigravity/scratch/wro_4ws_robot/test_sensors.py): Standalone sensor hardware test runner using exact provided VL53 & MPU setup code.
- [`config/robot_config.json`](file:///C:/Users/VivoBook/.gemini/antigravity/scratch/wro_4ws_robot/config/robot_config.json): Centralized configuration (PID constants, HSV thresholds, Surprise Rule flags, geometry).
- [`utils/serial_protocol.py`](file:///C:/Users/VivoBook/.gemini/antigravity/scratch/wro_4ws_robot/utils/serial_protocol.py): 10-byte CRC8 binary serial packet encoder/decoder.
- [`utils/calibrate_hsv.py`](file:///C:/Users/VivoBook/.gemini/antigravity/scratch/wro_4ws_robot/utils/calibrate_hsv.py): GUI HSV color threshold tuner for venue lighting.
- [`utils/calibrate_imu.py`](file:///C:/Users/VivoBook/.gemini/antigravity/scratch/wro_4ws_robot/utils/calibrate_imu.py): MPU6050 zero-bias calibration script.
- [`firmware/esp32_controller/esp32_controller.ino`](file:///C:/Users/VivoBook/.gemini/antigravity/scratch/wro_4ws_robot/firmware/esp32_controller/esp32_controller.ino): ESP32-S3 C++ firmware with 200ms Watchdog, CRC8, and PWM drivers.

### 📐 Software Layers (Layers 0 – 10)
1. **Layer 0 (`layer0_system_manager.py`)**: Thread manager, logger, health monitoring, FPS/latency stats.
2. **Layer 1 (`layer1_sensors.py`)**: Exact hardware init for VL53L1X, VL53L0X Left/Right, MPU6050 with median & EMA filtering.
3. **Layer 2 (`layer2_time_sync.py`)**: Time synchronization and circular buffer management.
4. **Layer 3 (`layer3_sensor_fusion.py`)**: Extended Kalman Filter & Gyro Complementary Filter for pose `[x, y, θ, v, ω]`.
5. **Layer 4 (`layer4_perception.py`)**: OpenCV color segmentation for Red/Green pillars, Blue stop line, free space.
6. **Layer 5 (`layer5_localization.py`)**: Track cross-track error and wall alignment.
7. **Layer 6 (`layer6_mission_manager.py`)**: Mission FSM + WRO 2026 Rule 6 Surprise Rules Engine.
8. **Layer 7 (`layer7_path_planner.py`)**: Dynamic corridor path generation and pillar avoidance offset blending.
9. **Layer 8 (`layer8_trajectory_opt.py`)**: Trajectory curvature optimization & dynamic velocity profiling.
10. **Layer 9 (`layer9_kinematics_4ws.py`)**: Single Servo Mechanical 4WS Ackermann model ($\delta_r = -\kappa \cdot \delta_f$).
11. **Layer 10 (`layer10_controller.py`)**: Stanley Steering Control Law & USB Serial packet transmission.

---

## ⚡ WRO 2026 Rule 6 (Surprise Rules) Readiness

To handle competition-day surprise rules announced at 08:30 AM:

1. **Pillar Colour Swap**:
   Change `"SIGN_LOGIC": "REVERSED"` in [`robot_config.json`](file:///C:/Users/VivoBook/.gemini/antigravity/scratch/wro_4ws_robot/config/robot_config.json).
2. **Fixed Driving Direction**:
   Set `"DRIVING_DIRECTION": "CW"` or `"CCW"`.
3. **Narrow Track Mode (600 mm lanes)**:
   Set `"NARROW_TRACK_MODE": true`. Increases wall centering gain dynamically.
4. **Stop-and-Go Marker (Blue line)**:
   Set `"STOP_AND_GO_ENABLED": true` to auto-pause 3.0 seconds on blue floor markers.
5. **Emergency Obstacle intruding on track**:
   Auto-triggers `EMERGENCY_BRAKE` when front sensor detects obstacles $< 180 \text{ mm}$.

---

## 🚀 Quickstart Guide

### 1. Hardware Verification
Run standalone sensor test on Raspberry Pi 4B:
```bash
python test_sensors.py
```

### 2. Fast Venue Lighting Calibration
Tune HSV thresholds during the 120-minute practice session:
```bash
python utils/calibrate_hsv.py
```

### 3. Flash ESP32-S3 Firmware
Open [`firmware/esp32_controller/esp32_controller.ino`](file:///C:/Users/VivoBook/.gemini/antigravity/scratch/wro_4ws_robot/firmware/esp32_controller/esp32_controller.ino) in Arduino IDE, select board `ESP32S3 Dev Module`, and flash via USB.

### 4. Execute Autonomous System
```bash
python main.py
```

---

## 📐 Engineering Summary (Why, not What)

- **Kinematics:** single-servo 4WS with rear counter-steering (κ = 0.85, δ_r = −κ·δ_f) cuts the turning radius from 274 mm (2WS) to **141 mm (−48.5%)** — derived and measured in [`ENGINEERING_PARAMETER_JUSTIFICATION.md`](ENGINEERING_PARAMETER_JUSTIFICATION.md) §1.
- **Real-time design:** VL53L1X ranging cycle (68 ms) is 6.8× slower than the 10 ms control frame, so sensors and camera run on dedicated threads with atomic health flags — the main loop never blocks (Layer 1/4).
- **Control:** adaptive-gain Stanley law (k(v) = 0.75/(1+0.015v), k_s = 0.1) — finite at standstill, which is why it was chosen over Pure Pursuit.
- **Safety in depth:** soft slowdown at 450 mm (full braking-chain distance = 296 mm + margin), FSM emergency brake at 180 mm, Pi-side 5-fault serial threshold, ESP32-side 200 ms watchdog.
- **Mission:** deterministic 7-state FSM (laps via yaw integral + start-zone proximity, stop-and-go, parking) with a config-driven WRO Rule 6 Surprise Rules adapter — rule changes deployable in under 2 minutes.
- **Fusion:** 6-DOF Unscented Kalman Filter with online gyro-bias estimation (Van der Merwe parametrization, R/Q calibrated by Allan variance and repeatability tests).

## 🔬 Validation Status

| Area | Result |
|---|---|
| Compile gate | All 16 Python files pass `python -m py_compile` |
| Integration | Full 10-layer pipeline: 200 loop iterations, 0 exceptions |
| Serial protocol | 10,000 random packets round-trip; CRC8 poly 0x07 rejects all injected bit flips |
| Boot probe | Fixed keyword bug (FA-1); probe now exercises real packet path |
| Serial fault path | Verified raising on link loss → LED4 OFF + emergency stop (FA-2) |
| Test matrix | T-1…T-10 pass; T-11 (lap consistency field data) on venue day |

## 🧾 Current Open Items (tracked honestly for judges)

- **O-1:** HSV tuner writes `camera.hsv_tuned`; perception reads per-colour keys — wiring scheduled before venue.
- **O-2:** parking hold is 5.0 s in code vs "15-second stationary rule" in comments — verify against 2026 rulebook.
- **O-3:** commanded-speed units differ between Layer 3 (mm/s scale) and Layers 8/10 (%) — unification scheduled.
- **O-4:** `controller.pid_speed` gains are unused (open-loop speed + jerk limiter); decision pending encoder feedback.
