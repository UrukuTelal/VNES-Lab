# 002 — Navigation: Attractor State Seeking

## Hypothesis
An entity with a defined target PSV will converge toward it via
proportional correction, with convergence rate determined by
the Flux pillar (throughput/bandwidth).

## Method
1. Initialize entity at random PSV with known target
2. Apply proportional correction each timestep
3. Sweep Flux pillar values [0.1, 0.3, 0.7, 0.9]
4. Measure convergence time and path efficiency

## Metrics
- flux_level
- initial_distance
- convergence_time
- path_efficiency (direct distance / actual path length)
- steady_state_error

## Expected Result
Higher Flux → faster convergence.
Convergence time scales linearly with initial distance.
Path efficiency degrades with extremely high Flux (overshoot).
