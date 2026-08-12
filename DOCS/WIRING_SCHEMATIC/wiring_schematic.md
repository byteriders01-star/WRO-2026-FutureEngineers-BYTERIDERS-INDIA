# WRO_4WS_Pro_2026 — Complete System Wiring & Pin Connection Schematic

> **Authentic Hardware Schematic & Pin Mapping**  
> **Platform:** Raspberry Pi 4B (High-Level Compute) + ESP32-S3 DevKit (Real-Time Control)  
> **Power System:** 3S 11.1V LiPo Pack + Dual Isolated Buck Converters (5V/3A & 6V/3A) + 10A Automotive Blade Fuse

---

## ⚡ 1. Power Distribution Network (PDN) Schematic

```
                  ┌─────────────────────────────────────────────────┐
                  │   11.1V 3S LiPo Battery Pack (2200 mAh 25C)    │
                  └────────────────────────┬────────────────────────┘
                                           │ (+) Positive Terminal
                                10A Automotive Blade Fuse
                                           │
                             SPST Main Mechanical Toggle Switch
                                           │
       ┌───────────────────────────────────┼───────────────────────────────────┐
       │ (+11.1V Fused)                    │ (+11.1V Fused)                    │ (+11.1V Direct Fused)
       ▼                                   ▼                                   ▼
┌───────────────┐                   ┌───────────────┐                   ┌───────────────┐
│ Buck A (5V/3A)│                   │ Buck B (6V/3A)│                   │ L298N VMS IN  │
│(LM2596/MP1584)│                   │(LM2596/MP1584)│                   │ (Motor Power) │
└───────┬───────┘                   └───────┬───────┘                   └───────┬───────┘
        │ (+5.0V Logic Rail)                │ (+6.0V Servo Rail)                │ (High Current)
        ├───────────────────┐               │                                   │
        ▼                   ▼               ▼                                   ▼
┌───────────────┐   ┌───────────────┐┌───────────────┐                   ┌───────────────┐
│Raspberry Pi 4B│   │ ESP32-S3      ││ MG995 Servo   │                   │ Johnson Motor │
│ (5V Pin 2/4)  │   │  (5V VIN Pin) ││ (VCC Red Wire)│                   │ (OUT1 & OUT2) │
└───────┬───────┘   └───────┬───────┘└───────┬───────┘                   └───────┬───────┘
        │                   │                │                                   │
        │ (3.3V Output)     │                │                                   │
        ▼                   │                │                                   │
┌───────────────┐           │                │                                   │
│ I2C Sensors   │           │                │                                   │
│(VL53/MPU6050) │           │                │                                   │
└───────┬───────┘           │                │                                   │
        │                   │                │                                   │
        ▼                   ▼                ▼                                   ▼
=========================================================================================
                 CENTRAL COPPER STAR GROUND HUB (Single Battery (-) Point)
=========================================================================================
```

---

## 📌 2. Detailed Subsystem Block-by-Block Pin Connection Map

