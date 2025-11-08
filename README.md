# thesis

### Folder Structure

```
thesis/
│
├── main.py                # entry point – runs experiments & compares policies
├── config.py              # centralized configuration parameters
├── environment.py         # defines SimPy environments (urban, rural)
├── responders.py          # responder logic (availability, fatigue, travel)
├── events.py              # cardiac event process & policy handling
├── policies.py            # defines static and dynamic alert policies
└── analysis.py            # aggregation, visualization, and summary
```

### Output Example

```
=== Environment: URBAN ===
PolicyA: Avg=3.98 min, Success=67.5%, SD=0.24
PolicyB: Avg=2.76 min, Success=83.1%, SD=0.18
PolicyC: Avg=2.33 min, Success=89.4%, SD=0.12
Dynamic:  Avg=2.91 min, Success=80.3%, SD=0.20

=== Environment: RURAL ===
PolicyA: Avg=9.42 min, Success=28.4%, SD=0.52
PolicyB: Avg=6.87 min, Success=51.8%, SD=0.39
PolicyC: Avg=5.71 min, Success=61.0%, SD=0.33
Dynamic:  Avg=5.23 min, Success=64.7%, SD=0.28
```