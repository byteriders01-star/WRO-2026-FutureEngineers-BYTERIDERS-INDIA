import serial, time, sys, tty, termios
ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
def cmd(deg, spd):
    s = int(deg * 100); v = int(spd * 10)
    pkt = bytes([0xAA, 0x55, 0, 0x01, s >> 8 & 0xFF, s & 0xFF, v >> 8 & 0xFF, v & 0xFF, 0, 0x0D])
    ser.write(pkt)
old = termios.tcgetattr(sys.stdin)
tty.setcbreak(sys.stdin)
try:
    while True:
        ch = sys.stdin.read(1)
        if ch == "w": cmd(0, 60)
        elif ch == "s": cmd(0, -40)
        elif ch == "a": cmd(25, 30)
        elif ch == "d": cmd(-25, 30)
        elif ch == "q": break
        else: cmd(0, 0)
finally:
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
cmd(0, 0)