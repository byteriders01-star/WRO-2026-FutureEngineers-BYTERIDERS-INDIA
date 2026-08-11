# v9.9 Release Notes - WRO 2026 4WS
## System
- Pi 4B brain + ESP32-S3 muscle, 100 Hz control, 30 FPS vision
- 5-LED health + Switch 2 start, serial CRC8 watchdog 200ms
## Sensors
- VL53L1X front (33ms budget) + 2x VL53L0X (XSHUT sequenced, -50mm offset)
- MPU6050 UKF 6D fusion, tilt compensation
## Mission
- 7-state machine, 3-lap counter, stop-and-go, emergency brake, parallel park
- Surprise rules in JSON: SIGN_LOGIC, DRIVING_DIRECTION, NARROW_TRACK_MODE, PARKING_REVERSAL
## Motion
- Single MG995 4WS linkage (rear ratio 0.85), adaptive Stanley k=0.75
- Centripetal 1.2 m/s^2, jerk-limited ramps
## Metrics
- Max speed 1.8 m/s, min radius 0.5 m, parking +/-2cm
- Target: 122/122 pts
## Final snapshot contains the complete working source.