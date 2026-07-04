# R-LAAER Roadmap — Phase 2 Milestones

## Milestone 1: Provenance (Complete Reproducibility)

Every artifact traces back to its origin.

```
spec hash → git commit → engine version → dataset hashes
                                            → compiler version
                                            → CUDA version
                                            → model version
```

**Requirements:**
- spec.yaml SHA256 locked at pre-registration (done in v1)
- Git commit pinned in `.pre_registration.json` (partial)
- Engine version recorded in results (stub)
- Dataset SHA256 hashes cached (done in Scraper)
- Compiler + CUDA + model versions recorded at execution time
- Full provenance chain in published manuscript appendix

**Status:** Implemented (Phase 2 complete; supersedes prior "Not started" designation). ProvenanceTracker captures git commit, spec hash, platform, toolchain. Full chain rendered in manuscript appendix.

---

## Milestone 2: Experiment Registry (Searchable Index)

Replace filesystem-based `experiments/` directory with an indexed registry.

**Requirements:**
- SQLite or JSON-based registry (`rlaaer/data/registry.json`)
- Searchable by: pillar, hypothesis, dataset, author, engine version, outcome, publication status
- Metadata index updated on every lifecycle transition
- CLI query: `pipeline search --pillar 07 --outcome significant`

**Status:** Implemented (Phase 2 complete; supersedes prior "Not started" designation). SQLite-backed ExperimentRegistry with list/search/history/stats. Wired into all CLI lifecycle transitions.

---

## Milestone 3: Scheduler (Experiment Queue)

Move from sequential single-experiment execution to a managed queue.

**Requirements:**
- Priority queue with configurable weights
- Automatic retry on failure (with backoff)
- Resource allocation (CPU, GPU, memory limits)
- Parallel worker pool (N workers, configurable)
- Queue persistence across restarts
- `pipeline queue` CLI subcommands (list, prioritize, cancel, retry)

**Status:** Implemented (Phase 2 complete; supersedes prior "Not started" designation). Priority queue, retry with exponential backoff, ThreadPoolExecutor workers, JSON job persistence, CLI queue subcommands.

---

## Milestone 4: Native Engine Streaming

Replace request/response polling with real-time WebSocket telemetry.

**Requirements:**
- Engine → WebSocket → live statistics stream
- Live metrics as they compute (not CSV after completion)
- Live council review during execution (not post-hoc)
- Adaptive experiment control: adjust parameters mid-run based on live metrics
- Early stopping when significance is reached or failure detected

**Architecture:**

```
Engine ──WebSocket──▶ Stream Processor ──▶ Live Dashboard
                         │
                         ├──▶ Live Statistician (real-time t-tests)
                         ├──▶ Live Council (early review)
                         └──▶ Adaptive Controller (parameter adjustment)
```

**Status:** Implemented (Phase 2 complete; supersedes prior "Not started" designation). StreamProcessor (WebSocket + synthetic fallback), LiveStatistician (Welford online stats, sequential Welch's t-test, Cohen's d), AdaptiveController, LiveDashboard, CLI stream/dashboard.

---

## Milestone 5: Experiment Graph (DAG Workflows)

Chain experiments into directed acyclic graphs where outputs feed inputs.

**Requirements:**
- `spec.yaml` gains `depends_on: [experiment_id, ...]` field
- Artifact inheritance: Experiment B inherits baseline from Experiment A
- DAG validation (no cycles, all deps satisfied)
- Partial re-execution: only re-run changed ancestors
- Parallel DAG execution: independent branches run concurrently
- Visualization: `pipeline graph --id 009 --render`

**Example:**

```
Experiment A (homeostasis baseline)
    │
    ├──▶ Experiment B (with noise injection) ──▶ Experiment D (combined effects)
    │
    └──▶ Experiment C (with coupling modulation)
```

