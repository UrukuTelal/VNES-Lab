# R-LAAER — Research Lab Adversarial Agentic Experiment Runner

## Design Record

**Filed:** 2026-07-03
**Status:** draft (not yet committed — awaiting first implementation pass)
**Authorities:** This document is Level 1 (interpretation) until its claims are verified by regression_suite.py (Level 4) and CI (Level 5).

---

## 1. Purpose

Build a system where adversarial agents:
1. **Scour online databases** for real-world variables and applications relevant to the Van Nueman project
2. **Design experiments** that test the system against real-world data
3. **Run experiments** against the full stack (VNES-Lab + C++ Engine + REST API)
4. **Produce peer-reviewable reports** using the Adversarial Council methodology

---

## 2. Scoping Decisions

### 2.1 Data Sources — Multi-Domain Ingestion (Hierarchical Priority)

| Tier | Sources | Trust | Use |
|------|---------|-------|-----|
| 1 | arXiv, NASA, NOAA, US Census | Highest | Calibration, parameter grounding, physics constraints, baseline priors |
| 2 | Kaggle, UCI ML Repository | Medium | Agent training environments, synthetic world validation, pattern discovery |
| 3 | General web search | Lowest | Hypothesis generation, anomaly detection, novelty discovery — NO direct parameter injection |

**Critical rule:** All external data must pass through:
```
raw data → parser agent → verification layer → pillar encoding → simulation injection
```
Never: `web → direct simulation mutation`

### 2.2 Stack Target — Full Stack

Experiments target ALL layers:

| Layer | Role | Strength | Weakness |
|-------|------|----------|----------|
| VNES-Lab (Python PSV) | Rapid hypothesis prototyping | Fast iteration | No physical grounding |
| C++ Engine Core | Ground truth execution | Real physics + emergence | Slow iteration |
| REST/WebSocket API | Orchestration + telemetry | Controllability, observability | Depends on engine |

**Principle:** Experiments are propagated across layers as synchronized hypotheses — not run in isolation.

### 2.3 Council Architecture — Hybrid (Existing + New)

**Existing agents (repurposed as Adversarial Review Board / Critic Layer):**

| Agent | Role in R-LAAER |
|-------|-----------------|
| Veridian — The Auditor | **The Methodologist** — study design audit, confounds |
| Axiom — The Mathematician | **The Theoretician** — math grounding, known-theory validation |
| Flux — The Physicist | **The Physicist** — physics-domain experiments, energy checks |
| Link — The Compiler Engineer | **The Systems Engineer** — API integration, stack boundary tests |
| Raster — The Performance Engineer | **The Performance Analyst** — benchmarking, scaling curves |
| Havik — The Security Engineer | **The Security Researcher** — boundary conditions, adversarial inputs |
| Pivot — The Maintainer | **The Reproducibility Officer** — reproducibility packages, documentation |
| Probe — The Test Engineer | **The Validation Engineer** — metric cross-checks, statistical error detection |
| Archive — The Historian | **The Literature Review Agent** — prior art search, citation |

**New agents (Experiment Designer Layer):**

| Agent | Role |
|-------|------|
| Hypothesis Generator | Generates falsifiable hypotheses from literature gaps |
| Experiment Synthesizer | Translates hypothesis into concrete run.py implementation |
| Metric Designer | Selects appropriate metrics and statistical tests |
| Data Source Selector | Matches hypotheses to available real-world datasets |
| Failure Mode Forecaster | Predicts what could go wrong before execution |

**Separation of concerns:**
- Old council: critique / break / stress test
- New agents: design / propose / structure
- Engine: execute
- VNES-Lab: prototype

### 2.4 Output Format — Dual Publication

| Format | Use Case |
|--------|----------|
| Markdown | Internal system review, iteration logs, council evaluation |
| LaTeX/PDF | Formal papers, external sharing, research archiving |

---

## 3. Experiment Lifecycle

### 10 Steps

| Step | Real Research Analogue | Who | Artifact |
|------|----------------------|-----|----------|
| 1 | Literature Review | Archive + Domain Scraper | 3-5 grounding papers, cited |
| 2 | Data Discovery | Domain Scraper + Data Scientist | Registry entry in sourced_datasets.json |
| 3 | Hypothesis Design | Designer agents + Methodologist | spec.yaml with hypothesis, parameters, metrics |
| 4 | Pre-Registration | Pillar Council (16 reps) | Locked spec.yaml + approved status |
| 5 | Implementation | Experiment Synthesizer | run.py + metrics.py entries |
| 6 | Code Review | Adversarial Council (9 agents) | Review verdicts |
| 7 | Execution | Runner + engine_client.py | CSV metrics + raw results |
| 8 | Statistical Testing | Statistician agent | Effect sizes, CIs, significance verdict |
| 9 | Peer Review | All 14 agents + Meta-Reviewer | Multi-round revision, editorial decision |
| 10 | Publication | Editor agent | Markdown manuscript + LaTeX PDF |

### Status Flow
```
draft → registered → executing → review → published | rejected
```

---

## 4. Experiment DSL

### spec.yaml — The Core Contract

Each experiment has a single `spec.yaml` that all agents, councils, and pipeline stages read from and write to.

Key sections:
- `experiment` — ID, title, hypothesis, status, author
- `systems` — which stack layers are involved (VNES-Lab, engine, API)
- `data_sources` — traced to Tier model (Tier 1/2/3)
- `parameters` — independent vars (with domain + source), controlled vars, computed vars
- `metrics` — stability (approx with tolerance) + invariants (lt/gt with thresholds)
- `statistics` — pre-registered: alpha, power, effect size, analysis method
- `execution` — trials, duration, checkpoint, rollback
- `review` — pre-registration requirements, peer reviewer list, revision cap
- `publication` — format, license, authors

---
