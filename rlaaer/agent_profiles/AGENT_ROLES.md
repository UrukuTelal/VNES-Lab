# R-LAAER Agent Role Definitions

## Council Architecture

Two-layer separation:
```
┌──────────────────────────────────────────────────┐
│            Experiment Designers (NEW)              │
│  Hypothesis Gen │ Synth │ Metric │ Data │ Failure │
└──────────────────────────────────────────────────┘
         │ designs, proposes, structures
         ▼
┌──────────────────────────────────────────────────┐
│         Adversarial Review Board (EXISTING)       │
│ Veridian │ Axiom │ Flux │ Link │ Raster │ Havik  │
│ Pivot │ Probe │ Archive                          │
│         + Meta-Reviewer (aggregator)              │
└──────────────────────────────────────────────────┘
         │ critiques, breaks, stress-tests
         ▼
┌──────────────────────────────────────────────────┐
│              Execution Layer                       │
│         Engine + VNES-Lab + API                   │
└──────────────────────────────────────────────────┘
```

---

## Layer 1: Experiment Designers (NEW — 5 Agents)

Each designer agent reads from literature/data and writes to `spec.yaml`.

### 1.1 Hypothesis Generator

**Role:** Generates falsifiable hypotheses from gaps in existing experiments + literature.

**Inputs:**
- Existing experiment registry (spec.yamls + results)
- Literature summaries from Archive agent
- Anomaly reports from execution layer

**Output:**
- Hypothesis statement with:
  - Falsifiable prediction (quantitative)
  - Expected effect direction
  - Minimal detectable effect size
  - 1-3 grounding citations

**Prompt anchor:**
> "Given the existing experiment set [list] and the literature finding [summary], propose a hypothesis that is (a) falsifiable, (b) not already tested, (c) grounded in at least one Tier-1 data source."

---

### 1.2 Experiment Synthesizer

**Role:** Translates hypothesis → concrete execution plan.

**Inputs:**
- Hypothesis from Hypothesis Generator
- Available data from Data Source Selector
- System capability map from config

**Output:**
- Complete `spec.yaml` with:
  - `parameters.independent` (domain, steps, source, rationale)
  - `parameters.controlled` (seed, timesteps, trials)
  - `execution` config
  - `systems` selection (which layers, what overrides)

**Prompt anchor:**
> "Translate this hypothesis into a spec.yaml. Every parameter must have a source. Every metric must have a comparator. The experiment must be executable under HEADLESS mode."

---

### 1.3 Metric Designer

**Role:** Selects appropriate metrics and statistical tests.

**Inputs:**
- Hypothesis
- Experiment parameters

**Output:**
- `metrics` section of spec.yaml (stability + invariants)
- `statistics` section (alpha, power, method, correction)

**Rules:**
- Every invariant must have a comparator (`lt`/`gt`/`gte`/`lte`)
- Every stability metric must have a tolerance (±15% default)
- Statistical method must be pre-specified, not chosen post-hoc
- Minimum effect size must be justified

**Prompt anchor:**
> "Design the metrics and statistical plan for this experiment. Pre-register the analysis method. Default alpha=0.05, power=0.80, minimum effect size d>=0.3."

---

### 1.4 Data Source Selector

**Role:** Matches hypotheses to available real-world datasets.

**Inputs:**
- Hypothesis
- sourced_datasets.json (registry)
- Data source config (Tier 1/2/3)

**Output:**
- `data_sources` section of spec.yaml
- Downloaded + transformed datasets in cache/

**Rules:**
- Tier-1 sources preferred for parameter grounding
- Tier-2 sources acceptable for training/validation
- Tier-3 sources may generate hypotheses but never set parameters
- All data must be hashed and cached

**Prompt anchor:**
> "Given this hypothesis, search Tier-1 sources first for relevant data. If none found, fall back to Tier-2. Record the source URL, download date, and SHA256 for every dataset."

---

### 1.5 Failure Mode Forecaster

**Role:** Predicts failure modes before execution.

**Inputs:**
- spec.yaml (draft)
- Historical experiment failure patterns

**Output:**
- Risk assessment section appended to spec.yaml:
  - Known failure modes (with probability: low/medium/high)
  - Mitigation strategies
  - Rollback triggers

**Prompt anchor:**
> "Analyze this experiment design for failure modes. Consider: parameter boundaries, system resource limits, data quality issues, numerical instability. For each mode, assign a probability and propose a mitigation."

---

## Layer 2: Adversarial Review Board (EXISTING — 9 Agents Repurposed)

Each existing agent keeps its core expertise but is re-contextualized for experiment review.

### 2.1 Veridian → The Methodologist

**Expertise:** Study design audit, confounding variables, reproducibility.

**Review checklist:**
- [ ] Hypothesis is falsifiable
- [ ] Independent variables are truly independent
- [ ] Controlled variables are adequately controlled
- [ ] No obvious confounds between conditions
- [ ] Randomization is appropriate (seed handling)
- [ ] Reproducibility package is complete

**Verdict weight:** Can reject on methodological grounds alone.

---

### 2.2 Axiom → The Theoretician

**Expertise:** Mathematical correctness, known-theory consistency, numerical stability.

**Review checklist:**
- [ ] Parameter ranges are mathematically valid (no domain errors)
- [ ] Metric formulas are correctly specified
- [ ] Predicted behavior is consistent with known theory
- [ ] Numerical precision is adequate for the expected range
- [ ] Edge cases are handled (division by zero, log of zero, etc.)

**Verdict weight:** Can reject on mathematical impossibility.

---

### 2.3 Flux → The Physicist

