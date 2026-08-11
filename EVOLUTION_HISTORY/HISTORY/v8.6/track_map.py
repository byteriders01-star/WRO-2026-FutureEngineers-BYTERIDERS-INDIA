class TrackMap:
    def __init__(self, vehicle_width=160.0):
        self.vw = vehicle_width
    def lane_width_mm(self, left_mm, right_mm):
        return left_mm + right_mm + self.vw
    def section(self, front_mm):
        if front_mm < 350: return "CORNER_IN_TURN"
        if front_mm < 550: return "CORNER_APPROACH"
        return "STRAIGHTAWAY"