# VNES-Lab — Experimental Validation Suite

**Shift from "Does it compile?" to "What does it do under controlled conditions?"**

VNES-Lab is a standalone experimental testbed for the Van Nueman ecosystem.
Each experiment isolates a single claim about the system and measures it
quantitatively — pressure, entropy, convergence rates, memory decay,
oscillator synchronization, and emergent behavior.

## Philosophy

- **Hypothesis-first.** Every experiment states what it expects before it runs.
- **Metrics over features.** Output is CSV data and visualizations, not code.
- **Reproducible.** Each experiment seeds RNGs and logs all parameters.
- **Minimal dependencies.** Pure Python with standard library + numpy/matplotlib.

## Structure

```
VNES-Lab/
├── experiments/
│   ├── 001_homeostasis/   Pillar equilibrium under perturbation
│   ├── 002_navigation/    Attractor state seeking
│   ├── 003_memory/        WHT/FLL recall and decay
│   ├── 004_prediction/    Hopf-PID trajectory forecasting
│   ├── 005_multi_agent/   Agent interaction dynamics
│   ├── 006_self_repair/   Recovery from Harm/distortion
│   ├── 007_tool_use/      PSV manipulation of environment
│   └── 008_emergence/     Unexpected emergent behaviors
├── lib/psv_core.py         Shared PSV math library
├── metrics/                 Cross-experiment aggregations
├── visualizations/          Shared visualization tools
├── run_all.py              Batch runner
└── requirements.txt        Python dependencies
```

## How to Run

```bash
# Single experiment
cd experiments/001_homeostasis && python run.py

# All experiments
python run_all.py

# With custom seed
python run_all.py --seed 42
```

## Requirements

- Python 3.10+
- numpy, matplotlib (for visualizations)
- Standard library only for CSV/metrics output

## Status Convention

Every status label (blocked, fixed, pending, regression) MUST trace to one of:

1. **`regressions/regression_suite.py` output** — ground truth test results
2. **`regressions/status.py` computation** — derived from suite output
3. **commit-pinned artifact** — persistent file with specific commit hash

Anything else must be explicitly labeled "non-authoritative interpretation".

Run `python regressions/status.py` to see current derived project status.

## Experiment Lifecycle

1. **Hypothesis** — State a falsifiable claim
2. **Setup** — Initialize system under controlled parameters
3. **Run** — Execute for N timesteps, logging metrics every step
4. **Measure** — Compute summary statistics from raw logs
5. **Visualize** — Generate plot showing results
6. **Report** — Print verdict (PASS/FAIL/INCONCLUSIVE) with evidence
