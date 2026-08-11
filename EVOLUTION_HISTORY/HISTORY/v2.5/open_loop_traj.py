import serial, time
ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
def cmd(deg, spd):
    s = int(deg * 100); v = int(spd * 10)
    pkt = bytes([0xAA, 0x55, 0, 0x01, s >> 8 & 0xFF, s & 0xFF, v >> 8 & 0xFF, v & 0xFF, 0, 0x0D])
    ser.write(pkt)
plan = [(0, 35, 2.0), (15, 25, 1.2), (0, 35, 2.0), (-15, 25, 1.2)]
t0 = time.time()
for i, (deg, spd, dur) in enumerate(plan):
    while time.time() - t0 < sum(p[2] for p in plan[:i]):
        pass
    cmd(deg, spd)
    while time.time() - t0 < sum(p[2] for p in plan[:i + 1]):
        time.sleep(0.01)
cmd(0, 0)