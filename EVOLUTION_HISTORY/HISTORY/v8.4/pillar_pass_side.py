class SurpriseRuleAdapter:
    def __init__(self, cfg):
        self.reversed = cfg.get("SIGN_LOGIC", "NORMAL").upper() == "REVERSED"
    def get_avoidance_direction(self, color):
        if color == "green":
            return "RIGHT" if self.reversed else "LEFT"
        if color == "red":
            return "LEFT" if self.reversed else "RIGHT"
        return "CENTER"