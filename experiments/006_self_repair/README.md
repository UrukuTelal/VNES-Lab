# 006 — Self-Repair: Recovery from Harm/Distortion

## Hypothesis
An entity subjected to a Harm event will recover its pillar state
toward equilibrium via natural damping over time. Recovery rate
depends on Integrity and Depth reserves. Entities with Depth > 0.3
recover fully; entities with Depth < 0.1 may permanently drift.

## Method
1. Apply Harm pulse (delta_theta = 0.5) to a random pillar
2. Allow entity to recover with natural drift + Depth restoration
3. Sweep initial Depth [0.05, 0.1, 0.2, 0.3, 0.5]
4. Measure recovery time and residual error

## Metrics
- initial_depth
- harm_magnitude
- recovery_time (steps to < 5% of baseline)
- residual_error (permanent drift)
- pillar_integrity_min (lowest Integrity during recovery)

## Expected Result
Depth > 0.3: full recovery (residual < 0.01)
Depth < 0.1: permanent drift > 0.05
Recovery time scales inversely with Integrity.
