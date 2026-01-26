# thesis

### Getting Started

Create a virtual environment

    python -m venv .venv-thesis

Activate your virtual environment

    source .venv/Scripts/activate

Install requirements

    pip install -r requirements.txt

### Folder Structure

```
thesis/
│
├── README.md                  # project documentation
├── requirements.txt           # python dependencies
├── main.py                    # entry point to run simulations
├── config.py                  # simulation parameters
├── event.py                   # OHCA event class
├── responder.py               # responder agent class
├── policies.py                # alert policy definitions
├── simulation.py              # core DES logic
├── utils.py                   # helper functions for random sampling and travel times
├── analysis.py                # summary statistics and plotting
└── results/
    └── output.csv             # Aggregated simulation outputs
```