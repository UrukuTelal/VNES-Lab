"""003_memory — WHT/FLL recall and decay patterns.

Hypothesis: WHT-compressed memory can be recalled above 0.9 precision
at similarity > 0.7. Fidelity decays exponentially with overwrites.
"""

import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from lib.psv_core import FLLGraph, wht_forward, MetricLogger

SEED = 42
EMBEDDING_DIM = 32
N_MEMORIES = 50
NOISE_LEVELS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
QUERIES_PER_NOISE = 20
OVERWRITE_CYCLES = 20


def random_embedding(seed: int) -> list[float]:
    random.seed(seed)
    raw = [random.random() for _ in range(EMBEDDING_DIM)]
    wht = wht_forward(raw)
    mag = math.sqrt(sum(x * x for x in wht))
    return [x / mag for x in wht] if mag > 0 else wht


def add_noise(embedding: list[float], noise_level: float) -> list[float]:
    n = len(embedding)
    noise = [random.gauss(0, noise_level / math.sqrt(n)) for _ in range(n)]
    return [e + noise[i] for i, e in enumerate(embedding)]


def run():
    random.seed(SEED)
    logger = MetricLogger(
        base_dir=os.path.join(os.path.dirname(__file__), "metrics"),
        columns=["noise_level", "recall_precision", "overwrite_count", "memory_fidelity", "graph_diameter"],
    )

    # Build memory graph
    graph = FLLGraph()
    memories = []
    for i in range(N_MEMORIES):
        emb = random_embedding(SEED + i)
        graph.add_node(i, emb)
        memories.append((i, emb))

    # Connect similar memories
    for i in range(N_MEMORIES):
        for j in range(i + 1, N_MEMORIES):
            sim = graph.cosine_sim(memories[i][1], memories[j][1])
            if sim > 0.5:
                graph.connect(i, j, weight=sim)

    # Noise sweep — query each memory with noise
    for noise_level in NOISE_LEVELS:
        correct = 0
        for q in range(min(QUERIES_PER_NOISE, N_MEMORIES)):
            idx, original = memories[q]
            probe = add_noise(original, noise_level)

            # Find nearest neighbor
            best_sim = -1.0
            best_idx = -1
            for nid, node in graph.nodes.items():
                sim = graph.cosine_sim(probe, node.embedding)
                if sim > best_sim:
                    best_sim = sim
                    best_idx = nid
            if best_idx == idx:
                correct += 1

        precision = correct / min(QUERIES_PER_NOISE, N_MEMORIES)
        logger.log(noise_level, precision, 0, 1.0 - noise_level, graph.diameter())

    # Overwrite decay test
    for overwrites in range(1, OVERWRITE_CYCLES + 1):
        nid = overwrites % N_MEMORIES
        new_emb = random_embedding(SEED + 1000 + overwrites)
        graph.nodes[nid].embedding = new_emb

        correct = 0
        trials = min(10, N_MEMORIES)
        for q in range(trials):
            idx, original = memories[q]
            probe = add_noise(original, 0.1)

            best_sim = -1.0
            best_idx = -1
            for nid, node in graph.nodes.items():
                sim = graph.cosine_sim(probe, node.embedding)
                if sim > best_sim:
                    best_sim = sim
                    best_idx = nid
            if best_idx == idx:
                correct += 1

        fidelity = correct / trials
        logger.log(0.1, fidelity, overwrites, fidelity, graph.diameter())

    path = logger.save("memory.csv")
    print(f"Saved: {path}")

    print(f"\n=== MEMORY RESULTS ===")
    noise_rows = [r for r in logger.rows if r[2] == 0]
    print(f"{'Noise':>6} {'Precision':>10}")
    for row in noise_rows:
        print(f"{row[0]:>6.1f} {row[1]:>10.4f}")

    overwrite_rows = [r for r in logger.rows if r[2] > 0]
    print(f"\nOverwrite decay (sample):")
    print(f"{'Overwrites':>10} {'Fidelity':>10}")
    for row in overwrite_rows[::3]:
        print(f"{row[2]:>10} {row[3]:>10.4f}")

    precision_07 = 0.0
    for row in noise_rows:
        if abs(row[0] - 0.3) < 0.01:
            precision_07 = row[1]
            break
    verdict = "PASS" if precision_07 >= 0.9 else "FAIL"
    print(f"\nVerdict: {verdict}")
    print(f"  Precision at noise=0.3: {precision_07:.4f} (threshold: 0.9)")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        axes[0].plot([r[0] for r in noise_rows], [r[1] for r in noise_rows], marker="o", linewidth=2)
        axes[0].set_xlabel("Noise Level")
        axes[0].set_ylabel("Recall Precision")
        axes[0].set_title("Recall Precision vs Noise")
        axes[0].axhline(y=0.9, color="g", linestyle="--", alpha=0.5, label="0.9 threshold")
        axes[0].grid(True)
        axes[0].legend()

        if overwrite_rows:
            axes[1].plot([r[2] for r in overwrite_rows], [r[3] for r in overwrite_rows], "r-", linewidth=1)
            axes[1].set_xlabel("Overwrite Count")
            axes[1].set_ylabel("Memory Fidelity")
            axes[1].set_title("Memory Decay via Overwrites")
            axes[1].grid(True)

        plt.tight_layout()
        vis_path = os.path.join(os.path.dirname(__file__), "visualizations", "memory.png")
        plt.savefig(vis_path, dpi=150)
        plt.close()
        print(f"Saved: {vis_path}")
    except ImportError:
        print("(matplotlib not available)")

    return verdict


if __name__ == "__main__":
    run()
