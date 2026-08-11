# Architecture - v9.3
WRO 2026 4WS - Raspberry Pi 4B + ESP32-S3
           +-------------------+
  main.py  | 100 Hz control loop
           |   |-> L1 sensors thread (VL53x3 + MPU)
           |   |-> L2 time-sync buffer
           |   |-> L3 UKF fusion (6D)
           |   |-> L4 perception thread (30 FPS)
           |   |-> L5 localization + tilt
           |   |-> L6 mission state machine
           |   |-> L7 path planner
           |   |-> L8 trajectory optimization
           |   |-> L9 4WS kinematics
           |   |-> L10 Stanley + serial TX
           +-------------------+
                    | CRC8 10-byte packets @100Hz
           +-------------------+
  ESP32-S3 | servo + motor + watchdog (200ms)
           | 5 LEDs + failsafe
           +-------------------+