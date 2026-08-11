import serial, time
ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.1)
seq = 0
for _ in range(20):
    ser.reset_input_buffer()
    ser.write(bytes([0xAA, 0x55, seq, 0x03, 0,0, 0,0, 0x5A, 0x0D]))
    echo = ser.read(10)
    ok = len(echo) == 10 and echo[8] == 0x5A
    print("ping", seq, "OK" if ok else "FAIL")
    seq = (seq + 1) & 0xFF
    time.sleep(0.05)