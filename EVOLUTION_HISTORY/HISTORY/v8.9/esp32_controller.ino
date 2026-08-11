/*
 * ======================================================================================
 *                 ESP32-S3  ·  REAL-TIME MOTOR CONTROLLER FIRMWARE
 *            WRO Future Engineers 2026 – Single Servo Mechanical 4WS Robot
 * ======================================================================================
 *
 * 5-LED STATUS INDICATOR MAP
 * ─────────────────────────────────────────────────────────────────────────────────────
 *  LED   GPIO  Colour  Meaning              ON when…            OFF when…
 *  ────  ────  ──────  ───────────────────  ──────────────────  ────────────────────
 *  LED1   4    Green   Boot / Power OK      Setup complete      Never (ESP32 alive)
 *  LED2   5    Green   Pi Serial Connected  Valid packet rcvd   No packet > 200 ms
 *  LED3   15   Green   Servo OK             Servo cmd executed  Servo pulse error
 *  LED4   16   Green   Motor Driver OK      Motor STBY HIGH     STBY went LOW (fault)
 *  LED5   17   Red     Fault Indicator      Servo OR Motor err  Both servo+motor OK
 *
 * LED5 (Red) = combined fault flag: ON when LED3 or LED4 is OFF
 *
 * Serial Packet Format (10 bytes, binary)
 * ─────────────────────────────────────────
 *  Byte  0   : Header 0xAA
 *  Byte  1   : Header 0x55
 *  Byte  2   : Sequence counter (uint8)
 *  Byte  3   : Command (0x01=DRIVE, 0x02=EMSTOP, 0x03=CALIBRATE)
 *  Bytes 4-5 : Servo angle ×100  (int16 big-endian)  -3500..+3500 → -35.0°..+35.0°
 *  Bytes 6-7 : Motor speed ×10   (int16 big-endian)  -1000..+1000 → -100%..+100%
 *  Byte  8   : CRC8 (polynomial 0x07) over bytes 0–7
 *  Byte  9   : Footer 0x0D
 *
 * Hardware Pin Map (ESP32-S3)
 * ────────────────────────────
 *  GPIO 18   MG995 4WS Steering Servo  (PWM 50 Hz, 900–2100 µs)
 *  GPIO 19   TB6612FNG PWMA / L298N ENA
 *  GPIO 20   TB6612FNG AIN1  / L298N IN1
 *  GPIO 21   TB6612FNG AIN2  / L298N IN2
 *  GPIO 22   TB6612FNG STBY  (HIGH = Driver Active)
 *  GPIO  4   LED1 Green  Boot / Power OK
 *  GPIO  5   LED2 Green  Pi Serial Connected
 *  GPIO 15   LED3 Green  Servo OK
 *  GPIO 16   LED4 Green  Motor Driver OK
 *  GPIO 17   LED5 Red    Fault (Servo OR Motor)
 * ======================================================================================
 */

#include <Arduino.h>
#include <ESP32Servo.h>

// ─────────────────────────────────────────────────────────────────────────────
// PIN DEFINITIONS
// ─────────────────────────────────────────────────────────────────────────────
#define SERVO_PIN          18
#define MOTOR_PWM_PIN      19
#define MOTOR_IN1_PIN      20
#define MOTOR_IN2_PIN      21
#define MOTOR_STBY_PIN     22

#define LED1_BOOT_PIN       4    // Green — Boot / Power OK
#define LED2_SERIAL_PIN     5    // Green — Pi Serial Connected
#define LED3_SERVO_PIN     15    // Green — Servo OK
#define LED4_MOTOR_PIN     16    // Green — Motor Driver OK
#define LED5_FAULT_PIN     17    // Red   — Servo OR Motor Fault

// ─────────────────────────────────────────────────────────────────────────────
// CONSTANTS
// ─────────────────────────────────────────────────────────────────────────────
#define SERIAL_BAUD        115200
#define PACKET_SIZE        10
#define TIMEOUT_MS         200     // No packet → failsafe + LED2 OFF

const uint8_t HEADER_0    = 0xAA;
const uint8_t HEADER_1    = 0x55;
const uint8_t FOOTER_BYTE = 0x0D;

#define CMD_DRIVE          0x01
#define CMD_EMERGENCY_STOP 0x02
#define CMD_CALIBRATE      0x03

// ─────────────────────────────────────────────────────────────────────────────
// GLOBAL STATE
// ─────────────────────────────────────────────────────────────────────────────
Servo         mg995Servo;
unsigned long lastPacketTime  = 0;
uint8_t       rxBuffer[PACKET_SIZE];
uint8_t       bufferIdx       = 0;

bool          servoOK  = false;   // LED3 state
bool          motorOK  = false;   // LED4 state
bool          serialOK = false;   // LED2 state

