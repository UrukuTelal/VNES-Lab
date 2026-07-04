# Demographic Scaling of Consensus Formation

**Experiment ID:** 009

**Authors:** R-LAAER

**Date:** 2026-07-04

**License:** CC-BY-4.0


---

## Abstract

**Hypothesis:** If entity population size follows real Census demographic distributions, then consensus convergence time scales logarithmically with population diversity entropy, modulated by the Scale Router attention attenuation mechanism.


**Data Sources:** census

**Systems:** VNES-Lab (PSV layer)

---

## Introduction

**Domain:** emergence, cognition, multi-agent, scale-router

**Hypothesis:** If entity population size follows real Census demographic distributions, then consensus convergence time scales logarithmically with population diversity entropy, modulated by the Scale Router attention attenuation mechanism.


**Grounding:**
- census: US Census ACS 5-year estimates (2016-2020) for population by region. Embedded as static snapshot in data/census_regions.csv. Four regions: Northeast (17.1%), Midwest (20.7%), South (38.1%), West (24.1%).



---

## Methods

### Parameters

- **population_scale**: domain=[0, 4], steps=5, source=None
- **diversity_entropy**: domain=[0.1, 0.9], steps=5, source=None
- **random_seed** (controlled): 42
- **timesteps** (controlled): 1000
- **consensus_threshold** (controlled): 0.85

### Statistical Design

- Alpha: 0.05
- Power: 0.8
- Minimum effect size: 0.3
- Method: independent_t

### Execution

- Trials: 125
- Max duration: 15 min
- Checkpoint interval: 250 ticks

---

## Results

*No results available.*

---

## Statistical Analysis

*Analysis pending.*

---

## Peer Review

*Not yet reviewed.*

---

## Discussion

*Interpretation pending.*

---

## Conclusion

*Summary pending.*

---

## References

- [census] US Census ACS 5-year estimates (2016-2020) for population by region. Embedded as static snapshot in data/census_regions.csv. Four regions: Northeast (17.1%), Midwest (20.7%), South (38.1%), West (24.1%).


---

## Appendix


### Provenance

*No provenance data available.*

### Review Transcripts

#### Literature Review Agent (Archive)
- **Decision:** accept
- **Confidence:** 0.8
- **Model:** stub
- **Prompt Version:** v1.2
- **Timestamp:** 2026-07-04T03:29:11.091871+00:00

#### Methodologist (Veridian)
- **Decision:** accept
- **Confidence:** 0.8
- **Model:** stub
- **Prompt Version:** v1.2
- **Timestamp:** 2026-07-04T03:29:11.085882+00:00

#### Performance Analyst (Raster)
- **Decision:** accept
- **Confidence:** 0.8
- **Model:** stub
- **Prompt Version:** v1.2
- **Timestamp:** 2026-07-04T03:29:11.088844+00:00

#### Physicist (Flux)
- **Decision:** accept
- **Confidence:** 0.8
- **Model:** stub
- **Prompt Version:** v1.2
- **Timestamp:** 2026-07-04T03:29:11.087883+00:00

#### Reproducibility Officer (Pivot)
- **Decision:** accept
- **Confidence:** 0.8
- **Model:** stub
- **Prompt Version:** v1.2
- **Timestamp:** 2026-07-04T03:29:11.091871+00:00

#### Security Researcher (Havik)
- **Decision:** accept
- **Confidence:** 0.8
- **Model:** stub
- **Prompt Version:** v1.2
- **Timestamp:** 2026-07-04T03:29:11.088844+00:00

#### Systems Engineer (Link)
- **Decision:** accept
- **Confidence:** 0.8
- **Model:** stub
- **Prompt Version:** v1.2
- **Timestamp:** 2026-07-04T03:29:11.088844+00:00

#### Theoretician (Axiom)
- **Decision:** accept
- **Confidence:** 0.8
- **Model:** stub
- **Prompt Version:** v1.2
- **Timestamp:** 2026-07-04T03:29:11.086890+00:00

#### Validation Engineer (Probe)
- **Decision:** accept
- **Confidence:** 0.8
- **Model:** stub
- **Prompt Version:** v1.2
- **Timestamp:** 2026-07-04T03:29:11.091871+00:00
