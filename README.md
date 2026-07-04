# VNES-Lab — Experimental Validation Suite + R-LAAER

**Shift from "Does it compile?" to "What does it do under controlled conditions?"**

VNES-Lab is a standalone experimental testbed for the Van Nueman ecosystem.
It combines a classic regression suite (experiments 001-008) with **R-LAAER**,
an adversarial agentic experiment runner that designs, executes, reviews, and
publishes full-stack experiments autonomously.

## Philosophy

- **Hypothesis-first.** Every experiment states what it expects before it runs.
- **Metrics over features.** Output is CSV data and visualizations, not code.
- **Reproducible.** Each experiment seeds RNGs and logs all parameters.
- **Dual tracks:** Classic regression (pure Python, deterministic) + agentic
  experimentation (R-LAAER, multi-agent, LLM-evaluated).

## Structure

```
VNES-Lab/
├── experiments/
│   ├── 001_homeostasis/           Pillar equilibrium under perturbation
│   ├── 002_navigation/            Attractor state seeking
│   ├── 003_memory/                WHT/FLL recall and decay
│   ├── 004_prediction/            Hopf-PID trajectory forecasting
│   ├── 005_multi_agent/           Agent interaction dynamics
│   ├── 006_self_repair/           Recovery from Harm/distortion
│   ├── 007_tool_use/              PSV manipulation of environment
│   ├── 008_emergence/             Unexpected emergent behaviors
│   └── 009_demographic_consensus/ Census-driven opinion dynamics (R-LAAER)
├── rlaaer/                        R-LAAER package (see below)
├── regressions/
│   ├── regression_suite.py        Level 4 ground truth (241 metrics)
│   ├── status.py                  Level 3 derived truth
│   ├── metrics.py                 241 metric extractors
│   ├── generate_baselines.py      Baseline capture
│   ├── regression_review.py       Regression diff review
│   └── correlate.py               Cross-experiment correlation
├── lib/psv_core.py                Shared PSV math library
├── metrics/                       Cross-experiment aggregations
├── visualizations/                Shared visualization tools
├── .github/workflows/ci.yml       CI workflow (Level 5 verifier)
├── run_all.py                     Batch runner
└── requirements.txt               Python dependencies
```

## How to Run

```bash
# Regression suite (experiments 001-008)
python regressions/regression_suite.py

# Single experiment
python experiments/001_homeostasis/run.py

# All experiments (legacy)
python run_all.py

# R-LAAER pipeline (experiments 009+)
python -m rlaaer pipeline list
python -m rlaaer pipeline submit 009
python -m rlaaer pipeline execute 009
python -m rlaaer pipeline review 009
python -m rlaaer pipeline publish 009

# R-LAAER scheduler
python -m rlaaer queue --help

# R-LAAER graph (DAG workflows)
python -m rlaaer graph --help
```

## Requirements

- Python 3.10+
- numpy, matplotlib (for visualizations)
- requests (for R-LAAER engine client)
- pytest (for R-LAAER test suite, 265 tests)

## Status Convention

Every status label (blocked, fixed, pending, regression) MUST trace to one of:

| Level | Role | Description |
|-------|------|-------------|
| 5 | External verifier | `CI = run(regression_suite.py @ commit SHA)` — NOT a higher truth layer |
| 4 | Ground truth | `regressions/regression_suite.py` (canonical logic) |
| 3 | Derived truth | `regressions/status.py` (pure function over Level 4 output) |
| 2 | Persistence | commit-pinned artifacts (historical snapshots) |
| 1 | Interpretation | agent narratives — must be labeled "non-authoritative interpretation" |

**CI divergence drift guard**: CI MUST execute the same entrypoint as local ground truth.
Pins to exact commit, calls `regression_suite.py` directly.

Run `python regressions/status.py` for current derived project status.

## R-LAAER Subsystem

R-LAAER (autonomous experiment runner) lives under `rlaaer/` and provides:

| Milestone | Status | Description |
|-----------|--------|-------------|
| M1: Provenance | ✅ | spec hash → git commit → toolchain → dataset hashes |
| M2: Registry | ✅ | SQLite-backed searchable index |
| M3: Scheduler | ✅ | Priority queue, retry, parallel workers |
| M4: Streaming | ✅ | WebSocket/synthetic telemetry, online statistics |
| M5: Graph | ✅ | DAG workflows with parallel level execution |
| LLM Council | ✅ | 9-agent Ollama-powered review with stub fallback |
| Transcripts | ✅ | Per-experiment review artifacts |

**CLI:** `python -m rlaaer --help` (22+ subcommands)

**Tests:** 265/265 passing across 17 test files.

**Experiment 009:** Demographic Scaling of Consensus Formation — US Census ACS data,
5×5 factorial design, bounded-confidence opinion dynamics, 125 trials, published
manuscript with full review transcript appendix.

## Experiment Lifecycle

### Classic (001-008)
1. **Hypothesis** — State a falsifiable claim
2. **Setup** — Initialize system under controlled parameters
3. **Run** — Execute for N timesteps, logging metrics every step
4. **Measure** — Compute summary statistics from raw logs
5. **Visualize** — Generate plot showing results
6. **Report** — Print verdict (PASS/FAIL/INCONCLUSIVE) with evidence

### R-LAAER (009+)
1. **Design** — Hypothesis Generator + Designer assemble spec.yaml
2. **Pre-register** — spec locked after Pillar Council approval (≥12/16)
3. **Execute** — Data → transform → simulation → CSV metrics
4. **Review** — 9-agent adversarial council (LLM-powered)
5. **Publish** — Manuscript with provenance appendix + review transcripts
