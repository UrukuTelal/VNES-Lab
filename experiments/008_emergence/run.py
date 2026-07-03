"""008_emergence — Many-body PSV self-organization.

Hypothesis: N entities with random PSVs self-organize into clusters.
Cluster count < sqrt(N). Modularity > 0.3.
"""

import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from lib.psv_core import PillarState, MetricLogger, NUM_PILLARS

SEED = 42
TIMESTEPS = 200
POPULATIONS = [10, 20, 50, 100]
COUPLING = 0.05


def run():
    random.seed(SEED)
    logger = MetricLogger(
        base_dir=os.path.join(os.path.dirname(__file__), "metrics"),
        columns=["population", "cluster_count", "modularity", "intra_sim", "inter_sim"],
    )

    for pop in POPULATIONS:
        entities = [PillarState.random(seed=SEED + i) for i in range(pop)]
        n = len(entities)

        for t in range(TIMESTEPS):
            for i in range(n):
                for j in range(n):
                    if i == j:
                        continue
                    sim = entities[i].similarity(entities[j])
                    pull = (entities[i].theta[3] - entities[j].theta[3]) * COUPLING * sim
                    for k in range(NUM_PILLARS):
                        entities[i].theta[k] -= pull * 0.01
                        entities[j].theta[k] += pull * 0.01
                    entities[i].theta[3] -= pull * 0.5 * sim
                    entities[j].theta[3] += pull * 0.5 * sim
            for e in entities:
                e.clamp()

        # Compute similarity matrix
        sim_matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                sim_matrix[i][j] = entities[i].similarity(entities[j])

        # Simple clustering: group by >0.6 similarity
        assigned = [-1] * n
        cluster_id = 0
        for i in range(n):
            if assigned[i] >= 0:
                continue
            assigned[i] = cluster_id
            for j in range(i + 1, n):
                if assigned[j] >= 0:
                    continue
                if sim_matrix[i][j] > 0.6:
                    assigned[j] = cluster_id
            cluster_id += 1

        cluster_count = cluster_id
        clusters = {c: [i for i, a in enumerate(assigned) if a == c] for c in range(cluster_count)}

        # Intra/inter cluster similarity
        intra_sim = 0.0
        intra_count = 0
        inter_sim = 0.0
        inter_count = 0
        for i in range(n):
            for j in range(i + 1, n):
                if assigned[i] == assigned[j]:
                    intra_sim += sim_matrix[i][j]
                    intra_count += 1
                else:
                    inter_sim += sim_matrix[i][j]
                    inter_count += 1
        intra_sim /= max(intra_count, 1)
        inter_sim /= max(inter_count, 1)

        # Simple modularity score
        total_sim = sum(sim_matrix[i][j] for i in range(n) for j in range(i + 1, n))
        mod = 0.0
        for c in range(cluster_count):
            members = clusters[c]
            in_sum = sum(sim_matrix[i][j] for i in members for j in members if i < j)
            out_sum = sum(sim_matrix[i][j] for i in members for j in range(n) if j not in members)
            mod += (in_sum - out_sum) / max(total_sim, 1e-6)
        mod /= max(cluster_count, 1)

        logger.log(pop, cluster_count, mod, intra_sim, inter_sim)
        print(f"  Pop={pop:>4}: {cluster_count} clusters, mod={mod:.3f}, intra={intra_sim:.3f}, inter={inter_sim:.3f}")

    path = logger.save("emergence.csv")
    print(f"\nSaved: {path}")

    print(f"\n=== EMERGENCE RESULTS ===")
    for row in logger.rows:
        pop, cc, mod, intra, inter = row
        ratio = intra / max(inter, 1e-6)
        marker = " [OK]" if cc < math.sqrt(pop) and mod > 0.3 and ratio > 2.0 else ""
        print(f"Pop={pop:>4}: #clusters={cc:>3} mod={mod:.3f} intra/inter={ratio:.2f}{marker}")

    passed = all(
        r[1] < math.sqrt(r[0]) and r[2] > 0.3 and r[3] > 2.0 * r[4]
        for r in logger.rows
    )
    verdict = "PASS" if passed else "FAIL"
    print(f"\nVerdict: {verdict}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        axes[0].plot([r[0] for r in logger.rows], [r[1] for r in logger.rows], "bo-", linewidth=2)
        axes[0].plot(
            [r[0] for r in logger.rows],
            [math.sqrt(r[0]) for r in logger.rows],
            "r--", alpha=0.5, label="sqrt(N) upper bound"
        )
        axes[0].set_xlabel("Population")
        axes[0].set_ylabel("Cluster Count")
        axes[0].set_title("Emergent Clusters vs Population")
        axes[0].grid(True)
        axes[0].legend()

        pop_labels = [r[0] for r in logger.rows]
        x = range(len(logger.rows))
        axes[1].plot(x, [r[3] for r in logger.rows], "go-", label="Intra-cluster")
        axes[1].plot(x, [r[4] for r in logger.rows], "ro-", label="Inter-cluster")
        axes[1].set_xticks(x)
        axes[1].set_xticklabels([str(int(p)) for p in pop_labels])
        axes[1].set_xlabel("Population")
        axes[1].set_ylabel("Avg Similarity")
        axes[1].set_title("Intra vs Inter-Cluster Similarity")
        axes[1].legend()
        axes[1].grid(True)

        plt.tight_layout()
        vis_path = os.path.join(os.path.dirname(__file__), "visualizations", "emergence.png")
        plt.savefig(vis_path, dpi=150)
        plt.close()
        print(f"Saved: {vis_path}")
    except ImportError:
        print("(matplotlib not available)")

    return verdict


if __name__ == "__main__":
    run()
