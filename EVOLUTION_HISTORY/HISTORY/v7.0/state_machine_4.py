class StateMachine:
    def __init__(self):
        self.state = "INIT"
        self.rules = [
            ("INIT",    lambda m: m.start_signal,           "RUNNING"),
            ("RUNNING", lambda m: m.parking_detected,       "PARKING"),
            ("PARKING", lambda m: m.stop_completed,         "FINISHED"),
        ]
    def update(self, mission):
        for state, cond, next_state in self.rules:
            if self.state == state and cond(mission):
                self.state = next_state
                return
        return self.state
