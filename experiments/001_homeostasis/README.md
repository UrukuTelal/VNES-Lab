# 001 — Homeostasis: Pillar Equilibrium Under Perturbation

## Hypothesis
A PSV entity subjected to periodic Harmonic perturbation will maintain
equilibrium (return to baseline within tolerance) via natural damping,
provided the perturbation amplitude stays below the entity's Resistance
and Willpower thresholds.

## Method
1. Initialize entity with neutral PSV (theta_i = PI/2 for all i)
2. Apply sinusoidal perturbation to a target pillar at varying amplitudes
3. Measure settling time (steps to return within 5% of baseline)
4. Sweep amplitude from 0.1 to 1.0 in 10 steps
5. Repeat for Resistance values [0.1, 0.5, 0.9]

## Metrics
- perturbation_amplitude
- resistance_level
- settling_time
- overshoot_ratio
- final_drift (bias after settling)

## Expected Result
Higher Resistance → faster settling, lower overshoot.
Amplitudes exceeding Willpower cause permanent drift.
