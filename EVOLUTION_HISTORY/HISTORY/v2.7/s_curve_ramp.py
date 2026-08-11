import serial, time, math
ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
def cmd(spd):
    v = int(spd * 10)
    pkt = bytes([0xAA, 0x55, 0, 0x01, 0, 0, v >> 8 & 0xFF, v & 0xFF, 0, 0x0D])
    ser.write(pkt)
T = 0.5
t0 = time.time()
while time.time() - t0 < T:
    frac = (time.time() - t0) / T
    cmd(100 * math.sin(math.pi / 2 * frac))
    time.sleep(0.01)
cmd(100)