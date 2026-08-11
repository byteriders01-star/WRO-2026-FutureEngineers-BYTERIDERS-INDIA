import struct
HEADER = bytes([0xAA, 0x55]); FOOTER = bytes([0x0D])
CMD_DRIVE = 0x01
def calculate_crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc
class PacketEncoder:
    def __init__(self): self.seq = 0
    def encode_drive(self, servo_deg, speed):
        self.seq = (self.seq + 1) & 0xFF
        s = int(max(-45, min(45, servo_deg)) * 100)
        v = int(max(-100, min(100, speed)) * 10)
        payload = struct.pack(">BBhh", self.seq, CMD_DRIVE, s, v)
        return HEADER + payload + bytes([calculate_crc8(HEADER + payload)]) + FOOTER