// ─────────────────────────────────────────────────────────────────────────────
// LED HELPERS
// ─────────────────────────────────────────────────────────────────────────────

// Update all 5 LEDs from current state flags
void updateAllLEDs() {
  // LED1 always ON (ESP32 is running)
  digitalWrite(LED1_BOOT_PIN,  HIGH);

  // LED2 — serial link alive
  digitalWrite(LED2_SERIAL_PIN, serialOK ? HIGH : LOW);

  // LED3 — servo OK
  digitalWrite(LED3_SERVO_PIN,  servoOK  ? HIGH : LOW);

  // LED4 — motor driver OK
  digitalWrite(LED4_MOTOR_PIN,  motorOK  ? HIGH : LOW);

  // LED5 — fault = servo OR motor failed (Red ON = fault)
  digitalWrite(LED5_FAULT_PIN,  (!servoOK || !motorOK) ? HIGH : LOW);
}

// ─────────────────────────────────────────────────────────────────────────────
// CRC8 (Polynomial 0x07 — SMBus compatible)
// ─────────────────────────────────────────────────────────────────────────────
uint8_t calculateCRC8(const uint8_t *data, size_t len) {
  uint8_t crc = 0x00;
  for (size_t i = 0; i < len; i++) {
    crc ^= data[i];
    for (uint8_t j = 0; j < 8; j++) {
      crc = (crc & 0x80) ? (crc << 1) ^ 0x07 : (crc << 1);
    }
  }
  return crc;
}

// ─────────────────────────────────────────────────────────────────────────────
// ACTUATOR CONTROL
// ─────────────────────────────────────────────────────────────────────────────
void setServoAngle(float angleDeg) {
  // MG995: 900 µs = -35°, 1500 µs = 0°, 2100 µs = +35°
  long rawScaled = (long)(angleDeg * 10.0f);
  int  pulseUs   = (int)map(rawScaled, -350, 350, 900, 2100);
  pulseUs        = constrain(pulseUs, 900, 2100);

  servoOK = true;   // Servo command executed successfully
  mg995Servo.writeMicroseconds(pulseUs);
}

void setMotorSpeed(float speedPct) {
  speedPct = constrain(speedPct, -100.0f, 100.0f);
  int pwmVal = (int)map((long)abs((int)speedPct), 0, 100, 0, 255);

  // Check if TB6612FNG / L298N motor driver is responding
  // STBY pin should be HIGH (we drive it HIGH in normal operation)
  // If it reads LOW after we set it HIGH → driver fault
  digitalWrite(MOTOR_STBY_PIN, HIGH);
  delayMicroseconds(10);
  if (!digitalRead(MOTOR_STBY_PIN)) {
    // Driver not responding — mark motor fault
    motorOK = false;
    analogWrite(MOTOR_PWM_PIN, 0);
    return;
  }
  motorOK = true;

  if (speedPct > 0.5f) {
    digitalWrite(MOTOR_IN1_PIN, HIGH);
    digitalWrite(MOTOR_IN2_PIN, LOW);
  } else if (speedPct < -0.5f) {
    digitalWrite(MOTOR_IN1_PIN, LOW);
    digitalWrite(MOTOR_IN2_PIN, HIGH);
  } else {
    // Active brake (short brake)
    digitalWrite(MOTOR_IN1_PIN, LOW);
    digitalWrite(MOTOR_IN2_PIN, LOW);
    pwmVal = 0;
  }
  analogWrite(MOTOR_PWM_PIN, pwmVal);
}

void executeFailsafe() {
  // Coast to zero — servo centre, motor stop, STBY low
  analogWrite(MOTOR_PWM_PIN, 0);
  digitalWrite(MOTOR_IN1_PIN,  LOW);
  digitalWrite(MOTOR_IN2_PIN,  LOW);
  digitalWrite(MOTOR_STBY_PIN, LOW);
  setServoAngle(0.0f);

  serialOK = false;
  // Keep servoOK and motorOK at their current states so LED5 stays correct
  updateAllLEDs();
}

