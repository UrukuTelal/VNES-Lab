# 004 — Prediction: Hopf-PID Trajectory Forecasting

## Hypothesis
A Hopf-PID controller operating on PSV space can predict the
next-N timesteps of a periodic system with bounded error,
where error scales with prediction horizon and system
nonlinearity.

## Method
1. Generate known periodic PSV trajectories (sine + coupled oscillators)
2. Train Hopf-PID on first 50% of trajectory
3. Predict remaining 50%
4. Measure prediction error vs horizon
5. Sweep PID gain parameters

## Metrics
- prediction_horizon (steps ahead)
- mse (mean squared error per pillar)
- coupling_strength (between pillar oscillators)
- kp_gain
- phase_error (radians)

## Expected Result
MSE < 0.01 for horizon < 20 steps.
Error grows super-linearly with horizon.
Optimal kp ~0.5 across all conditions.
