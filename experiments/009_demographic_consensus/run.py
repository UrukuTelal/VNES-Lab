"""009_demographic_consensus — Bounded-confidence opinion dynamics with Census priors.

Hypothesis: If entity population scale and demographic diversity follow real
Census distributions, then consensus convergence time scales logarithmically
with diversity entropy and is modulated by scale attention.
"""
import csv
import math
import os
import random
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from lib.psv_core import MetricLogger

SEED = 42
TIMESTEPS = 200
CONFIDENCE_BOUND = 0.25
SCALE_LEVELS = [0, 1, 2, 3, 4]
ENTROPY_TARGETS = [0.1, 0.3, 0.5, 0.7, 0.9]
NUM_TRIALS = 5

CENSUS_FPATH = os.path.join(os.path.dirname(__file__), "data", "census_regions.csv")

# Regional opinion centers (baseline position on a hypothetical issue)
REGION_OPINIONS = {
    "Northeast": 0.65,
    "Midwest":   0.52,
    "South":     0.38,
    "West":      0.58,
}


def assign_scales(pop_scale, n_entities):
    """Assign each entity a sub-scale for cross-level attention effects."""
    if n_entities <= 1:
        return [pop_scale]
    max_sub = max(0, pop_scale - 1)
    scales = []
    per_level = max(1, n_entities // (pop_scale + 1))
    for s in range(pop_scale + 1):
        scales.extend([s] * per_level)
    scales = scales[:n_entities]
    while len(scales) < n_entities:
        scales.append(pop_scale)
    random.shuffle(scales)
    return scales


class CensusLoader:
    def __init__(self, path=CENSUS_FPATH):
        self.regions = {}
        self.proportions = {}
        self._load(path)

    def _load(self, path):
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row["region"]
                self.regions[name] = float(row["proportion"])
        total = sum(self.regions.values())
        self.proportions = {k: v / total for k, v in self.regions.items()}

    def region_names(self):
        return list(self.regions.keys())

    def sample_distribution(self, target_entropy):
        probs = list(self.proportions.values())
        n = len(probs)
        max_h = -sum((1 / n) * math.log2(1 / n) for _ in range(n))
        mix = target_entropy / max_h if max_h > 0 else 0
        mix = max(0.0, min(1.0, mix))
        blended = [(1 - mix) * p + mix * (1 / n) for p in probs]
        s = sum(blended)
        return [b / s for b in blended]

    def realized_entropy(self, counts):
        total = sum(counts)
        if total == 0:
            return 0.0
        probs = [c / total for c in counts]
        return -sum(p * math.log2(p) if p > 0 else 0 for p in probs)


class Agent:
    """Bounded-confidence opinion agent with scale and region affiliation."""
    def __init__(self, uid, scale_level, opinion, region):
        self.uid = uid
        self.scale = scale_level
        self.opinion = opinion
        self.region = region
        self.attenuation = 1.0

    def influence(self, others, coupling=0.1):
        total_delta = 0.0
        total_atten = 0.0
        count = 0
        for other in others:
            if other is self:
                continue
            diff = abs(self.opinion - other.opinion)
            if diff < CONFIDENCE_BOUND:
                atten = 1.0 / (1.0 + 0.5 * abs(self.scale - other.scale))
                total_delta += (other.opinion - self.opinion) * coupling * atten
                total_atten += atten
                count += 1
        self.attenuation = total_atten / max(count, 1)
        return total_delta


def run_condition(pop_scale, ent_target, trial_seed, census):
    random.seed(trial_seed)
    n_entities = max(1, 2 ** pop_scale)
    dist = census.sample_distribution(ent_target)
    region_names = census.region_names()

    agents = []
    counts = [0] * len(region_names)
    scales = assign_scales(pop_scale, n_entities)
    for uid in range(n_entities):
        region_idx = random.choices(range(len(region_names)), weights=dist, k=1)[0]
        counts[region_idx] += 1
        region = region_names[region_idx]
        center = REGION_OPINIONS[region]
        opinion = max(0.0, min(1.0, center + random.uniform(-0.25, 0.25)))
        agents.append(Agent(uid, scales[uid], opinion, region))

    realized_h = census.realized_entropy(counts)
    converged_at = TIMESTEPS
    prev_opinions = [a.opinion for a in agents]

    for t in range(TIMESTEPS):
        for a in agents:
            a.opinion += a.influence(agents)
            a.opinion = max(0.0, min(1.0, a.opinion))

        if converged_at == TIMESTEPS and t % 5 == 0:
            max_drift = max(abs(a.opinion - prev_opinions[i])
                           for i, a in enumerate(agents))
            if max_drift < 0.005:
                converged_at = t
            prev_opinions = [a.opinion for a in agents]

    final_opinions = [a.opinion for a in agents]
    mean_opinion = sum(final_opinions) / len(final_opinions)
    opinion_var = sum((o - mean_opinion) ** 2 for o in final_opinions) / len(final_opinions)

    mean_atten = sum(a.attenuation for a in agents) / max(len(agents), 1)

    return {
        "convergence_time": converged_at,
        "opinion_variance": opinion_var,
        "mean_opinion": mean_opinion,
        "attenuation_factor": mean_atten,
        "demographic_entropy_realized": realized_h,
    }


def run():
    random.seed(SEED)
    census = CensusLoader()
    logger = MetricLogger(
        base_dir=os.path.join(os.path.dirname(__file__), "metrics"),
        columns=[
            "population_scale", "diversity_entropy", "trial",
            "convergence_time", "opinion_variance", "mean_opinion",
            "attenuation_factor", "demographic_entropy_realized",
        ],
    )

    trial = 0
    for pop_scale in SCALE_LEVELS:
        for ent_target in ENTROPY_TARGETS:
            for rep in range(NUM_TRIALS):
                trial_seed = SEED + trial
                result = run_condition(pop_scale, ent_target, trial_seed, census)
                logger.log(
                    float(pop_scale), float(ent_target), float(rep),
                    float(result["convergence_time"]),
                    float(result["opinion_variance"]),
                    float(result["mean_opinion"]),
                    float(result["attenuation_factor"]),
                    float(result["demographic_entropy_realized"]),
                )
                trial += 1

    path = logger.save("demographic_consensus.csv")
    print(f"Saved: {path} ({trial} trials)")

    print(f"\n=== DEMOGRAPHIC CONSENSUS RESULTS ===")
    header = f"{'Scale':>6} {'Entropy':>8} {'Trial':>6} {'Conv@':>6} {'Var':>7} {'Mean':>6} {'Atten':>6}"
    print(header)
    print("-" * 55)
    for row in logger.rows:
        ps, et, tr, ct, var, mn, att, deh = row
        marker = " *" if ct >= TIMESTEPS else ""
        print(f"{ps:>6.0f} {et:>8.2f} {tr:>6.0f} {ct:>6.0f} {var:>7.5f} {mn:>6.3f} {att:>6.3f}{marker}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 3, figsize=(16, 5))

        for ps in SCALE_LEVELS:
            sub = [r for r in logger.rows if abs(r[0] - ps) < 0.1]
            xs = [r[1] for r in sub]
            ys = [r[3] for r in sub]
            axes[0].scatter(xs, ys, label=f"Scale={ps}", alpha=0.6, s=20)
        axes[0].set_xlabel("Diversity Entropy")
        axes[0].set_ylabel("Convergence Time")
        axes[0].set_title("Convergence Time vs Entropy")
        axes[0].legend(fontsize=8)

        for ps in SCALE_LEVELS:
            sub = [r for r in logger.rows if abs(r[0] - ps) < 0.1]
            xs = [r[1] for r in sub]
            ys = [r[4] for r in sub]
            axes[1].scatter(xs, ys, label=f"Scale={ps}", alpha=0.6, s=20)
        axes[1].set_xlabel("Diversity Entropy")
        axes[1].set_ylabel("Opinion Variance")
        axes[1].set_title("Residual Variance vs Entropy")
        axes[1].legend(fontsize=8)

        for ps in SCALE_LEVELS:
            sub = [r for r in logger.rows if abs(r[0] - ps) < 0.1]
            xs = [r[1] for r in sub]
            ys = [r[6] for r in sub]
            axes[2].scatter(xs, ys, label=f"Scale={ps}", alpha=0.6, s=20)
        axes[2].set_xlabel("Diversity Entropy")
        axes[2].set_ylabel("Attenuation")
        axes[2].set_title("Scale Attention vs Entropy")
        axes[2].legend(fontsize=8)

        plt.tight_layout()
        vis_dir = os.path.join(os.path.dirname(__file__), "visualizations")
        os.makedirs(vis_dir, exist_ok=True)
        plt.savefig(os.path.join(vis_dir, "demographic_consensus.png"), dpi=150)
        print(f"Saved: {vis_dir}/demographic_consensus.png")
    except ImportError:
        print("matplotlib not available — skipping visualization")


if __name__ == "__main__":
    run()
