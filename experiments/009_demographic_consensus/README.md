# 009 — Demographic Scaling of Consensus Formation

## Hypothesis
If entity population size follows real Census demographic distributions,
then consensus convergence time scales logarithmically with population
diversity entropy, modulated by the Scale Router attention attenuation mechanism.

## Method
1. Load US Census regional population proportions (Northeast 17.1%, Midwest 20.7%, South 38.1%, West 24.1%).
2. For each condition: generate 2^k entities where k = population_scale [0..4].
3. Assign each entity a demographic region sampled from a distribution with target entropy E [0.1..0.9].
4. Initialize each entity's PSV with a region-specific target state (cultural baseline).
5. Run for 1000 timesteps, measuring pairwise PSV similarity across entities.
6. Convergence defined as mean similarity >= 0.85 threshold.
7. Attenuation factor computed via scale_attention() for each cross-scale interaction.

## Independent Variables
- population_scale [0, 1, 2, 3, 4] — entity count = 2^k
- diversity_entropy [0.1, 0.3, 0.5, 0.7, 0.9] — target Shannon entropy

## Metrics
- convergence_time: timesteps to reach consensus (or 1000 if never)
- final_coherence: mean pairwise cosine similarity at end
- convergence_reached: boolean
- post_convergence_drift: std dev of similarity after convergence
- attenuation_factor: mean Scale Router attention value
- demographic_entropy_realized: actual entropy of realized assignments

## Expected Result
- Higher diversity entropy → slower convergence (log-linear)
- Higher population scale → lower attenuation → faster consensus
- Interaction: scale moderates entropy effect (more entities buffer diversity)
