# 007 — Tool Use: PSV Manipulation of Environment

## Hypothesis
An entity can manipulate environment-state pillars (Force, Influence,
Warmth) to achieve a desired effect on a target entity, with
efficiency proportional to the entity's Awareness (understanding
of the relationship) and inversely to target Resistance.

## Method
1. Entity A attempts to modify Entity B's state via Influence/Force
2. Entity A's Awareness determines action selection accuracy
3. Sweep Awareness [0.1, 0.3, 0.5, 0.7, 0.9]
4. Sweep target Resistance [0.1, 0.3, 0.5]
5. Measure effect magnitude and energy cost

## Metrics
- awareness_level
- target_resistance
- effect_magnitude (delta on target's target pillar)
- energy_cost (sum of absolute delta on actor)
- efficiency (effect / cost)

## Expected Result
Higher Awareness → higher efficiency.
Higher Resistance → lower effect magnitude at same cost.
Optimal Awareness/Resistance ratio ~2:1 for max efficiency.