### A. Raspberry Pi 4B (Compute Core)
| Pi Pin Name | Physical Pin | Direction / Logic | Signal Function | Connected Component & Pin |
|---|---|---|---|---|
| **5V_IN** | Pin 2 / Pin 4 | POWER IN (+5.0V) | Main Compute Logic Power | Buck A Output (+5.0V Rail) |
| **GND** | Pin 6 / Pin 14 | GROUND (0V) | Common Logic Ground | Central Copper Star Ground Hub |
| **GPIO 2** | Pin 3 | BIDIRECTIONAL (3.3V) | I2C SDA (Data Line) | Shared SDA (VL53L1X, 2x VL53L0X, MPU6050) |
| **GPIO 3** | Pin 5 | OUTPUT (3.3V) | I2C SCL (Clock Line) | Shared SCL (VL53L1X, 2x VL53L0X, MPU6050) |
| **GPIO 22** | Pin 15 | OUTPUT (3.3V) | XSHUT Front ToF | VL53L1X Front XSHUT Pin (Addr `0x30`) |
| **GPIO 17** | Pin 11 | OUTPUT (3.3V) | XSHUT Left ToF | VL53L0X Left XSHUT Pin (Addr `0x31`) |
| **GPIO 27** | Pin 13 | OUTPUT (3.3V) | XSHUT Right ToF | VL53L0X Right XSHUT Pin (Addr `0x32`) |
| **GPIO 16** | Pin 36 | INPUT (Active-LOW) | Start Push-Button | Momentary Switch $\rightarrow$ GND (Pin 34) |
| **GPIO 5** | Pin 29 | OUTPUT (3.3V) | Status LED 1 | Green LED (+220$\Omega$ resistor to GND) — System ON |
| **GPIO 6** | Pin 31 | OUTPUT (3.3V) | Status LED 2 | Green LED (+220$\Omega$ resistor to GND) — Sensors OK |
| **GPIO 13** | Pin 33 | OUTPUT (3.3V) | Status LED 3 | Green LED (+220$\Omega$ resistor to GND) — Camera OK |
| **GPIO 19** | Pin 35 | OUTPUT (3.3V) | Status LED 4 | Green LED (+220$\Omega$ resistor to GND) — Serial OK |
| **GPIO 26** | Pin 37 | OUTPUT (3.3V) | Status LED 5 | Red/Green LED (+220$\Omega$ to GND) — Race Active |
| **CSI Port** | Ribbon Header | HIGH-SPEED DIFFERENTIAL| Camera CSI Interface | Raspberry Pi Camera v2 (Sony IMX219) |
| **USB Port**| Type-A Host | USB SERIAL (115200 Baud)| High-Level Comm Link| ESP32-S3 Micro-USB Port |

---

### B. ESP32-S3 DevKit (Real-Time Motor Controller)
| ESP32 Pin | Logic Level | Direction | Signal Function | Connected Component & Pin |
|---|---|---|---|---|
| **5V (VIN)** | +5.0V | POWER IN | Microcontroller Power | Buck A Output (+5.0V Rail) |
| **GND** | 0V | GROUND | Common Logic Ground | Central Copper Star Ground Hub |
| **GPIO 1 (ADC1_CH0)**| 0 - 3.3V Analog| INPUT | Battery Voltage Sensing | $10\text{k}\Omega / 3.3\text{k}\Omega$ Divider across +11.1V Battery |
| **GPIO 18** | 3.3V PWM (50Hz)| OUTPUT | Steering Servo Signal | MG995 Servo Signal Wire (Yellow/Orange) |
| **GPIO 19** | 3.3V PWM | OUTPUT | Motor Speed (ENA) | L298N Motor Driver ENA Pin |
| **GPIO 20** | 3.3V Digital | OUTPUT | Motor Direction IN1 | L298N Motor Driver IN1 Pin |
| **GPIO 21** | 3.3V Digital | OUTPUT | Motor Direction IN2 | L298N Motor Driver IN2 Pin |
| **GPIO 22** | 3.3V Digital | OUTPUT | Driver STBY / Enable | L298N Motor Driver STBY Pin |
| **GPIO 4** | 3.3V Digital | OUTPUT | Status LED 1 | Green LED (+220$\Omega$ to GND) — ESP32 Boot OK |
| **GPIO 5** | 3.3V Digital | OUTPUT | Status LED 2 | Green LED (+220$\Omega$ to GND) — Serial Rx OK |
| **GPIO 15** | 3.3V Digital | OUTPUT | Status LED 3 | Green LED (+220$\Omega$ to GND) — Servo Active |
| **GPIO 16** | 3.3V Digital | OUTPUT | Status LED 4 | Green LED (+220$\Omega$ to GND) — Motor Active |
| **GPIO 17** | 3.3V Digital | OUTPUT | Status LED 5 | Red LED (+220$\Omega$ to GND) — System Fault |

---

