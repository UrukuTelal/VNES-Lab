# 005 — Multi-Agent: Interaction Dynamics

## Hypothesis
Two PSV entities with coupled pillars (via Influence/Relation) will
synchronize their PSV states over time, with synchronization rate
proportional to their coupling strength and inversely proportional
to their Willpower difference.

## Method
1. Initialize two entities with random PSVs
2. Apply mutual Influence coupling each timestep
3. Sweep coupling strength and Willpower difference
4. Measure phase synchronization index and convergence time

## Metrics
- coupling_strength
- willpower_difference
- sync_index (cosine similarity over time)
- convergence_time
- energy_transfer (net pillar movement)

## Expected Result
Sync_index > 0.9 when coupling > 0.3 and Willpower diff < 0.2.
Energy transfer is directional (higher Influence → lower).
