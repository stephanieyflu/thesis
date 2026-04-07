class OHCAEvent:
    def __init__(self, event_time, location):
        self.event_time = event_time
        self.location = location
        self.responder_arrivals = []
        self.redundant_responders = []
        self.responders_alerted = []
        self.success = False
        self.first_arrival_time = None
        self.num_accepted = 0
        self.num_redundant = 0