### C. Sensors Subsystem (I2C Bus & Camera)
| Sensor Board | Pin Name | Connected To | Signal Type & Address |
|---|---|---|---|
| **VL53L1X Front ToF** | VCC | Raspberry Pi 3.3V (Pin 1) | +3.3V Regulated Power |
| | GND | Central Star Ground Hub | Ground (0V) |
| | SDA | Pi GPIO 2 (Pin 3) | Shared I2C Data (Default `0x29` $\rightarrow$ Re-addressed to `0x30`) |
| | SCL | Pi GPIO 3 (Pin 5) | Shared I2C Clock (400 kHz Fast Mode) |
| | XSHUT | Pi GPIO 22 (Pin 15) | Active-HIGH Enable for dynamic address assignment |
| **VL53L0X Left ToF** | VCC | Raspberry Pi 3.3V (Pin 1) | +3.3V Regulated Power |
| | GND | Central Star Ground Hub | Ground (0V) |
| | SDA | Pi GPIO 2 (Pin 3) | Shared I2C Data (Default `0x29` $\rightarrow$ Re-addressed to `0x31`) |
| | SCL | Pi GPIO 3 (Pin 5) | Shared I2C Clock (400 kHz Fast Mode) |
| | XSHUT | Pi GPIO 17 (Pin 11) | Active-HIGH Enable for dynamic address assignment |
| **VL53L0X Right ToF**| VCC | Raspberry Pi 3.3V (Pin 1) | +3.3V Regulated Power |
| | GND | Central Star Ground Hub | Ground (0V) |
| | SDA | Pi GPIO 2 (Pin 3) | Shared I2C Data (Default `0x29` $\rightarrow$ Re-addressed to `0x32`) |
| | SCL | Pi GPIO 3 (Pin 5) | Shared I2C Clock (400 kHz Fast Mode) |
| | XSHUT | Pi GPIO 27 (Pin 13) | Active-HIGH Enable for dynamic address assignment |
| **MPU6050 6-DoF IMU** | VCC | Raspberry Pi 3.3V (Pin 1) | +3.3V Regulated Power |
| | GND | Central Star Ground Hub | Ground (0V) |
| | SDA | Pi GPIO 2 (Pin 3) | Shared I2C Data (Fixed Address `0x68`) |
| | SCL | Pi GPIO 3 (Pin 5) | Shared I2C Clock (400 kHz Fast Mode) |

*Note: $4.7\text{ k}\Omega$ metal-film pull-up resistors are connected between the 3.3V rail and the SDA/SCL lines to ensure sharp signal rise times ($<300\text{ ns}$) across the $400\text{ kHz}$ bus.*

---

### D. Actuators Subsystem (Servo & Motor Driver)

#### 1. MG995 Steering Servo
* **VCC (Red Wire):** Connected to **Buck B Output (+6.0V Rail)**. *(Never powered from 5V logic rail to prevent Pi brownouts).*
* **GND (Brown/Black Wire):** Connected to **Central Copper Star Ground Hub**.
* **Signal (Orange/Yellow Wire):** Connected to **ESP32-S3 GPIO 18** ($50\text{ Hz}$ PWM, $1000\mu\text{s} - 2000\mu\text{s}$ pulse width).

#### 2. L298N Dual H-Bridge Motor Driver
* **VMS Terminal (+12V IN):** Connected to **+11.1V Fused Battery Power**.
* **GND Terminal:** Connected to **Central Copper Star Ground Hub**.
* **5V Logic Terminal:** Connected to **+5.0V Logic Rail** (or internal jumper enabled).
* **ENA Pin:** Connected to **ESP32-S3 GPIO 19** (PWM Speed Control).
* **IN1 Pin:** Connected to **ESP32-S3 GPIO 20** (Direction Signal A).
* **IN2 Pin:** Connected to **ESP32-S3 GPIO 21** (Direction Signal B).
* **OUT1 & OUT2 Terminals:** Connected to **Johnson 300 RPM 12V DC Planetary Gear Motor** terminals.
* **RC Snubber Filter:** A $100\Omega$ metal-film resistor in series with a $0.1\mu\text{F}$ ceramic capacitor is soldered directly across OUT1 & OUT2 to eliminate motor brush switching EMI spikes.

---

## 🔍 3. Verification & Diagnostic Commands

To verify that every physical connection is functioning correctly without hardware faults:

```bash
# 1. Verify I2C Bus Addresses (0x30, 0x31, 0x32, 0x68 should appear):
i2cdetect -y 1

# 2. Run full hardware diagnostics test:
python3 test_sensors.py

# 3. Test serial packet transmission to ESP32:
python3 -c "from utils.serial_protocol import SerialProtocol; sp = SerialProtocol(); print('Encoder Test OK:', sp.encode_packet(0, 0, 60, 1, 2, 0))"
```

---
*Verified against WRO Future Engineers 2026 Hardware Rules (11.1–11.5).*
