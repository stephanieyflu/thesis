# thesis

thesis/
│
├── main.py                     # Entry point – runs experiments & compares policies
├── config.py                   # Centralized configuration parameters
├── environment.py              # Defines SimPy environments (urban, rural)
├── responders.py               # Responder logic (availability, fatigue, travel)
├── events.py                   # Cardiac event process & policy handling
├── policies.py                 # Defines static and dynamic alert policies
└── analysis.py                 # Aggregation, visualization, and summary