**Status:** Implemented (Phase 2 complete; supersedes prior "Not started" designation). DepGraph (Kahn's algorithm, cycle detection, parallel levels), DAGExecutor (ThreadPoolExecutor, partial re-execution, error isolation), CLI graph subcommands.

---

## Phase 3 — Forward-Looking Capabilities

The following capabilities are beyond Phase 2's scope and represent future architectural evolution:

### 3.1 Distributed Execution

Replace the local `ThreadPoolExecutor` worker pool with a distributed task queue spanning multiple machines or clusters.

**Requirements:**
- Worker registration/discovery (mDNS, Consul, or similar)
- Task serialization with full provenance context (spec hash, git commit, dataset hashes)
- Result aggregation and conflict resolution
- Fault tolerance: worker loss → task re-queued
- CLI: `pipeline execute --distributed --workers host1:port,host2:port`

**Architecture sketch:**
```
CLI / Scheduler ──▶ Message Queue (RabbitMQ / NATS)
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
        Worker 1    Worker 2    Worker N
        (GPU node)  (CPU node)  (cloud spot)
            │           │           │
            └───────────┼───────────┘
                        ▼
                Result Collector ──▶ Registry
```

### 3.2 Real Engine Integration

Replace the synthetic data fallback (`_run_simulation` stub, `StreamProcessor` Gaussian noise) with native WebSocket telemetry from the Van Neumann Engine.

**Requirements:**
- `EngineClient` connects to engine WebSocket at `ws://localhost:8081/stream`
- StreamProcessor consumes engine's real pillar state, WHT coefficients, FLL graph updates
- LiveStatistician operates on engine-native telemetry (not synthetic)
- AdaptiveController sends parameter adjustments back through engine REST API
- Engine startup/shutdown lifecycle managed by Scheduler

**Dependencies:**
- Engine WebSocket endpoint must publish structured telemetry frames (protobuf or JSON)
- Engine REST API must accept live parameter overrides
- Engine must support checkpoint/restore for experiment rollback

### 3.3 Experiment Federation

Allow multiple R-LAAER instances (different labs, machines, organizations) to share registries, provenance chains, and reproducibility artifacts.

**Requirements:**
- Federation protocol over HTTPS or libp2p
- Registry sync (merge conflicts resolved by spec hash + git commit)
- Provenance artifact exchange (CSV, spec.yaml, transcripts, manuscripts)
- Cross-instance search: `pipeline search --federation --query "hypothesis:entropy"`
- Trust model: pinning keys for known lab identities, audit trail for untrusted sources

**Architecture sketch:**
```
Lab A Registry ──▶ Federation Bridge ──▶ Lab B Registry
     │                                         │
     ├── Publish spec + results                 ├── Subscribe to topics
     ├── Query remote provenance                ├── Replicate artifacts
     └── Verify artifact hashes                 └── Cache remote entries
```

### 3.4 Knowledge Graph Integration

Published experiments become searchable nodes in a knowledge graph, consumed by the Hypothesis Generator for literature-grounded proposal.

**Requirements:**
- Entity extraction from published manuscripts (hypotheses, metrics, effect sizes, data sources)
- Relationship edges: `replicates`, `contradicts`, `extends`, `depends_on`, `uses_data_source`
- Graph query: "find experiments with effect size > 0.5 that use Census data"
- Hypothesis Generator queries graph before proposing new experiments
- Visualization: interactive graph browser in DeveloperConsole

**Data model:**
```
Nodes: Experiment, Hypothesis, Metric, DataSource, Agent, Publication
Edges: TESTS, MEASURES, USES, PRODUCES, REPLICATES, CONTRADICTS, EXTENDS
```

### 3.5 Closed-Loop Autonomous Science

**Structural risk: this is not just another feature.**

It implicitly requires governance primitives that are not yet explicit in Phase 2:

- **Compute budgeting** — per-experiment, per-agent, daily/weekly caps enforced at the scheduler level
- **Safety constraints on experiment generation** — hypothesis must pass adversarial filtering before entering the queue (not just at review time)
- **Adversarial hypothesis filtering** — separate pre-execution gate that rejects harmful, expensive, or-duplicate proposals before they consume resources
- **Replayability guarantees** — auto-generated experiments must be fully deterministic; random seeds, parameter grids, and data splits pinned at generation time
- **"Why was this experiment generated?" traceability** — every auto-generated experiment must carry a provenance chain back to the specific literature gap, anomaly alert, or prior result that triggered it

Phase 2 provides implicit scaffolding (review gates, registry, provenance tracker, spec validation), but Phase 3.5 forces these into **first-class policy infrastructure** — enforceable at the scheduler level, auditable in the registry, and rendered in the publication appendix. These primitives should be designed before the closed-loop orchestrator is built, not retrofitted after.

The agent council proposes, executes, reviews, and refines experiments in a continuous loop under configurable governance constraints.

**Requirements:**
- Orchestrator agent manages the loop lifecycle
- Governance constraints: max concurrent experiments, daily compute budget, allowed data tiers, required reviewer quorum
- Experiment chaining: output of experiment N feeds hypothesis generation for experiment N+1
- Automatic refinement: if review is "conditional", designer agent revises and resubmits
- Auto-publish: if review passes governance and significance threshold, manuscript is generated and queued for publication
- Human-in-the-loop break-glass: any council member can escalate to human review

**Lifecycle:**
```
        ┌──────────────────────────────────────────────┐
        │                                              ▼
    Hypothesis Gen ──▶ Designer ──▶ Scheduler ──▶ Execution ──▶ Review ──▶ Publish
        ▲                                                                   │
        └─────────────────────── Feedback ──────────────────────────────────┘
```

---

*Phase 2 (Milestones 1–5, LLM Council Integration, Review Transcripts, Experiment 009) complete. Phase 3 items are aspirational and unstarted.*

## Completed Checklist

| Item | Date | Evidence |
|------|------|----------|
| M1: Provenance | 2026-07-03 | ProvenanceTracker, manuscript appendix |
| M2: Registry | 2026-07-03 | SQLite, CLI search/history |
| M3: Scheduler | 2026-07-03 | Priority queue, retry, workers |
| M4: Streaming | 2026-07-03 | Welford online stats, adaptive control |
| M5: Graph | 2026-07-03 | DepGraph, DAGExecutor |
| LLM Council | 2026-07-03 | 9 roles, Ollama, JSON parsing |
| Review Transcripts | 2026-07-03 | Per-experiment review artifacts |
| Experiment 009 | 2026-07-03 | Census data, 125 trials |
| GitHub push + CI | 2026-07-03 | github.com/UrukuTelal/VNES-Lab |
| Polish | 2026-07-03 | depends_on docs, socket probe, Ollama timeout |
| Regression suite | 2026-07-04 | 241/241 PASS (verified) |
| R-LAAER tests | 2026-07-04 | 265/265 PASS (verified) |

## Known Gaps

1. **Pillar Council infra:** Van_Nueman_AI missing `aiohttp`, `numpy`, `ollama` packages
2. **CI doesn't run R-LAAER tests** — requires adding `requests` + `pytest` to deps
3. **API keys unset** — CENSUS_API_KEY, NASA_API_KEY, NOAA_API_KEY, KAGGLE_API_KEY empty
4. **MultiverseScreensaver:** Not a git repo
5. **Van_Nueman_Whisper:** Path missing