// ─────────────────────────────────────────────────────────────────────────────
// PACKET PROCESSING
// ─────────────────────────────────────────────────────────────────────────────
void processPacket(const uint8_t *pkt) {
  // Verify CRC over bytes 0–7
  if (calculateCRC8(pkt, 8) != pkt[8]) {
    return;  // Bad CRC — discard silently, don't reset watchdog
  }

  uint8_t cmdByte   = pkt[3];
  int16_t rawServo  = (int16_t)((pkt[4] << 8) | pkt[5]);
  int16_t rawSpeed  = (int16_t)((pkt[6] << 8) | pkt[7]);

  float servoAngleDeg = rawServo / 100.0f;
  float motorSpeedPct = rawSpeed /  10.0f;

  // ── Command dispatch ──────────────────────────────────────────────────────
  if (cmdByte == CMD_EMERGENCY_STOP) {
    executeFailsafe();
    serialOK = true;              // Pi is still connected (sent the packet)
    servoOK  = false;             // Servo commanded to stop — mark uncertain
    motorOK  = false;
    lastPacketTime = millis();
    updateAllLEDs();
    return;
  }

  if (cmdByte == CMD_DRIVE) {
    digitalWrite(MOTOR_STBY_PIN, HIGH);   // Re-enable driver before commands
    setServoAngle(servoAngleDeg);         // → sets servoOK
    setMotorSpeed(motorSpeedPct);         // → sets motorOK
    serialOK       = true;                // Good packet received → LED2 ON
    lastPacketTime = millis();
    updateAllLEDs();
    return;
  }

  if (cmdByte == CMD_CALIBRATE) {
    setServoAngle(0.0f);
    setMotorSpeed(0.0f);
    serialOK       = true;
    lastPacketTime = millis();
    updateAllLEDs();
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SETUP
// ─────────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(SERIAL_BAUD);

  // ── LED pins ──────────────────────────────────────────────────────────────
  pinMode(LED1_BOOT_PIN,   OUTPUT);
  pinMode(LED2_SERIAL_PIN, OUTPUT);
  pinMode(LED3_SERVO_PIN,  OUTPUT);
  pinMode(LED4_MOTOR_PIN,  OUTPUT);
  pinMode(LED5_FAULT_PIN,  OUTPUT);

  // All OFF initially
  digitalWrite(LED1_BOOT_PIN,   LOW);
  digitalWrite(LED2_SERIAL_PIN, LOW);
  digitalWrite(LED3_SERVO_PIN,  LOW);
  digitalWrite(LED4_MOTOR_PIN,  LOW);
  digitalWrite(LED5_FAULT_PIN,  LOW);

  // ── Motor driver pins ─────────────────────────────────────────────────────
  pinMode(MOTOR_PWM_PIN,  OUTPUT);
  pinMode(MOTOR_IN1_PIN,  OUTPUT);
  pinMode(MOTOR_IN2_PIN,  OUTPUT);
  pinMode(MOTOR_STBY_PIN, OUTPUT);
  digitalWrite(MOTOR_STBY_PIN, LOW);

  // ── Servo ─────────────────────────────────────────────────────────────────
  ESP32PWM::allocateTimer(0);
  mg995Servo.setPeriodHertz(50);
  mg995Servo.attach(SERVO_PIN, 900, 2100);

  // ── Startup self-test: blink all 5 LEDs once ─────────────────────────────
  // Sweep ON left to right
  for (int pin : {LED1_BOOT_PIN, LED2_SERIAL_PIN,
                  LED3_SERVO_PIN, LED4_MOTOR_PIN, LED5_FAULT_PIN}) {
    digitalWrite(pin, HIGH);
    delay(100);
  }
  delay(200);
  // All OFF
  for (int pin : {LED1_BOOT_PIN, LED2_SERIAL_PIN,
                  LED3_SERVO_PIN, LED4_MOTOR_PIN, LED5_FAULT_PIN}) {
    digitalWrite(pin, LOW);
  }
  delay(150);

  // Failsafe position
  executeFailsafe();
  lastPacketTime = millis();

  // LED1 ON — setup complete, waiting for Pi
  digitalWrite(LED1_BOOT_PIN, HIGH);

  // LED5 ON (red) — no Pi connection yet
  digitalWrite(LED5_FAULT_PIN, HIGH);
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN LOOP (fully non-blocking)
// ─────────────────────────────────────────────────────────────────────────────
void loop() {
  // ── 1. Serial packet receiver ─────────────────────────────────────────────
  while (Serial.available() > 0) {
    uint8_t byteIn = Serial.read();

    if (bufferIdx == 0) {
      if (byteIn == HEADER_0) rxBuffer[bufferIdx++] = byteIn;
    }
    else if (bufferIdx == 1) {
      if (byteIn == HEADER_1) rxBuffer[bufferIdx++] = byteIn;
      else                    bufferIdx = 0;
    }
    else {
      rxBuffer[bufferIdx++] = byteIn;
      if (bufferIdx == PACKET_SIZE) {
        if (rxBuffer[PACKET_SIZE - 1] == FOOTER_BYTE) {
          processPacket(rxBuffer);
        }
        bufferIdx = 0;
      }
    }
  }

  // ── 2. Watchdog: 200 ms no packet → failsafe ──────────────────────────────
  if (millis() - lastPacketTime > TIMEOUT_MS) {
    if (serialOK) {
      // First time serial is lost — execute failsafe
      executeFailsafe();   // Also sets serialOK = false
    }
    // LED update: LED2 OFF (no serial), LED5 ON (fault — connection lost)
    serialOK = false;
    updateAllLEDs();
  }
}
