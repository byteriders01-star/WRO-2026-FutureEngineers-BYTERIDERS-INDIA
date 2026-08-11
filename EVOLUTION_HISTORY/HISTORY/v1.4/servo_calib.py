import time
import serial
ser = serial.Serial("/dev/ttyUSB0", 115200)
for deg in range(-35, 36, 5):
    pkt = bytes([0xAA, 0x55, 0, 0x01, (deg*100)>>8 & 0xFF, deg*100 & 0xFF, 0, 0, 0, 0x0D])
    ser.write(pkt)
    print("deg:", deg)
    time.sleep(0.8)