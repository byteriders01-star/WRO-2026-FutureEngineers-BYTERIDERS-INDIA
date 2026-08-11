import struct

HEADER = bytes([0xAA, 0x55])
FOOTER = bytes([0x0D])

CMD_DRIVE = 0x01
CMD_EMERGENCY_STOP = 0x02
CMD_CALIBRATE = 0x03

def calculate_crc8(data: bytes) -> int:
    """CRC8 (Polynomial 0x07 - SMBus compliant)"""
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc

class PacketEncoder:
    def __init__(self):
        self.seq_number = 0

    def encode_drive(self, servo_angle_deg: float, motor_speed: float, cmd: int = CMD_DRIVE) -> bytes:
        """
        Encodes motion commands into a 10-byte serial binary packet.
        - servo_angle_deg: float (-45.0 to +45.0 degrees) mapped to int16 (scale x100)
        - motor_speed: float (-100.0 to +100.0 percent) mapped to int16 (scale x10)
        """
        self.seq_number = (self.seq_number + 1) & 0xFF
        servo_raw = int(clamp(servo_angle_deg, -45.0, 45.0) * 100)
        speed_raw = int(clamp(motor_speed, -100.0, 100.0) * 10)

        payload = struct.pack(">BBhh", self.seq_number, cmd, servo_raw, speed_raw)
        crc = calculate_crc8(HEADER + payload)
        
        packet = HEADER + payload + bytes([crc]) + FOOTER
        return packet

class PacketDecoder:
    """Parses binary packets from ESP32 telemetry/feedback if needed."""
    def parse_packet(self, data: bytes):
        if len(data) < 10:
            return None
        if data[0:2] != HEADER or data[-1:] != FOOTER:
            return None
        
        calculated_crc = calculate_crc8(data[0:8])
        if calculated_crc != data[8]:
            return None # CRC mismatch

        seq, cmd, servo_raw, speed_raw = struct.unpack(">BBhh", data[2:8])
        return {
            "seq": seq,
            "cmd": cmd,
            "servo_angle": servo_raw / 100.0,
            "motor_speed": speed_raw / 10.0
        }

def clamp(val, min_val, max_val):
    return max(min_val, min(val, max_val))
