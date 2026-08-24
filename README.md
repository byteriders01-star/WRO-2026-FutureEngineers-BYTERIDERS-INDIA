
<div align="center">
<img src="BRANDING/logo_after_4WS.jpg" alt="Logo After 4WS" width="400">


# 🤖 WRO 2026 – Future Engineers
# Team **BYTE RIDERS**

**World Robot Olympiad 2026 · Future Engineers Category**

[![WRO](https://img.shields.io/badge/WRO-2026-blue)](https://wroindia.org)
[![Category](https://img.shields.io/badge/Category-Future%20Engineers-orange)]()
[![Country](https://img.shields.io/badge/Country-India-green)]()
[![Status](https://img.shields.io/badge/Status-In%20Development-yellow)]()

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
11. [Video Demonstrations](#11-video-demonstrations)
12. [How to Reproduce This Robot](#12-how-to-reproduce-this-robot)
13. [Bill of Materials (BOM)](#13-bill-of-materials-bom)
14. [WRO 2026 Surprise Rules Readiness](#14-wro-2026-surprise-rules-readiness)
15. [Engineering Post-Mortem — What Went Wrong & Fixes](#15-engineering-post-mortem--what-went-wrong--fixes)
16. [References & Acknowledgments](#16-references--acknowledgments)

---

## 1. Team Introduction

**Team Name:** Byte Riders  
**Competition:** World Robot Olympiad 2026, Future Engineers Category

Byte Riders is a two-member engineering team built around a clean split between mechanical and software ownership, developing a fully autonomous, self-driving vehicle for the WRO Future Engineers category. The team's approach centers on a 4-wheel-steering mechanical platform paired with a dual-controller electronics stack — a Raspberry Pi 4B for high-level perception and decision-making, and a dedicated ESP32-S3 for deterministic, real-time actuation.

---

<h3 align="center">👨‍💻 Meet the Team</h3>

<table align="center">
<tr>

<td align="center" width="33%">

<img src="https://github.com/user-attachments/assets/d21bec4c-5d1e-41b7-9e72-61128f5b7a66" width="300" alt="Shrut Barasara">

### Shrut Barasara

**Mechanical & Hardware Lead**

Chassis design, 4-wheel steering geometry, sensor mounting, wiring, and power distribution.

</td>

<td align="center" width="33%">

<img src="https://github.com/user-attachments/assets/01f8d001-fef8-4bf8-8a35-8ab29fd71b7d" width="300" alt="Happy Patel">

### Happy Patel

**Software & Version Control Engineer**

Embedded firmware, ESP32-S3 programming, OpenCV vision pipeline, Git/GitHub workflow, and repository management.

</td>

<td align="center" width="33%">

<img src="https://github.com/user-attachments/assets/f87b31eb-6b12-4b34-a412-93f213edb491" width="300" alt="Brijesh Kundaliya">

### Brijesh Kundaliya

**Coach & Mentor**

Technical mentorship, engineering review, design guidance, and competition-readiness support.

</td>

</tr>
</table>

---

## 2. Repository Structure

```
WRO-2026-FutureEngineers-BYTERIDERS-INDIA/
│
├── assets/
│   ├── logo.jpeg                 # Team logo used in this README
│   └── hardware/                 # Individual component photos + spec reference table (Section 5.6)
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
│   └── DIFFERENTIAL_GEAR/       # Custom 3D-printed differential gear assembly (bevel pinion + ring)
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
├── config/
│   └── robot_config.json        # Runtime-tunable parameters, incl. WRO 2026 surprise-rule overrides
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
- **Custom 3D-printed differential drivetrain** on the rear axle, engineered from first principles (see [Section 4.2](#42-drivetrain--differential-gear-kinematic-derivation)) rather than a stock off-the-shelf differential.
- **Deterministic actuator control:** the Pi streams high-level commands to the ESP32-S3 over a binary, CRC8-checked serial protocol at 100 Hz, so steering/motor response is never blocked by vision-processing latency.

---

## 4. Mobility Management — Mechanical Design

### 4.1 Steering

The vehicle uses a **4-Wheel Steering (4WS) system based on Ackermann steering theory**, applied symmetrically to the front and rear axles. Unlike a standard front-wheel-steering (FWS) layout, 4WS lets the rear wheels counter-steer relative to the front, which:
- Shrinks the turning radius substantially (see [Section 8](#8-engineering-specifications) — **~44.9% smaller than an equivalent FWS layout**).
- Improves cornering stability on tight track segments.

**Measured steering range:** **35°–40°** at the wheel, matching the ±35° design target in the specification table below.
**Chassis material:** PETG with 30% gyroid infill, chosen for isotropic stiffness and heat resistance (T<sub>g</sub> ≈ 80 °C).

<!-- Add chassis/steering assembly renders or photos here -->

### 4.2 Drivetrain & Differential Gear Kinematic Derivation

The rear drivetrain incorporates a **custom-designed, 3D-printed differential gear mechanism** (`models/DIFFERENTIAL_GEAR/`) combined with a **Johnson 300 RPM / 12 V DC motor**.

**Drivetrain chain, motor to wheel:**

```
Johnson Motor Armature: 6000 RPM @ 12V
        │
        ▼
20:1 Planetary Gearbox (Internal Motor Gearhead)
        │
        ▼
Output Shaft: 300 RPM @ 12V (Stall Torque: 0.85 Nm)
        │
        ▼
10T Bevel Pinion Gear (Bevel_Gears-10T_.f3d)
        │   (2:1 Gear Reduction)
        ▼
20T Bevel Ring Gear (Bevel_Gear-20T_.f3d, mounted on case1.f3d)
        │
        ▼
Solid Differential Rear Axle: 150 RPM (1.70 Nm Axle Torque)
        │
        ▼
65 mm High-Grip Rubber Wheels (Tractive Force: 52.3 N)
```

**Gear Ratio & Torque Physics Derivations:**

1. **Internal Motor Planetary Gearbox:** 20:1 reduction.
2. **Rear Differential Bevel Gear Set:**
   - Pinion Gear: 10 teeth (`Bevel_Gears-10T_.f3d`)
   - Ring Gear: 20 teeth (`Bevel_Gear-20T_.f3d`)
   - Differential Reduction Ratio: 20T / 10T = **2 : 1**
3. **Total Drive Reduction Ratio (G<sub>total</sub>):** G<sub>total</sub> = 20 × 2 = **40 : 1** total gear reduction.
4. **Wheel Rotational Speed (N<sub>wheel</sub>):** N<sub>wheel</sub> = 300 RPM (Motor Shaft) ÷ 2 (Differential Ratio) = **150 RPM = 2.5 rev/s**.
5. **Maximum Vehicle Linear Velocity (v<sub>max</sub>):** v<sub>max</sub> = N<sub>wheel</sub> × (π · D<sub>w</sub>) = 2.5 rev/s × (π × 0.065 m) = 0.5105 m/s ≈ **0.51 m/s**.
6. **Total Drive Axle Torque (τ<sub>axle</sub>):** τ<sub>axle</sub> = τ<sub>motor</sub> × 2 = 0.85 Nm × 2 = **1.70 Nm** (17.33 kg·cm).
7. **Total Tractive Force (F<sub>drive</sub>):** F<sub>drive</sub> = τ<sub>axle</sub> / r<sub>w</sub> = 1.70 Nm / 0.0325 m = **52.31 N**.
8. **Torque Safety Margin Over Vehicle Weight:** Total Vehicle Weight W<sub>v</sub> = 1.215 kg × 9.81 m/s² = 11.92 N. Tractive Force Safety Margin = 52.31 N / 11.92 N = **4.39× torque safety margin**.

This 4.39× margin confirms the drivetrain has substantial reserve tractive force over the vehicle's own weight, ensuring reliable acceleration and hill-start behavior even with sensor/battery payload variance.

---

## 5. Power & Sense Management — Electronics

### 5.1 High-Level Sensing (Raspberry Pi 4B)
- **Pi Camera v2** — OpenCV-based red/green pillar detection and magenta parking-block detection.
- **VL53L1X** Front ToF — I²C address `0x30`, `XSHUT` on GPIO 22.
- **VL53L0X** Left ToF — I²C address `0x31`, `XSHUT` on GPIO 17.
- **VL53L0X** Right ToF — I²C address `0x32`, `XSHUT` on GPIO 27.
- **MPU6050** 6-DoF IMU — I²C address `0x68`.

### 5.2 Inter-Processor Link
The Raspberry Pi 4B communicates with the ESP32-S3 over **USB serial**, using a **10-byte, CRC8-checked binary packet streamed at 100 Hz**. This keeps the safety-critical steering/motor loop running on dedicated real-time hardware, decoupled from the Pi's variable-latency vision pipeline.

### 5.3 Real-Time Actuation (ESP32-S3)
- **MG995 servo** — 4WS steering actuator, GPIO 18, 50 Hz PWM.
- **L298N `ENA`** — motor speed control, GPIO 19, PWM.
- **L298N `IN1`** — direction control, GPIO 20.
- **L298N `IN2`** — direction control, GPIO 21.

### 5.4 Power Architecture

```mermaid
graph TD
    BAT["11.1V 3S LiPo Battery (2200 mAh)"]
    FUSE["10A Blade Fuse (ATO)"]
    SW["Master Mechanical Toggle Switch"]
    BUCKA["Buck A: 5V / 3A (Logic Plane)"]
    BUCKB["Buck B: 6V / 3A (Actuator Plane)"]
    L298N["L298N VMS +12V (Motor Plane)"]
    PI["Raspberry Pi (Compute)"]
    ESP["ESP32-S3 (Control)"]
    SERVO["MG995 (Servo VCC) — GPIO 18 PWM"]
    MOTOR["Johnson DC Motor (Rear Axle) — GPIO 19-21"]

    BAT --> FUSE --> SW
    SW --> BUCKA
    SW --> BUCKB
    SW --> L298N
    BUCKA --> PI
    BUCKA --> ESP
    BUCKB --> SERVO
    L298N --> MOTOR
```

**Power distribution tree (text form):**

```
11.1V 3S LiPo Battery (2200 mAh)
        │
10A Blade Fuse (ATO)
        │
Master Mechanical Toggle Switch
        │
        ├── Buck A: 5V / 3A (Logic Plane)   → Raspberry Pi (Compute), ESP32-S3 (Control)
        ├── Buck B: 6V / 3A (Actuator Plane) → MG995 Servo VCC  [ESP32 GPIO 18 PWM]
        └── L298N VMS (+12V, Motor Plane)    → Johnson DC Motor, Rear Axle [ESP32 GPIO 19–21]
```

### 5.5 Battery Capacity & WHY Factors for Electronics Selection

- **Battery Pack:** 3S 11.1 V, 2200 mAh LiPo battery pack (24.42 Wh total energy).
  - **WHY 3S 11.1V (not 2S 7.4V):** The L298N motor driver drops ≈1.8–2.0 V across its internal Darlington transistors. On 7.4 V, motor voltage drops to 5.4 V, lowering top speed by <0.23 m/s (a 55% drop). 11.1 V maintains the full 9.2 V motor voltage needed for target speeds.
  - **WHY 2200 mAh (not 5000 mAh):** A 2200 mAh pack weighs 180 g. A 5000 mAh pack weighs 410 g, pushing vehicle weight over the 1500 g rule limit.
- **Average Power Draw:** 1.85 A @ 11.1 V (20.5 W nominal).
- **Peak Power Draw:** 3.85 A @ 11.1 V (42.7 W) under full acceleration + maximum steering lock.
- **Estimated Runtime:** ~38 minutes of continuous racing load (185+ laps per charge).
- **WHY Dual Buck Converters (5V/3A Buck A & 6V/3A Buck B):**
  - MG995 servo torque is 8.5 kg·cm @ 4.8 V, but 11.0 kg·cm @ 6.0 V (a 29.4% torque increase).
  - Powering the servo off the Pi's 5 V rail caused 450 mV inductive transients, triggering Pi brownout resets (`Undervoltage detected`). Dedicating Buck B (6V/3A) to the servo completely eliminated logic brownouts.

<!-- Add a labelled photo of the wiring/electronics bay -->

### 5.6 Hardware Components — Detailed Specifications & Photos

Every major component on the vehicle is documented below with its role in the system, key electrical/mechanical specifications, and a photo slot. Drop the corresponding product photo into `assets/hardware/<component-name>.jpg` and it will render automatically in the cell below (the `<!-- photo -->` markers show exactly where each image belongs).
<table border="1" cellpadding="10" cellspacing="0">
  <thead>
    <tr bgcolor="#0d1117" align="center">
      <th width="15%">Photo</th>
      <th width="25%">Component</th>
      <th width="60%">Description & Role in the System</th>
    </tr>
  </thead>
  <tbody>
    <!-- Row 1: Raspberry Pi -->
    <tr>
      <td align="center" valign="middle">
        <img src="DOCS/FINAL_COMPONENTS%20USED/rasberry%20pi.png" width="100" alt="Raspberry Pi 4">
      </td>
      <td>
        <strong>Raspberry Pi 4 Model B</strong><br>
        <font color="#8b949e">4 GB RAM · ARM Cortex-A72</font>
      </td>
      <td>The vehicle's high-level "brain." A quad-core, 64-bit ARM Cortex-A72 SoC clocked at 1.5 GHz with 4 GB of LPDDR4 RAM runs the entire perception and decision-making stack — the OpenCV vision pipeline, the 6-DoF Unscented Kalman Filter, the mission-manager state machine, and the Bézier path planner (Layers 1, 3, 4, 6–10 of the software pipeline in Section 6). It streams the resulting steering/speed commands to the ESP32-S3 over USB serial. Chosen over lighter boards specifically for its CSI camera interface and the CPU headroom needed to run HSV segmentation at frame rate without starving the control loop.</td>
    </tr>
    <!-- Row 2: ESP32-S3 -->
    <tr>
      <td align="center" valign="middle">
        <img src="DOCS/FINAL_COMPONENTS%20USED/ESP32-S3.png" width="100" alt="ESP32-S3">
      </td>
      <td>
        <strong>ESP32-S3 DevKitC</strong><br>
        <font color="#8b949e">Dual-core 240 MHz · Wi-Fi + BT</font>
      </td>
      <td>The vehicle's real-time "spinal cord." A dual-core Xtensa LX7 microcontroller running at 240 MHz, dedicated entirely to deterministic actuation — driving the MG995 steering servo and the L298N motor driver via hardware LEDC PWM. Receiving commands from the Pi as 10-byte, CRC8-checked binary packets at 100 Hz, it guarantees the steering/motor loop never stalls or jitters even if the vision pipeline momentarily lags, decoupling "thinking" from "acting."</td>
    </tr>
    <!-- Row 3: Pi Camera -->
    <tr>
      <td align="center" valign="middle">
        <img src="DOCS/FINAL_COMPONENTS%20USED/PI-CAMERA%20V2.png" width="100" alt="Pi Camera v2">
      </td>
      <td>
        <strong>Pi Camera v2</strong><br>
        <font color="#8b949e">Sony IMX219 · 8 MP · CSI</font>
      </td>
      <td>The vehicle's only forward-facing vision sensor, connected to the Raspberry Pi via the CSI ribbon interface for low-latency, uncompressed frame capture. Its 8 MP Sony IMX219 sensor feeds the OpenCV HSV-thresholding pipeline that identifies red/green traffic pillars and the magenta parking-block marker, forming the entire basis of Obstacle Challenge perception.</td>
    </tr>
    <!-- Row 4: VL53L1X ToF -->
    <tr>
      <td align="center" valign="middle">
        <img src="DOCS/FINAL_COMPONENTS%20USED/VL53L1X%20ToF%20Sensor.png" width="100" alt="VL53L1X ToF">
      </td>
      <td>
        <strong>VL53L1X ToF Sensor</strong><br>
        <font color="#8b949e">Front distance · 0-4000 mm</font>
      </td>
      <td>A long-range Time-of-Flight laser-ranging sensor mounted facing forward (I²C address 0x30, XSHUT on GPIO 22). Its extended 4-metre range makes it well suited to detecting the front wall or an approaching obstacle pillar early enough for the path planner to react smoothly rather than reactively.</td>
    </tr>
    <!-- Row 5: VL53L0X ToF -->
    <tr>
      <td align="center" valign="middle">
        <img src="DOCS/FINAL_COMPONENTS%20USED/VL53L0X%20ToF%20Sensors.png" width="100" alt="VL53L0X ToF">
      </td>
      <td>
        <strong>VL53L0X ToF Sensors (×2)</strong><br>
        <font color="#8b949e">Left/Right distance · 0-2000 mm</font>
      </td>
      <td>A pair of shorter-range ToF sensors mounted on the left and right flanks (I²C addresses 0x31 / 0x32, XSHUT on GPIO 17/27). They continuously measure clearance to the inner and outer arena walls, feeding the wall-following logic that keeps the vehicle centred in its lane between camera-based corrections.</td>
    </tr>
    <!-- Row 6: MPU6050 IMU -->
    <tr>
      <td align="center" valign="middle">
        <img src="DOCS/FINAL_COMPONENTS%20USED/MPU6050.png" width="100" alt="MPU6050 IMU">
      </td>
      <td>
        <strong>MPU6050 IMU</strong><br>
        <font color="#8b949e">6-DoF gyro + accelerometer · I²C 0x68</font>
      </td>
      <td>A 6-degree-of-freedom inertial measurement unit combining a 3-axis gyroscope and a 3-axis accelerometer on a single die. Its yaw-rate output is fused into the 6-state Unscented Kalman Filter (Layer 3) to correct for heading drift between camera updates and to execute clean, repeatable turns — critical since the raw gyro alone drifts roughly 5°/minute due to thermal bias (see Section 15).</td>
    </tr>
    <!-- Row 7: MG995 Servo -->
    <tr>
      <td align="center" valign="middle">
        <img src="DOCS/FINAL_COMPONENTS%20USED/MG995%20Servo.png" width="100" alt="MG995 Servo">
      </td>
      <td>
        <strong>MG995 Servo</strong><br>
        <font color="#8b949e">11 kg·cm torque · 50 Hz PWM</font>
      </td>
      <td>A metal-gear standard servo driving the 4-Wheel-Steering linkage on both axles simultaneously through the mechanical bellcrank assembly. Delivering 11 kg·cm of torque at its dedicated 6 V rail (versus only 8.5 kg·cm at 4.8 V — a 29% torque loss), it easily overcomes steering-linkage friction at the full ±35° lock without stalling.</td>
    </tr>
    <!-- Row 8: Johnson DC Motor -->
    <tr>
      <td align="center" valign="middle">
        <img src="DOCS/FINAL_COMPONENTS%20USED/Johnson%20DC%20Motor.png" width="100" alt="Johnson DC Motor">
      </td>
      <td>
        <strong>Johnson DC Motor</strong><br>
        <font color="#8b949e">20:1 planetary · 12 V · 600 RPM (armature)</font>
      </td>
      <td>A brushed DC motor with an internal 20:1 planetary gearhead, providing the sole source of propulsion. Its output shaft (300 RPM, 0.85 N·m stall torque) drives the custom 3D-printed differential (see Section 4.2) through a 2:1 bevel gear reduction, yielding a 40:1 total drive ratio and a calculated 4.39× torque safety margin over the vehicle's own weight.</td>
    </tr>
    <!-- Row 9: L298N Motor Driver -->
    <tr>
      <td align="center" valign="middle">
        <img src="DOCS/FINAL_COMPONENTS%20USED/L298N%20Motor%20Driver.png" width="100" alt="L298N Motor Driver">
      </td>
      <td>
        <strong>L298N Motor Driver</strong><br>
        <font color="#8b949e">2 A continuous · 12 V dual H-bridge</font>
      </td>
      <td>A dual H-bridge module that converts the ESP32-S3's low-current PWM/direction signals (ENA / IN1 / IN2 on GPIO 19-21) into the high-current drive needed by the Johnson DC motor, sourcing its motor-plane power directly from the fused 11.1 V battery rail rather than a regulated supply.</td>
    </tr>
    <!-- Row 10: 3S LiPo Battery -->
    <tr>
      <td align="center" valign="middle">
        <img src="DOCS/FINAL_COMPONENTS%20USED/3S%20LiPo%20Battery.png" width="100" alt="3S LiPo Battery">
      </td>
      <td>
        <strong>3S LiPo Battery</strong><br>
        <font color="#8b949e">11.1 V · 2200 mAh · 25C</font>
      </td>
      <td>The vehicle's sole power source — a 3-cell lithium-polymer pack storing 24.42 Wh. 3S (11.1 V) was chosen over 2S (7.4 V) specifically to absorb the ~2 V forward drop across the L298N's internal Darlington transistors without starving the motor of voltage (see Section 5.5), and 2200 mAh was chosen over larger capacities purely to stay under the competition's 1500 g weight limit.</td>
    </tr>
    <!-- Row 11: Buck Converters -->
    <tr>
      <td align="center" valign="middle">
        <img src="DOCS/FINAL_COMPONENTS%20USED/Buck%20Converters%20A%20&%20B.png" width="100" alt="Buck Converters">
      </td>
      <td>
        <strong>Buck Converters A & B</strong><br>
        <font color="#8b949e">5 V/3 A (logic) · 6 V/3 A (servo)</font>
      </td>
      <td>Two independent switching step-down regulators isolate the electrically noisy motor/servo loads from the sensitive compute hardware. Buck A supplies a clean, dedicated 5 V "Logic Plane" to the Raspberry Pi and ESP32-S3; Buck B supplies a separate 6 V "Actuator Plane" exclusively to the MG995 servo. Splitting these rails eliminated the inductive voltage transients that were previously triggering Raspberry Pi under-voltage brownouts when the servo shared the Pi's own 5 V supply.</td>
    </tr>
    <!-- Row 12: 10A Blade Fuse -->
    <tr>
      <td align="center" valign="middle">
        <img src="DOCS/FINAL_COMPONENTS%20USED/10A%20Blade%20Fuse.png" width="100" alt="10A Blade Fuse">
      </td>
      <td>
        <strong>10A Blade Fuse</strong><br>
        <font color="#8b949e">Automotive ATO standard</font>
      </td>
      <td>A resettable-holder automotive-grade fuse placed directly after the battery's positive terminal, ahead of the master toggle switch. It protects the entire electrical system — battery, converters, driver, and both compute boards — against a short circuit or driver fault, sized to trip safely above the 3.85 A peak system draw but well below the battery's damage threshold.</td>
    </tr>
  </tbody>
</table>

### 5.7 Wiring & Power Schematic Diagram

The diagram below traces every electrical connection on the vehicle — from the 11.1 V 3S LiPo pack, through the blade fuse and master switch, down to the two isolated power planes (Logic and Actuator) and the common Star Ground Hub. It mirrors the power-distribution tree described in [Section 5.4](#54-power-architecture) and the pin-level detail in [`docs/wiring/WIRING.md`](docs/wiring/WIRING.md).

<p align="center">
<img src="./schemes/wiring_schematic.png" alt="Full electrical wiring and power distribution schematic" width="720"/>
</p>

**Reading the diagram:**
- **Power path (left/top):** Battery → 10A blade fuse → master toggle switch → split to Buck A (5 V logic), Buck B (6 V servo), and the L298N's raw 12 V motor input.
- **Logic Plane (isolated):** Buck A feeds the Raspberry Pi 4B and ESP32-S3 5 V inputs; the Pi's onboard 3.3 V rail in turn powers the three ToF sensors, the MPU6050, and the Pi Camera v2 over CSI.
- **Actuator Plane (isolated):** Buck B powers the MG995 servo VCC exclusively, while the L298N draws its motor current straight from the fused battery rail — keeping high-current switching noise off the logic supply entirely.
- **Signal path:** ESP32-S3 GPIOs 18–21 carry PWM/direction signals to the servo and to the L298N's `ENA`/`IN1`/`IN2` pins.
- **Star Ground Hub:** every plane — logic, actuator, and motor — returns to a single common ground point, preventing ground-loop noise between the sensitive I²C/camera lines and the high-current motor/servo lines.

---

## 6. Obstacle Management — Software & Control

### 6.1 Perception
- **Color-based pillar detection (OpenCV):** HSV thresholding identifies red and green pillars in the camera frame; the robot passes red pillars on the right and green pillars on the left.
- **Magenta parking-block detection:** a dedicated HSV mask locates the parking-lot marker for the precision-parking maneuver at the end of each run.
- **ToF wall-following:** the left/right VL53L0X sensors maintain a target offset from the inner wall; the front VL53L1X sensor triggers corner/obstacle response.
- **IMU heading correction:** the MPU6050 supplies yaw-rate data used to correct for drift between vision updates and to execute clean, repeatable turns.

### 6.2 Software Architecture & Control Algorithms

The vehicle operates on an **11-layer asynchronous software pipeline** executing on the Raspberry Pi 4B at a deterministic **100 Hz (10 ms period)**, communicating with the ESP32-S3 motor controller via a **10-byte binary packet with CRC-8 checksum**.

```mermaid
graph TD
    subgraph High_Level ["Raspberry Pi 4B (100 Hz Main Execution Thread)"]
        L1["Layer 1: Sensor Acquisition (VL53L1X/L0X + MPU6050 Async I2C)"]
        L3["Layer 3: 6-DoF UKF State Estimation (x, y, θ, v, ω, b_gyro)"]
        L4["Layer 4: Perception Pipeline (OpenCV HSV Segmentation)"]
        L6["Layer 6: Mission Manager FSM (IDLE→RACING→PARKING→DONE)"]
        L7["Layer 7: Path Planner (Cubic Bezier Corridor Generation)"]
        L8["Layer 8: Trajectory Optimizer (Curvature Speed Profiling)"]
        L10["Layer 10: Stanley Controller + Speed PID + CRC8 Serial TX"]
    end
    subgraph Low_Level ["ESP32-S3 Microcontroller (Real-Time Actuation)"]
        ESP["Hardware LEDC PWM Generator → MG995 Servo & L298N Motor Driver"]
    end
    L1 --> L3
    L4 --> L6
    L3 --> L6
    L6 --> L7
    L7 --> L8
    L8 --> L10
    L10 -->|"10-Byte CRC8 Packet @ 115,200 Baud"| ESP
```

**Pipeline summary:**

| Layer | Function |
|---|---|
| Layer 1 | Sensor Acquisition — async I²C polling of VL53L1X/VL53L0X + MPU6050 |
| Layer 3 | 6-DoF Unscented Kalman Filter (UKF) state estimation: x, y, θ, v, ω, gyro bias (b<sub>gyro</sub>) |
| Layer 4 | Perception Pipeline — OpenCV HSV color segmentation (pillars + parking marker) |
| Layer 6 | Mission Manager Finite State Machine: IDLE → RACING → PARKING → DONE |
| Layer 7 | Path Planner — cubic Bézier corridor generation |
| Layer 8 | Trajectory Optimizer — curvature-based speed profiling |
| Layer 10 | Stanley Controller + Speed PID, output framed as a CRC-8 serial packet |
| ESP32-S3 | Hardware LEDC PWM generation driving the MG995 servo and L298N motor driver |

### 6.3 Control Loop
- **Control loop rate:** 100 Hz on the ESP32-S3 (5× the ~10 Hz mechanical bandwidth of the servo/motor).
- **Serial link:** 115,200 baud, <9% UART utilization at the 100 Hz packet rate — comfortable headroom for retries/CRC handling.

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
| Total Drive Reduction Ratio | 40:1 | 20:1 planetary gearbox × 2:1 bevel differential |
| Wheel Rotational Speed | 150 RPM (2.5 rev/s) | Motor output shaft (300 RPM) ÷ 2:1 differential ratio |
| Maximum Vehicle Linear Velocity | ≈0.51 m/s | N<sub>wheel</sub> × π × wheel diameter (65 mm) |
| Total Drive Axle Torque | 1.70 Nm (17.33 kg·cm) | Motor stall torque (0.85 Nm) × 2:1 differential |
| Total Tractive Force | 52.31 N | Axle torque ÷ wheel radius (32.5 mm) |
| Torque Safety Margin | 4.39× | Tractive force (52.31 N) ÷ vehicle weight (11.92 N) |
| Control Loop Rate | 100 Hz | 5× Nyquist margin over 10 Hz actuator bandwidth |
| Serial Baud Rate | 115,200 | <9% UART utilization at 100 Hz packet rate |
| Chassis Material | PETG, 30% gyroid infill | Isotropic stiffness, T<sub>g</sub> 80 °C heat resistance |
| Drive Motor | Johnson-type DC, 300 RPM | Balances top speed against torque needed for rapid heading corrections |
| Measured Turning Angle | 35°–40° | Bench-measured, matches ±35° design spec |
| Battery Pack | 3S 11.1V, 2200 mAh LiPo (24.42 Wh) | 180 g pack keeps total vehicle mass under 1500 g rule limit |
| Estimated Runtime | ~38 minutes | Continuous racing load at 1.85 A average draw (185+ laps/charge) |

<!-- Optional additions: total vehicle mass, ground clearance, wheel diameter/type, gear ratio, battery weight -->

---

## 9. Component & Power Distribution Table

| Component | File | Power Rail | Interface | Official Datasheet |
|---|---|---|---|---|
| Raspberry Pi 4 Model B | [`raspberry_pi_4b.md`](docs/components/raspberry_pi_4b.md) | 5V rail (Buck A) | GPIO, I2C1, UART | [PDF](#) |
| ESP32-S3 | [`esp32_s3.md`](docs/components/esp32_s3.md) | 5V rail (Buck A) | UART, PWM | [PDF](#) |
| L298N driver module | [`l298n.md`](docs/components/l298n.md) | Motor rail 11.1V | ENA / IN1 / IN2 | [PDF](#) |
| MG995 steering servo | [`mg995.md`](docs/components/mg995.md) | 6V rail (Buck B) | 50 Hz PWM | [PDF](#) |
| MPU6050 IMU | [`mpu6050.md`](docs/components/mpu6050.md) | Pi 3.3V | I2C | [PDF](#) |
| VL53L0X ToF (left/right) | [`vl53l0x.md`](docs/components/vl53l0x.md) | Pi 3.3V | I2C | [PDF](#) |
| VL53L1X ToF (front) | [`vl53l1x.md`](docs/components/vl53l1x.md) | Pi 3.3V | I2C | [PDF](#) |
| Drive motor (rear axle) | [`drive_motor.md`](docs/components/drive_motor.md) | Motor rail (via L298N) | PWM DC | none — bench measured |
| LiPo 3S battery | [`lipo_battery.md`](docs/components/lipo_battery.md) | Source (11.1V) | XT60 | none — manufacturer data |

*All power rails are defined in [`docs/power/POWER_DISTRIBUTION.md`](docs/power/POWER_DISTRIBUTION.md); pin connections are in [`docs/wiring/WIRING.md`](docs/wiring/WIRING.md).*

<!-- Replace the # placeholder datasheet links with real manufacturer PDF URLs. -->

---
## 10. Vehicle Photos and Team photos
### 👥 Meet Team BYTE RIDERS

<p align="center">
  <img src="./t-photos/teampic--1.png" alt="Team BYTE RIDERS - Photo 1" width="350">
  &nbsp;&nbsp;
  <img src="./t-photos/teampic--2.png" alt="Team BYTE RIDERS - Photo 2" width="350">
</p>

<p align="center">
  <b>Team BYTE RIDERS</b><br>
  <i>Designing, building, and programming an autonomous robot for the WRO 2026 Future Engineers Category.</i>
</p>
<p align="center">
  <b>BYTE RIDERS Autonomous Robot</b><br>
  <i>WRO 2026 – Future Engineers Category</i>
</p>

<table align="center">

<tr>
<td align="center">
<img src="./ROBOT-PHOTOS/r-photos/back--r-1.png" width="300" alt="Robot Rear View 1"><br><br>
<b>Rear View</b><br>
<sub>Rear view of the autonomous robot and drivetrain assembly.</sub>
</td>

<td align="center">
<img src="./ROBOT-PHOTOS/r-photos/back--r-2.png" width="300" alt="Robot Rear View 2"><br><br>
<b>Rear Electronics View</b><br>
<sub>Detailed view of the robot's rear structure and electronics.</sub>
</td>
</tr>

<tr>
<td align="center">
<img src="./ROBOT-PHOTOS/r-photos/bottom-r-1.png" width="300" alt="Robot Bottom View"><br><br>
<b>Bottom View</b><br>
<sub>Bottom view showing the chassis and mechanical configuration.</sub>
</td>

<td align="center">
<img src="./ROBOT-PHOTOS/r-photos/top-r-1.png" width="300" alt="Robot Top View"><br><br>
<b>Top View</b><br>
<sub>Top view showing the component and electronics arrangement.</sub>
</td>
</tr>

<tr>
<td align="center">
<img src="./ROBOT-PHOTOS/r-photos/side-r-1.png" width="300" alt="Robot Side View 1"><br><br>
<b>Side View</b><br>
<sub>Side profile of the BYTE RIDERS autonomous robot.</sub>
</td>

<td align="center">
<img src="./ROBOT-PHOTOS/r-photos/side-r-2.png" width="300" alt="Robot Side View 2"><br><br>
<b>Side View – Opposite Angle</b><br>
<sub>Detailed view of the robot's mechanical and steering structure.</sub>
</td>
</tr>

</table>

<p align="center">
  <b>BYTE RIDERS</b> 🤖<br>
  <i>Designed and developed for the World Robot Olympiad 2026 – Future Engineers Category.</i>
</p>
<!-- Full checklist: 6 vehicle angles, team photo, individual member photos, wiring bay close-up,
     4WS steering close-up, sensor mounting close-up, CAD renders, wiring schematic scan. -->

---

## 11. Video Demonstrations

Full details and links live in [`video/video.md`](https://youtu.be/L5KGnchQRr0?si=QbbOCd11ulyS-JgA).

---

## 12. How to Reproduce This Robot

### Mechanical
1. Print/source the chassis parts from `models/` (PETG, 30% gyroid infill recommended, see [Section 8](#8-engineering-specifications)).
2. Assemble the 4-wheel Ackermann steering linkage per the CAD assembly drawing in `models/`.
3. Print and assemble the differential gear set (`models/DIFFERENTIAL_GEAR/`: 10T bevel pinion + 20T bevel ring gear) per the kinematic derivation in [Section 4.2](#42-drivetrain--differential-gear-kinematic-derivation).
4. Mount the Johnson 300 RPM drive motor and confirm the measured steering range (35°–40°) matches spec before proceeding.

### Electronics
1. Wire all components exactly as documented in [`docs/wiring/WIRING.md`](docs/wiring/WIRING.md) and the [power table above](#9-component--power-distribution-table).
2. Set I²C addresses for the three ToF sensors (`0x30` / `0x31` / `0x32`, set via `XSHUT` sequencing at boot) and the MPU6050 (`0x68`).
3. Confirm both buck converters output 5V (Logic Plane) and 6V (Actuator Plane) independently before connecting the Pi/ESP32 and servo.

### Software
1. Flash the ESP32-S3 with the firmware in `src/`.
2. Set up the Raspberry Pi 4B with the required dependencies.
3. Run the calibration routine to tune HSV thresholds for competition lighting.
4. Launch the main control script for the desired challenge (`src/open_challenge/` or `src/obstacle_challenge/`).

<!-- Fill in exact file paths and commands (e.g. python3 src/open_challenge/main.py) so another team can follow this with zero guessing.
     Consider adding a requirements.txt and/or platformio.ini at the repo root. -->

---

## 13. Bill of Materials (BOM)

| Category | Component Description | Part / Model Number | Qty | Approx Cost (USD) | Primary Vendor |
|---|---|---|---|---|---|
| Compute | Raspberry Pi 4B (4 GB RAM) | RPI4-MODBP-4GB | 1 | $55.00 | Adafruit / Mouser |
| Controller | ESP32-S3 DevKit C | ESP32-S3-DevKitC-1 | 1 | $8.00 | Mouser / DigiKey |
| Vision | Raspberry Pi Camera v2 | RPI-CAM-V2 (IMX219) | 1 | $25.00 | SparkFun |
| Sensing | Front Distance ToF Sensor | VL53L1X (I2C 0x30) | 1 | $7.50 | Pololu / Adafruit |
| Sensing | Side Distance ToF Sensors | VL53L0X (I2C 0x31/0x32) | 2 | $10.00 | Pololu / Adafruit |
| Sensing | 6-DoF Inertial Measurement Unit | MPU6050 (I2C 0x68) | 1 | $4.50 | Amazon / HandsonTEC |
| Actuator | Metal Gear Steering Servo | MG995 (11 kg·cm) | 1 | $12.00 | TowerPro |
| Drive | 20:1 Planetary DC Gear Motor | Johnson 300 RPM 12V | 1 | $18.00 | Pololu |
| Diff Gear | Differential Bevel Gear Assembly | `models/DIFFERENTIAL_GEAR` | 1 | $3.50 | Custom 3D Print |
| Driver | Dual H-Bridge Motor Driver | L298N Module (2A) | 1 | $5.00 | HandsonTEC |
| Power | 3S 11.1V 2200mAh 25C LiPo Pack | Turnigy 2200mAh 3S | 1 | $22.00 | HobbyKing |
| Power | Step-Down Buck Converter (5V/3A) | LM2596 / MP1584 | 1 | $3.00 | Amazon |
| Power | Step-Down Buck Converter (6V/3A) | LM2596 / MP1584 | 1 | $3.00 | Amazon |
| Protection | Automotive ATO Blade Fuse Hub | 10A Blade Fuse + Holder | 1 | $2.50 | AutoZone |
| Chassis | PETG Filament & Fasteners | PETG 1.75mm + M3 Hardware | 1 | $15.00 | Prusa / McMaster |
| **TOTAL** | **Complete System Cost** | — | — | **≈$188.00** | — |

---

## 14. WRO 2026 Surprise Rules Readiness

> **Why this section matters.** In the WRO Future Engineers category, a **surprise rule** is a modification to the challenge that is revealed only on competition day, after teams have already arrived with a finished robot. Teams then get a short window to adapt. A robot whose behaviour is **hard-coded** must be re-programmed, re-compiled and re-flashed under time pressure — the single most common way a well-built robot loses a round. Byte Riders therefore treats surprise-rule adaptability as a **first-class design requirement**, on the same level as steering geometry or power budgeting, rather than as an afterthought.

### 14.1 Design Principle — Behaviour Is Data, Not Code

Every rule-dependent behaviour on the vehicle is expressed as a **parameter that is read at runtime**, never as a hard-coded constant buried inside the control logic. All of these parameters live in a single file:

```
config/robot_config.json
```

The consequences of this are deliberate and specific:

- **No source edits.** The competition-day change is a value in a JSON file, not a line of Python or C++.
- **No recompilation, no re-flash.** The ESP32-S3 firmware is a *dumb, deterministic actuator* — it only ever receives steering angle and speed. Every rule-level decision is made upstream on the Raspberry Pi, so **no surprise rule can ever require re-flashing the microcontroller.** This is the single most important architectural property for surprise-rule readiness.
- **One file, one source of truth.** There is no second place where a rule constant could be hiding and silently disagree with the config.
- **Reversible.** A wrong guess under pressure is undone by changing one value back, not by hunting through a diff.

### 14.2 Surprise-Rule Parameter Map

All surprise-rule parameters can be set in `config/robot_config.json` in **under 30 seconds** on competition day:

| # | Surprise Rule Scenario | Config Key | Type | Default Value | Competition Override | Software Layer Affected |
|:--:|---|---|---|---|---|---|
| 1 | Pillar Sign Color Swap | `SIGN_LOGIC` | string | `"NORMAL"` | `"REVERSED"` | Layer 4 (Perception) → Layer 7 (Path Planner) |
| 2 | Mandatory Driving Direction | `DRIVING_DIRECTION` | string | `"CCW"` | `"CW"` | Layer 6 (Mission FSM) → Layer 7 |
| 3 | Narrow Track Corridor (500 mm) | `NARROW_TRACK_MODE` | bool | `false` | `true` | Layer 7 (Corridor width) → Layer 8 (Speed profile) |
| 4 | Stop-and-Go Rule Active | `STOP_AND_GO_ENABLED` | bool | `true` | `false` | Layer 6 (Mission FSM) |
| 5 | Stop Duration Threshold | `STOP_DURATION_SEC` | float | `3.0` | *any float* | Layer 6 (Mission FSM) |
| 6 | Random Parking Side Swap | `PARKING_REVERSAL` | bool | `false` | `true` | Layer 6 → Layer 7 (Parking maneuver) |

### 14.3 How Each Scenario Is Actually Handled

Listing config keys is not the same as being ready. Below is what each override *physically changes in the vehicle's behaviour.*

**1. Pillar Sign Color Swap — `SIGN_LOGIC`**
The default rule is *pass red pillars on the right, green pillars on the left.* If the rule is inverted on the day, the perception layer's classification is unchanged — the camera still reports "red" or "green" exactly as before. Only the **mapping from colour to avoidance side** is flipped, at the single point where Layer 4 hands the detected pillar to Layer 7. Because the HSV thresholds themselves are untouched, **a colour swap requires no re-calibration of the vision pipeline** — a critical property, since re-tuning HSV under unfamiliar venue lighting is exactly what teams do not have time for.

**2. Mandatory Driving Direction — `DRIVING_DIRECTION`**
Switching between counter-clockwise and clockwise laps mirrors the entire navigation frame. This inverts (a) the sign convention of the IMU yaw target used for corner detection in Layer 3/6, (b) which of the two VL53L0X side sensors is treated as the *inner wall* reference for wall-following, and (c) the sign of the lateral offset term fed to the Stanley controller in Layer 10. All three follow from the one key — there is no possibility of setting the direction "half way".

**3. Narrow Track Corridor — `NARROW_TRACK_MODE`**
A narrowed corridor is not merely a geometry change; it is a **speed problem**. Enabling this mode narrows the Bézier corridor half-width generated by Layer 7 *and* tightens the curvature-based speed ceiling in Layer 8, so the vehicle automatically slows into the sections it can no longer take at full speed. It also reduces the wall-following target offset used by the side ToF sensors. Handling corridor width without also handling speed would simply convert a clearance failure into a wall strike.

**4 & 5. Stop-and-Go — `STOP_AND_GO_ENABLED`, `STOP_DURATION_SEC`**
The Mission Manager FSM (Layer 6) carries a dedicated stop state. `STOP_AND_GO_ENABLED` controls whether that state is entered at all; `STOP_DURATION_SEC` controls the dwell time before the FSM releases back to `RACING`. The duration being a **free float rather than a boolean** matters: if the announced rule specifies an unusual dwell (1.5 s, 5 s), it is entered directly with no code change. During the stop the ESP32-S3 continues receiving packets at 100 Hz with a commanded speed of zero — the link never goes silent, so there is no watchdog timeout or restart transient on release.

**6. Random Parking Side Swap — `PARKING_REVERSAL`**
Mirrors the final precision-parking maneuver: the magenta parking-marker search is biased to the opposite side of the frame, and the parallel-parking Bézier path generated by Layer 7 is reflected about the vehicle's longitudinal axis. Steering limits and the reverse-motion sequencing are unchanged, so the maneuver's tuning carries over intact to the mirrored side.

### 14.4 Example `config/robot_config.json`

```jsonc
{
  "SIGN_LOGIC":          "NORMAL",   // "NORMAL" | "REVERSED"
  "DRIVING_DIRECTION":   "CCW",      // "CCW"    | "CW"
  "NARROW_TRACK_MODE":   false,      // true → narrower corridor + lower speed ceiling
  "STOP_AND_GO_ENABLED": true,       // false → FSM skips the stop state entirely
  "STOP_DURATION_SEC":   3.0,        // dwell time in seconds (any float)
  "PARKING_REVERSAL":    false       // true → mirror the parking maneuver
}
```

The config is **validated at start-up**: unknown keys, out-of-range values and type mismatches are rejected before the motors are ever enabled, and the vehicle refuses to start rather than running with a silently-ignored setting. The full active configuration is echoed to the console on boot, so the operator can visually confirm the overrides took effect **before** placing the robot on the mat.

### 14.5 Competition-Day Procedure

The adaptation is a rehearsed, written procedure — not improvisation:

| Step | Action | Owner | Target Time |
|:--:|---|---|:--:|
| 1 | Rule announced — read it aloud twice, write it down | Both | — |
| 2 | Map the rule to the affected config key(s) using the table in [14.2](#142-surprise-rule-parameter-map) | Happy Patel | 15 s |
| 3 | Edit `config/robot_config.json` and save | Happy Patel | 30 s |
| 4 | Restart the main script; read back the echoed config on the console | Happy Patel | 15 s |
| 5 | Dry-run verification of the changed behaviour off-mat | Shrut Barasara | 60 s |
| 6 | Physical check — battery voltage, wheel/steering freedom, sensor lenses clean | Shrut Barasara | 30 s |
| | **Total** | | **≈2.5 min** |

Steps 3 and 4 are the only software actions. No editor other than a text editor is required, and **no build toolchain is needed at the venue at all.**

### 14.6 Verification — Proving Readiness Instead of Claiming It

Configurability is worthless if the non-default branches have never been executed. Every override is therefore exercised as part of pre-competition testing:

- **Both values of every key are run on the practice mat**, not just the defaults — including the mirrored parking maneuver and the clockwise lap direction, which are the two least-used code paths and therefore the two most likely to hide a sign error.
- **Combination testing:** surprise rules can arrive stacked (e.g. reversed signs *and* clockwise direction *and* a narrowed corridor simultaneously). The combinations that interact — direction × sign logic, direction × parking side, narrow track × speed profile — are tested together rather than one at a time.
- **Timed drills:** the team rehearses the [14.5](#145-competition-day-procedure) procedure against a stopwatch with a randomly-drawn scenario, so the response on the day is muscle memory.
- **Known-good baseline:** a committed, tagged copy of the default config is kept in the repository so the robot can always be returned to a known-working state instantly if a change goes wrong.

### 14.7 Honest Limits — What a Config File Cannot Fix

Being genuinely prepared also means being clear about what this approach does **not** cover:

- **Physical/dimensional rule changes** (e.g. a change to permitted vehicle size or mass) cannot be solved in software. Our margins are the mitigation here: the vehicle sits 23% under the length limit and 20% under the width limit (see [Section 8](#8-engineering-specifications)), giving room to add or reposition hardware without breaching a tightened constraint.
- **A genuinely novel task element** (a manipulation or interaction the vehicle has no actuator for) is outside the config's reach. The mitigation is the Mission Manager FSM structure: a new state can be added in one place without disturbing perception, estimation or control.
- **Lighting changes at the venue** are handled by the HSV calibration routine ([Section 12](#12-how-to-reproduce-this-robot), Software step 3), not by the surprise-rule config — deliberately kept separate so that a colour-logic swap never triggers an unnecessary re-calibration, and vice versa.

---

## 15. Engineering Post-Mortem — What Went Wrong & Fixes

1. **EMI-Induced I²C Bus Hangs**
   - *Problem:* Brushed motor switching noise coupled onto the I²C SDA/SCL lines, causing `smbus2` to freeze mid-read.
   - *Fix:* Added 4.7 kΩ pull-up resistors, soldered an RC snubber across the motor terminals, and implemented GPIO `XSHUT` power-cycling logic in Layer 1.

2. **MPU6050 Gyroscope Cumulative Yaw Drift**
   - *Problem:* Sensor heating caused a steady 5°/min gyro drift, leading to corner overshooting.
   - *Fix:* Expanded the UKF state vector in Layer 3 to include a 6th state (b<sub>gyro</sub>) that continuously tracks and subtracts dynamic gyro bias.

3. **OpenCV GIL Thread Bottleneck**
   - *Problem:* High CPU load during color segmentation caused Python's Global Interpreter Lock (GIL) to delay the main control loop.
   - *Fix:* Decoupled vision processing into a dedicated thread updating an asynchronous, lock-free frame queue.

4. **Steering Linkage Mechanical Backlash**
   - *Problem:* Self-tapping M3 screws in the 3D-printed PETG bellcranks loosened over time, introducing 3° of mechanical slop.
   - *Fix:* Redesigned the bellcrank CAD files to incorporate brass heat-set M3 thread inserts, reducing backlash to <0.5°.

5. **Chassis 3D-Printing — Material & Support-Strategy Failures** ⚠️ *(open issue — actively being worked on)*

   The single largest schedule risk on the project so far has been getting a **structurally sound chassis to actually come off the printer.** Five distinct print iterations were attempted, each isolating one variable (material, infill density, or support type). None has yet produced a chassis that is both *printable* and *stiff enough*, so this item is documented as **unresolved and in progress** rather than closed.

   | # | Material | Infill Density | Support Type | Outcome |
   |:--:|---|---|---|---|
   | 1 | PETG | Low | — | ✅ Printed · ❌ **Structurally weak** |
   | 2 | PETG | High | Tree | ❌ **Print failure — chassis unusable** |
   | 3 | PLA | High | Tree | ✅ Printed · ⚠️ Material unsuitable as final part |
   | 4 | PETG | High | Tree | ❌ **Print failure — repeat of Iteration 2** |
   | 5 | PETG | High | Normal (linear) | ✅ Printed · ❌ **Structurally weak** |
   | 6 | *In progress* | *TBD* | *TBD* | 🔄 **Currently being worked on** |

   **Iteration-by-iteration breakdown:**

   - **Iteration 1 — PETG at low infill density.**
     *What we did:* Printed the first chassis in PETG at a low infill density to keep vehicle mass down and shorten print time.
     *What went wrong:* The part printed cleanly, but the resulting structure was **too weak**. With the drivetrain, servo and battery mounted, the chassis flexed under load — unacceptable for a platform where 4WS steering geometry depends on the mounting points staying rigid and coplanar.
     *Conclusion:* Low infill was the wrong trade. Stiffness, not mass, is the binding constraint.

   - **Iteration 2 — PETG at high infill density with tree supports.**
     *What we did:* Raised the infill density substantially to recover the stiffness lost in Iteration 1, and switched to **tree supports** to handle the chassis overhangs and internal cavities with less material and easier removal.
     *What went wrong:* **The print did not complete properly.** The tree supports failed to build correctly under PETG's stringing and poor bridging behaviour, and the print was compromised before the chassis geometry was finished. **The chassis could not be printed at all in this configuration.**
     *Conclusion:* Tree supports + high-density PETG is a bad combination on our printer/profile.

   - **Iteration 3 — switch to PLA.**
     *What we did:* To break the deadlock and get a physical chassis in hand for fitment checks, we changed material entirely and printed the same geometry in **PLA**, which is far more forgiving on overhangs, bridging and support adhesion.
     *What went wrong:* The part printed, but PLA is **not acceptable as the final competition material**. Its glass-transition temperature (T<sub>g</sub> ≈ 60 °C) is well below PETG's (T<sub>g</sub> ≈ 80 °C, the value the design targets in [Section 4.1](#41-steering)), and it is significantly more brittle — a real risk under repeated wall contact and the shock loading of a crash during a run.
     *Conclusion:* Useful as a **fit-check / mock-up part only**, not as the flight chassis.

   - **Iteration 4 — return to PETG.**
     *What we did:* With the geometry validated on the PLA print, we went back to **PETG** to produce the real part.
     *What went wrong:* **The print was again unsuccessful**, reproducing the Iteration 2 failure mode. This confirmed the problem was not a one-off printer glitch but a repeatable interaction between PETG and the support strategy.
     *Conclusion:* The variable to change was the **support type**, not the material.

   - **Iteration 5 — PETG with normal (linear) supports instead of tree supports.**
     *What we did:* Kept PETG, kept the higher infill, and replaced tree supports with **conventional normal/linear supports**, which contact the part over a much larger, more predictable footprint.
     *What went wrong:* The print **completed** — a clear improvement over Iterations 2 and 4 — **but the resulting chassis came out weak.** Support removal left poor surface quality on the down-facing structural faces, and layer adhesion in the supported regions was visibly inferior, so the part did not reach the rigidity the 4WS geometry needs.
     *Conclusion:* Printability solved; **strength still not solved.**

   **Current status — Iteration 6 (in progress):**
   The chassis is **the active work item on the mechanical side right now.** Rather than continuing to tune slicer settings on the existing geometry, the current effort is focused on attacking the problem from both the CAD and the process side simultaneously:

   - **Reduce the need for supports in the first place** — revising the CAD so that overhangs stay within the self-supporting angle (≈45°), converting horizontal holes to teardrop/chamfered profiles, and splitting the chassis into two or more separately-printed sections that each sit flat on the bed and are joined mechanically at a non-critical seam.
   - **Print-orientation study** — reorienting the part so the primary bending and torsional loads run *along* layer lines rather than *across* them, since layer adhesion (Z-direction strength) is where every weak print so far has failed.
   - **Wall count over infill density** — increasing perimeter/wall count rather than infill percentage, which contributes far more to bending stiffness per gram than raising infill alone.
   - **PETG process control** — drying the filament before printing, raising nozzle temperature and lowering print speed to improve interlayer bonding, and enabling an enclosure/draft shield to slow cooling.
   - **Stiffness verification before assembly** — each candidate chassis will be checked with a simple three-point deflection test at the motor and servo mount points, and only a part that passes will be committed to as the final build.

   *This entry will be updated with the final material, infill, wall count, orientation and support configuration once a chassis passes the deflection check. Until then, the PETG / 30% gyroid figure quoted in [Section 4.1](#41-steering) and [Section 8](#8-engineering-specifications) should be read as the **design target**, not as an as-built, validated result.*

---

## 16. References & Acknowledgments

- **OpenCV Computer Vision Library:** [https://opencv.org](https://opencv.org)
- **FilterPy Kalman Filtering Library:** Labbe, R. *"Kalman and Bayesian Filters in Python"*, 2018.
- **ESP32Servo Library:** Harrington, K. *ESP32 Hardware Timer Servo Control*.
- **Stanley Steering Control Literature:** Thrun, S., et al. *"Stanley: The Robot that Won the DARPA Grand Challenge"*, Journal of Field Robotics, 2006.
- **World Robot Olympiad (WRO):** Official WRO Future Engineers 2026 Competition Rulebook and Track Specifications.
- World Robot Olympiad Association & WRO India — competition rules and guidelines.

<!-- Add any additional open-source libraries/tutorials/prior-year repositories that informed this design. -->

---

<div align="center">

**Built by Team Byte Riders 🚗⚡**
*WRO 2026 Future Engineers*

</div>
