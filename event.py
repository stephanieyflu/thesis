import numpy as np

class OHCAEvent:
    def __init__(self, event_time, location):
        self.event_time = event_time
        self.location = location  # Could be x,y coordinates for clustering
        self.responders_alerted = []
        self.success = False
        self.first_arrival_time = None
