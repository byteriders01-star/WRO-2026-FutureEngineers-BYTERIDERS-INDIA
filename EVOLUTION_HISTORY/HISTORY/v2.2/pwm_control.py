import serial, time
ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
# speeds 0..100 -> PWM 0..255 mapped on ESP32
for spd in (0, 20, 40, 60, 80, 100):
    raw = int(spd * 10)
    pkt = bytes([0xAA, 0x55, 0, 0x01, 0, 0, raw >> 8 & 0xFF, raw & 0xFF, 0, 0x0D])
    ser.write(pkt)
    time.sleep(1.0)