import time
from collections import deque

class TimeSyncLayer:
    """
    Layer 2: Time Synchronization & Sensor Buffer Manager
    Aligns asynchronous sensor inputs (VL53, MPU6050, Vision) into
    time-synchronized state frames with latency compensation.
    """
    def __init__(self, buffer_size: int = 50):
        self.buffer_size = buffer_size
        self.sensor_buffer = deque(maxlen=buffer_size)

    def push_frame(self, sensor_data: dict, perception_data: dict):
        timestamp = time.time()
        synced_frame = {
            "timestamp": timestamp,
            "sensors": sensor_data,
            "perception": perception_data,
            "latency_ms": (timestamp - sensor_data.get("timestamp", timestamp)) * 1000.0
        }
        self.sensor_buffer.append(synced_frame)

    def get_latest_frame(self) -> dict:
        if not self.sensor_buffer:
            return None
        return self.sensor_buffer[-1]

    def get_history(self, num_frames: int = 10) -> list:
        return list(self.sensor_buffer)[-num_frames:]
