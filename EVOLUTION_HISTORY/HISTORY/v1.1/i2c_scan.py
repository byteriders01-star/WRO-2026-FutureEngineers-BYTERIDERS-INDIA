import board, busio
i2c = busio.I2C(board.SCL, board.SDA)
found = []
while not i2c.try_lock():
    pass
try:
    for addr in range(0x08, 0x78):
        if i2c.probe(addr):
            found.append(hex(addr))
finally:
    i2c.unlock()
print("Found:", found, "expected 0x68 (MPU6050)")