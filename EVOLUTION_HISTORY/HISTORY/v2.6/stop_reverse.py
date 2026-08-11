import serial, time
ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
def cmd(deg, spd, mode=1):
    s = int(deg * 100); v = int(spd * 10)
    pkt = bytes([0xAA, 0x55, 0, mode, s >> 8 & 0xFF, s & 0xFF, v >> 8 & 0xFF, v & 0xFF, 0, 0x0D])
    ser.write(pkt)
cmd(0, 60); time.sleep(2.0)
cmd(0, 0, 0x02)              # EMSTOP: short brake
time.sleep(0.5)
cmd(0, -40); time.sleep(1.5) # reverse
cmd(0, 0)