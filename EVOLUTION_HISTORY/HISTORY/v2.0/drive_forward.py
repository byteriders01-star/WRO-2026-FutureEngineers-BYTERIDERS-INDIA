import serial, time
ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
def drive(speed):
    raw = int(max(-100, min(100, speed)) * 10)
    pkt = bytes([0xAA, 0x55, 0, 0x01, 0, 0, raw >> 8 & 0xFF, raw & 0xFF, 0, 0x0D])
    ser.write(pkt)
for i in range(0, 101, 10):
    drive(i); time.sleep(0.05)   # 500ms ramp
time.sleep(2.0)
drive(0)