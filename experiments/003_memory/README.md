# 003 — Memory: WHT/FLL Recall and Decay Patterns

## Hypothesis
A Walsh-Hadamard compressed memory trace can be reliably recalled
if queried within the FLL graph's similarity threshold. Memory
fidelity decays exponentially with the number of intervening
overwrites.

## Method
1. Generate 32D WHT memory embeddings
2. Store in FLL graph with timestamp
3. Query with noisy probe at varying similarity levels
4. Measure recall precision vs noise level
5. Test memory decay after N overwrites

## Metrics
- noise_level (probe cosine similarity to original)
- recall_precision
- overwrite_count
- memory_fidelity
- graph_diameter vs node count

## Expected Result
Recall precision > 0.9 at similarity > 0.7.
Fidelity decays ~exponentially with overwrites.
Graph diameter grows logarithmically with node count.
