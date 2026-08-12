<div align="center">

# 🤖 WRO 2026 – Future Engineers
# Team **BYTE RIDERS**

**World Robot Olympiad 2026 · Future Engineers Category**


[![WRO](https://img.shields.io/badge/WRO-2026-blue)](https://wroindia.org)
[![Category](https://img.shields.io/badge/Category-Future%20Engineers-orange)]()
[![Country](https://img.shields.io/badge/Country-India-green)]()
[![Status](https://img.shields.io/badge/Status-In%20Development-yellow)]()

<!-- Add team logo/banner image here, e.g. ./t-photos/team_banner.png -->

</div>

---

## 📑 Table of Contents

1. [Team Introduction](#1-team-introduction)
2. [Repository Structure](#2-repository-structure)
3. [Project Overview](#3-project-overview)
4. [Mobility Management — Mechanical Design](#4-mobility-management--mechanical-design)
5. [Power & Sense Management — Electronics](#5-power--sense-management--electronics)
6. [Obstacle Management — Software & Control](#6-obstacle-management--software--control)
7. [System Architecture](#7-system-architecture)
8. [Engineering Specifications](#8-engineering-specifications)
9. [Component & Power Distribution Table](#9-component--power-distribution-table)
10. [Vehicle Photos](#10-vehicle-photos)
11. [Performance & Testing](#11-performance--testing)
12. [Video Demonstrations](#12-video-demonstrations)
13. [How to Reproduce This Robot](#13-how-to-reproduce-this-robot)
14. [Bill of Materials](#14-bill-of-materials)
15. [Challenges & Learnings](#15-challenges--learnings)
16. [Future Improvements](#16-future-improvements)
17. [Acknowledgments & References](#17-acknowledgments--references)
18. [License](#18-license)

---

## 1. Team Introduction

**Team Name:** Byte Riders
**Institution:** CHARUSAT — Charotar University of Science and Technology
**Competition:** World Robot Olympiad 2026, Future Engineers Category

Byte Riders is a two-member engineering team built around a clean split between mechanical and software ownership, developing a fully autonomous, self-driving vehicle for the WRO Future Engineers category. The team's approach centers on a 4-wheel-steering mechanical platform paired with a dual-controller electronics stack — a Raspberry Pi 4B for high-level perception and decision-making, and a dedicated ESP32-S3 for deterministic, real-time actuation — so that vision processing never compromises steering or motor response time.

<!-- Coach name and role currently not provided — add coach row below when available. -->

| Photo | Name | Role | Responsibilities |
|---|---|---|---|
| <!-- photo --> | **Shrut Barasara** | Mechanical & Hardware Lead | Chassis design, 4-wheel steering geometry, sensor mounting, wiring, power distribution |
| <!-- photo --> | **Happy Patel** | Software & Version Control Engineer | Embedded firmware (ESP32-S3), vision pipeline (OpenCV), Git/GitHub workflow, repository management |
| <!-- photo --> | **TBD** | Coach | — |

<!-- Add team photo here — see Section 10 for the full photo checklist -->

---

## 2. Repository Structure

```
WRO-2026-FutureEngineers-BYTERIDERS-INDIA/
│
├── docs/
│   ├── components/              # One .md datasheet-reference file per component
│   │   ├── raspberry_pi_4b.md
│   │   ├── esp32_s3.md
│   │   ├── l298n.md
│   │   ├── mg995.md
│   │   ├── mpu6050.md
│   │   ├── vl53l0x.md
│   │   ├── vl53l1x.md
│   │   ├── drive_motor.md
│   │   └── lipo_battery.md
│   ├── power/
│   │   └── POWER_DISTRIBUTION.md
│   └── wiring/
│       └── WIRING.md
│
├── models/                      # CAD source files + exported STL/STEP for all printed & machined parts
│
├── schemes/                     # Circuit + wiring schematics (PDF / PNG)
│
├── src/
│   ├── open_challenge/          # Firmware + vision code for the Open Challenge
│   └── obstacle_challenge/      # Firmware + vision code for the Obstacle Challenge
│
├── t-photos/                    # Team photo(s)
├── v-photos/                    # Vehicle photos — front, back, left, right, top, bottom
├── video/
│   └── video.md                 # Links to Open & Obstacle Challenge demo videos
│
├── LICENSE
└── README.md                    # You are here
```

<!-- This structure mirrors the folder layout referenced inside docs/power/POWER_DISTRIBUTION.md and docs/wiring/WIRING.md.
     Could not crawl the live repo tree (GitHub blocks automated fetching) — verify folder names against the actual repo before publishing. -->

---

## 3. Project Overview

Team Byte Riders' vehicle is a fully autonomous, self-driving robot built for the WRO 2026 Future Engineers category. The car must complete the **Open Challenge** (three laps of an unknown, randomly-configured track using wall/edge sensing) and the **Obstacle Challenge** (three laps while dynamically detecting and avoiding red/green traffic pillars, then performing precision parking) with zero human intervention after the start signal.

### Design Philosophy
The vehicle uses a **camera-based perception system** running on a Raspberry Pi 4B for high-level decision-making (pillar color and parking-block detection), paired with a dedicated **ESP32-S3 real-time controller** that closes the low-level steering/motor control loop independently of the vision pipeline's frame rate. This split-brain architecture keeps actuator response deterministic (100 Hz) even while the Pi is busy processing camera frames.

### Key Design Choices
- **4-Wheel Steering (4WS)** using Ackermann steering geometry on both axles, for a significantly tighter turning radius than front-wheel steering — important given the tight corners on a WRO Future Engineers arena.
- **Sensor fusion** of a monocular camera (OpenCV, color-based pillar/parking detection), three Time-of-Flight distance sensors (front/left/right), and a 6-DoF IMU for heading correction and drift compensation.
- **Deterministic actuator control:** the Pi streams high-level commands to the ESP32-S3 over a binary, CRC8-checked serial protocol at 100 Hz, so steering/motor response is never blocked by vision-processing latency.

---

## 4. Mobility Management — Mechanical Design

### Steering
The vehicle uses a **4-Wheel Steering (4WS) system based on Ackermann steering theory**, applied symmetrically to the front and rear axles. Unlike a standard front-wheel-steering (FWS) layout, 4WS lets the rear wheels counter-steer relative to the front, which:
- Shrinks the turning radius substantially (see [Section 8](#8-engineering-specifications) — **~44.9% smaller than an equivalent FWS layout**).
- Improves cornering stability on tight track segments.

### Drivetrain
- **Drive motor:** Johnson-type geared DC motor, **300 RPM**, driven through an **L298N** dual H-bridge driver (`ENA` → speed/PWM, `IN1`/`IN2` → direction). This RPM class was selected to balance top speed against the torque needed for quick direction/heading corrections on a compact 4WS chassis.
- **Measured steering range:** **35°–40°** at the wheel, matching the ±35° design target in the specification table below.
- **Chassis material:** PETG with 30% gyroid infill, chosen for isotropic stiffness and heat resistance (T<sub>g</sub> ≈ 80 °C).

<!-- Add chassis/steering assembly renders or photos here -->

---

## 5. Power & Sense Management — Electronics

### High-Level Sensing (Raspberry Pi 4B)
- **Pi Camera v2** — OpenCV-based red/green pillar detection and magenta parking-block detection.
- **VL53L1X** Front ToF — I²C address `0x30`, `XSHUT` on GPIO 22.
- **VL53L0X** Left ToF — I²C address `0x31`, `XSHUT` on GPIO 17.
- **VL53L0X** Right ToF — I²C address `0x32`, `XSHUT` on GPIO 27.
- **MPU6050** 6-DoF IMU — I²C address `0x68`.

### Inter-Processor Link
The Raspberry Pi 4B communicates with the ESP32-S3 over **USB serial**, using a **10-byte, CRC8-checked binary packet streamed at 100 Hz**. This keeps the safety-critical steering/motor loop running on dedicated real-time hardware, decoupled from the Pi's variable-latency vision pipeline.

### Real-Time Actuation (ESP32-S3)
- **MG995 servo** — 4WS steering actuator, GPIO 18, 50 Hz PWM.
- **L298N `ENA`** — motor speed control, GPIO 19, PWM.
- **L298N `IN1`** — direction control, GPIO 20.
- **L298N `IN2`** — direction control, GPIO 21.

### Power Rails
See the full [Component & Power Distribution Table](#9-component--power-distribution-table) below — all rail definitions live in `docs/power/POWER_DISTRIBUTION.md`, and pin-level connections live in `docs/wiring/WIRING.md`.

<!-- Add a labelled photo of the wiring/electronics bay -->
<!-- Add battery capacity/runtime, and any fusing/reverse-polarity protection details when available -->

---

## 6. Obstacle Management — Software & Control

### Perception
- **Color-based pillar detection (OpenCV):** HSV thresholding identifies red and green pillars in the camera frame; the robot passes red pillars on the right and green pillars on the left.
- **Magenta parking-block detection:** a dedicated HSV mask locates the parking-lot marker for the precision-parking maneuver at the end of each run.
- **ToF wall-following:** the left/right VL53L0X sensors maintain a target offset from the inner wall; the front VL53L1X sensor triggers corner/obstacle response.
- **IMU heading correction:** the MPU6050 supplies yaw-rate data used to correct for drift between vision updates and to execute clean, repeatable turns.

### Control Loop
- **Control loop rate:** 100 Hz on the ESP32-S3 (5× the ~10 Hz mechanical bandwidth of the servo/motor).
- **Serial link:** 115,200 baud, <9% UART utilization at the 100 Hz packet rate — comfortable headroom for retries/CRC handling.

<!-- Add the specific control algorithm (state machine / PID / pure-pursuit), tuning constants, parking trigger logic,
     and calibration routine details here once available — this section carries the most weight for the Obstacle Challenge score. -->

---

## 7. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Raspberry Pi 4B  (High-Level: Perception, Navigation & Control) │
│                                                                   │
│  ├── Pi Camera v2                                                │
│  │     (OpenCV Red/Green Pillar + Magenta Parking Block Detect)  │
│  ├── VL53L1X Front ToF   (I2C 0x30, XSHUT → GPIO 22)             │
│  ├── VL53L0X Left  ToF   (I2C 0x31, XSHUT → GPIO 17)             │
│  ├── VL53L0X Right ToF   (I2C 0x32, XSHUT → GPIO 27)             │
│  └── MPU6050 6-DoF IMU   (I2C 0x68)                              │
└──────────────────────────────┬────────────────────────────────────┘
                                │  USB Serial
                                │  10-byte CRC8 Binary Packet @ 100 Hz
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│         ESP32-S3  (Real-Time Motor & Steering Controller)        │
│                                                                   │
│  ├── MG995 Servo  — 4WS Steering   (GPIO 18, PWM 50 Hz)          │
│  ├── L298N ENA    — Motor Speed    (GPIO 19, PWM)                │
│  ├── L298N IN1    — Direction      (GPIO 20)                     │
│  └── L298N IN2    — Direction      (GPIO 21)                     │
└─────────────────────────────────────────────────────────────────┘
```

<!-- Consider re-drawing this as an exported PNG/SVG (draw.io, Figma) and placing it in schemes/ —
     GitHub renders images more consistently across viewers than ASCII art. -->

---

## 8. Engineering Specifications

| Parameter | Value | Justification |
|---|---|---|
| Vehicle Length | 230 mm | 23% margin under 300 mm WRO Rule 11.1 limit |
| Vehicle Width | 160 mm | 20% margin under 200 mm WRO Rule 11.1 limit |
| Wheelbase | 160 mm | 50:50 weight distribution, optimal pitch stability |
| Track Width | 130 mm | Rollover threshold 1.86 g ≫ max grip 0.80 g |
| Turning Radius (4WS) | ~126 mm | 44.9% smaller than FWS equivalent |
| Max Steering Angle | ±35° | CVD joint binding hard-stop limit |
| Rear/Front Steering Ratio (κ) | 0.85 | Optimal inner-wall clearance in tight corners |
| Control Loop Rate | 100 Hz | 5× Nyquist margin over 10 Hz actuator bandwidth |
| Serial Baud Rate | 115,200 | <9% UART utilization at 100 Hz packet rate |
| Chassis Material | PETG, 30% gyroid infill | Isotropic stiffness, T<sub>g</sub> 80 °C heat resistance |
| Drive Motor | Johnson-type DC, 300 RPM | Balances top speed against torque needed for rapid heading corrections |
| Measured Turning Angle | 35°–40° | Bench-measured, matches ±35° design spec |

<!-- Optional additions: total vehicle mass, ground clearance, wheel diameter/type, gear ratio, battery weight -->

---

## 9. Component & Power Distribution Table

| Component | File | Power Rail | Interface | Official Datasheet |
|---|---|---|---|---|
| Raspberry Pi 4 Model B | [`raspberry_pi_4b.md`](docs/components/raspberry_pi_4b.md) | 5V rail | GPIO, I2C1, UART | [PDF](#) |
| ESP32-S3 | [`esp32_s3.md`](docs/components/esp32_s3.md) | Pi USB (5V) | UART, PWM | [PDF](#) |
| L298N driver module | [`l298n.md`](docs/components/l298n.md) | Motor rail 11.1V | ENA / IN1 / IN2 | [PDF](#) |
| MG995 steering servo | [`mg995.md`](docs/components/mg995.md) | Servo rail (UBEC 5V) | 50 Hz PWM | [PDF](#) |
| MPU6050 IMU | [`mpu6050.md`](docs/components/mpu6050.md) | Pi 3.3V | I2C | [PDF](#) |
| VL53L0X ToF (left/right) | [`vl53l0x.md`](docs/components/vl53l0x.md) | Pi 3.3V | I2C | [PDF](#) |
| VL53L1X ToF (front) | [`vl53l1x.md`](docs/components/vl53l1x.md) | Pi 3.3V | I2C | [PDF](#) |
| Drive motor (AWD) | [`drive_motor.md`](docs/components/drive_motor.md) | Motor rail (via L298N) | PWM DC | none — bench measured |
| LiPo 3S battery | [`lipo_battery.md`](docs/components/lipo_battery.md) | source (11.1V) | XT60 | none — manufacturer data |

*All power rails are defined in [`docs/power/POWER_DISTRIBUTION.md`](docs/power/POWER_DISTRIBUTION.md); pin connections are in [`docs/wiring/WIRING.md`](docs/wiring/WIRING.md).*

<!-- Replace the # placeholder datasheet links with real manufacturer PDF URLs. -->

---

## 10. Vehicle Photos

| Front | Back | Left |
|---|---|---|
| <!-- photo --> | <!-- photo --> | <!-- photo --> |

| Right | Top | Bottom |
|---|---|---|
| <!-- photo --> | <!-- photo --> | <!-- photo --> |

<!-- Full checklist: 6 vehicle angles, team photo, individual member photos, wiring bay close-up,
     4WS steering close-up, sensor mounting close-up, CAD renders, wiring schematic scan. -->

---

## 11. Performance & Testing

<!-- Add lap times (Open/Obstacle), pillar-detection and parking success rates, and known failure modes here. -->

---

## 12. Video Demonstrations

| Challenge | Link |
|---|---|
| Open Challenge | — |
| Obstacle Challenge | — |

Full details and links live in [`video/video.md`](video/video.md).

---

## 13. How to Reproduce This Robot

### Mechanical
1. Print/source the chassis parts from `models/` (PETG, 30% gyroid infill recommended, see [Section 8](#8-engineering-specifications)).
2. Assemble the 4-wheel Ackermann steering linkage per the CAD assembly drawing in `models/`.
3. Mount the Johnson 300 RPM drive motor and confirm the measured steering range (35°–40°) matches spec before proceeding.

### Electronics
1. Wire all components exactly as documented in [`docs/wiring/WIRING.md`](docs/wiring/WIRING.md) and the [power table above](#9-component--power-distribution-table).
2. Set I²C addresses for the three ToF sensors (`0x30` / `0x31` / `0x32`, set via `XSHUT` sequencing at boot) and the MPU6050 (`0x68`).

### Software
1. Flash the ESP32-S3 with the firmware in `src/`.
2. Set up the Raspberry Pi 4B with the required dependencies.
3. Run the calibration routine to tune HSV thresholds for competition lighting.
4. Launch the main control script for the desired challenge (`src/open_challenge/` or `src/obstacle_challenge/`).

<!-- Fill in exact file paths and commands (e.g. python3 src/open_challenge/main.py) so another team can follow this with zero guessing.
     Consider adding a requirements.txt and/or platformio.ini at the repo root. -->

---

## 14. Bill of Materials

<!-- Add component quantities, approximate cost, and vendor/source here. -->

---

## 15. Challenges & Learnings

<!-- Add 2–5 honest "what went wrong and how we fixed it" bullets — this is one of the highest-value, easiest additions
     for README depth and is what separates a documentation dump from real engineering journaling. -->

---

## 16. Future Improvements

<!-- Add 2–4 bullets on what you'd do differently or add with more time. -->

---

## 17. Acknowledgments & References

- World Robot Olympiad Association & WRO India — competition rules and guidelines.
- CHARUSAT for mentorship and lab/workshop access.

<!-- Add coach name, and any open-source libraries/tutorials/prior-year repositories that informed this design. -->

---

## 18. License

<!-- Add a LICENSE file at the repo root and state the license here (MIT is common for WRO open-source repos). -->

---

<div align="center">

**Built by Team Byte Riders 🚗⚡ — CHARUSAT**
*WRO 2026 Future Engineers*

</div>