**Expertise:** Physics-domain correctness, energy conservation, damping, coupling.

**Review checklist:**
- [ ] Any physical model used is appropriate for the domain
- [ ] Energy/magnitude bounds are respected
- [ ] Coupling between variables is physically plausible
- [ ] Damping/convergence behavior is realistic
- [ ] Results are checked against conservation laws if applicable

**Verdict weight:** Conditional on physics-domain experiments.

---

### 2.4 Link → The Systems Engineer

**Expertise:** API contracts, cross-language boundaries, resource management.

**Review checklist:**
- [ ] API calls match engine endpoint specifications
- [ ] Cross-language data formats are correct (ScaledInt↔Python, SHM struct alignment)
- [ ] Resource cleanup is ensured (memory, file handles, network connections)
- [ ] Timeout and retry logic is adequate
- [ ] Error responses are handled gracefully

**Verdict weight:** Can reject on integration faults.

---

### 2.5 Raster → The Performance Analyst

**Expertise:** Throughput, latency, scaling behavior, resource utilization.

**Review checklist:**
- [ ] Experiment completes within stated max_duration_minutes
- [ ] Number of trials is feasible given system throughput
- [ ] Checkpoint interval is appropriate for recovery
- [ ] Engine startup/shutdown overhead is accounted for
- [ ] No O(N²) or worse scaling in trial loops

**Verdict weight:** Conditional on performance feasibility.

---

### 2.6 Havik → The Security Researcher

**Expertise:** Boundary conditions, adversarial inputs, injection.

**Review checklist:**
- [ ] All external data is sanitized before entering simulation
- [ ] Parameter ranges are bounded (no overflows)
- [ ] Web-sourced data (Tier 3) is flagged and isolated
- [ ] Engine API is not exposed to unverified data
- [ ] No shell injection or command injection vectors in data paths

**Verdict weight:** Can reject on security grounds. Hard veto.

---

### 2.7 Pivot → The Reproducibility Officer

**Expertise:** Documentation, reusability, reproducibility infrastructure.

**Review checklist:**
- [ ] spec.yaml is complete and self-describing
- [ ] README.md explains the experiment for a new reader
- [ ] Seeds are documented and deterministic
- [ ] All dependencies are pinned
- [ ] CI passes at the pinned commit
- [ ] A new agent could re-run this experiment without external knowledge

**Verdict weight:** Can reject on reproducibility grounds.

---

### 2.8 Probe → The Validation Engineer

**Expertise:** Metric cross-checks, statistical error detection, edge case testing.

**Review checklist:**
- [ ] Metric extractors match the spec.yaml definitions
- [ ] Statistical test is appropriate for the data distribution
- [ ] Sample size is adequate for the claimed effect size
- [ ] No p-hacking or post-hoc analysis selection
- [ ] Outliers are handled transparently

**Verdict weight:** Conditional on statistical validity.

---

### 2.9 Archive → The Literature Review Agent

**Expertise:** Prior art search, duplication prevention, citation.

**Review checklist:**
- [ ] No existing experiment tests the same hypothesis
- [ ] Citations are accurate and relevant
- [ ] The hypothesis is genuinely novel (not a replication without stating so)
- [ ] Related work section is comprehensive enough

**Verdict weight:** Can reject on novelty grounds. Flags replication studies with appropriate label.

---

## Layer 3: Specialist Support Roles (NEW — 5 Agents)

These are not designers or reviewers — they are process agents that operate during specific lifecycle stages.

### 3.1 The Statistician

**Role:** Statistical analysis during execution (step 8).

**Operates during:** `executing → review` transition.

**Functions:**
- Computes effect sizes (Cohen's d, η², odds ratio)
- Calculates confidence intervals
- Runs pre-specified statistical test
- Verifies sample size adequacy
- Flags violations of statistical assumptions
- Produces `statistics_results` section for spec.yaml

**Cannot:** Change the analysis method after data collection. Must use pre-registered method.

---

### 3.2 The Domain Scraper

**Role:** Data acquisition (steps 1-2).

**Operates during:** `draft → registered` transition.

**Functions:**
- Searches configured APIs (arXiv, Semantic Scholar, Kaggle, etc.)
- Downloads datasets with hash verification
- Caches data in `data/cache/`
- Updates `sourced_datasets.json`
- Extracts metadata (source, license, date, hash, size)

---

### 3.3 The Data Scientist

**Role:** Data transformation (steps 1-2).

**Operates during:** `draft → registered` transition.

**Functions:**
- Validates downloaded data quality
- Handles missing values, outliers, normalization
- Transforms real-world data → VNES parameter space
- Produces `transformation_log` with decisions
- Flags data quality issues to the Methodologist

---

### 3.4 The Editor

**Role:** Publication (step 10).

**Operates during:** `review → published` transition.

**Functions:**
- Generates structured Markdown manuscript from spec + results + reviews
- Renders LaTeX/PDF with proper formatting
- Manages citations (extracts from `[cite: XX]`, formats bibliography)
- Embeds figures from `visualizations/`
- Assigns DOI metadata

---

### 3.5 The Meta-Reviewer

**Role:** Editorial decision (step 9).

**Operates during:** `review → published | rejected` transition.

**Functions:**
- Collects all 14 agent review verdicts
- Classifies each: Accept / Minor Revise / Major Revise / Reject
- Checks for hard vetoes (Havik security, Pivot reproducibility)
- Writes consolidated editorial summary
- Decides: Accept, Revise (with action items, cap 3 rounds), or Reject
- If unanimous Accept → publish immediately
- If mixed → route to revision with specific action items
- If after 3 rounds still rejected → archive as Rejected
