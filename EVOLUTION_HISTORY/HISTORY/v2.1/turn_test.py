import serial, time
ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
def cmd(servo_deg, speed):
    s = int(servo_deg * 100); v = int(speed * 10)
    pkt = bytes([0xAA, 0x55, 0, 0x01, s >> 8 & 0xFF, s & 0xFF, v >> 8 & 0xFF, v & 0xFF, 0, 0x0D])
    ser.write(pkt)
for deg in (10, 20, 30):
    cmd(deg, 30); time.sleep(2.0)   # drive a circle
cmd(0, 0)