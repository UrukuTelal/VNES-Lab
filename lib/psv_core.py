"""psv_core.py — Pillar State Vector mathematics for experimental validation.

Pure Python reimplementation of the Van Nueman Engine's core math,
suitable for controlled experiments without needing the full C++ build.
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import csv
import os


# --- Constants ---
NUM_PILLARS = 16
PI = math.pi
TAU = 2 * PI


# --- Pillar Names ---
PILLAR_NAMES = [
    "Awareness", "Willpower", "Force", "Influence",
    "Resistance", "Integrity", "Cohesion", "Relation",
    "Presence", "Warmth", "Memory", "Attraction",
    "Harm", "Distortion", "Flux", "Depth",
]


# --- Data Classes ---

@dataclass
class PillarState:
    """16-dimensional Pillar State Vector (PSV).
    Each pillar is a Bloch sphere angle theta in [0, PI].
    """
    theta: List[float] = field(default_factory=lambda: [PI / 2] * NUM_PILLARS)
    phi: List[float] = field(default_factory=lambda: [0.0] * NUM_PILLARS)

    @classmethod
    def random(cls, seed: Optional[int] = None) -> "PillarState":
        if seed is not None:
            random.seed(seed)
        return cls(
            theta=[random.random() * PI for _ in range(NUM_PILLARS)],
            phi=[random.random() * TAU for _ in range(NUM_PILLARS)],
        )

    @classmethod
    def from_values(cls, theta: List[float], phi: Optional[List[float]] = None) -> "PillarState":
        if phi is None:
            phi = [0.0] * NUM_PILLARS
        return cls(theta=theta[:], phi=phi[:])

    def copy(self) -> "PillarState":
        return PillarState(theta=self.theta[:], phi=self.phi[:])

    def clamp(self, soft: bool = True):
        for i in range(NUM_PILLARS):
            # Soft boundary damping before hard clamp
            if soft and self.theta[i] > PI * 0.95:
                self.theta[i] -= (self.theta[i] - PI * 0.95) * 0.25
            elif soft and self.theta[i] < 0.05:
                self.theta[i] += (0.05 - self.theta[i]) * 0.25
            self.theta[i] = max(0.0, min(PI, self.theta[i]))
            self.phi[i] = self.phi[i] % TAU

    def magnitude(self) -> float:
        return math.sqrt(sum(t * t for t in self.theta)) / NUM_PILLARS

    def similarity(self, other: "PillarState") -> float:
        dot = sum(self.theta[i] * other.theta[i] for i in range(NUM_PILLARS))
        n1 = math.sqrt(sum(t * t for t in self.theta))
        n2 = math.sqrt(sum(t * t for t in other.theta))
        if n1 < 1e-12 or n2 < 1e-12:
            return 0.0
        return dot / (n1 * n2)

    def distance(self, other: "PillarState") -> float:
        return math.sqrt(sum((self.theta[i] - other.theta[i]) ** 2 for i in range(NUM_PILLARS)))

    def entropy(self) -> float:
        p = [t / PI for t in self.theta]
        s = 0.0
        for pi in p:
            pi = max(1e-12, min(1 - 1e-12, pi))
            s -= pi * math.log2(pi) + (1 - pi) * math.log2(1 - pi)
        return s / NUM_PILLARS

    def __repr__(self) -> str:
        return f"PSV({[f'{t:.3f}' for t in self.theta[:4]]}...)"


@dataclass
class Entity:
    """A simulated entity with PSV state."""
    uid: int
    state: PillarState = field(default_factory=PillarState)
    target: Optional[PillarState] = None
    scale: int = 0  # Scale exponent (0 = entity, 1 = system, etc.)

    def tick(self, dt: float = 1.0):
        if self.target is None:
            return
        for i in range(NUM_PILLARS):
            diff = self.target.theta[i] - self.state.theta[i]
            self.state.theta[i] += diff * 0.1 * dt
        self.state.clamp()


@dataclass
class MetricLogger:
    """Logs structured metrics to CSV."""
    base_dir: str
    columns: List[str]
    rows: List[List[float]] = field(default_factory=list)

    def log(self, *values):
        self.rows.append(list(values))

    def save(self, filename: str):
        os.makedirs(self.base_dir, exist_ok=True)
        path = os.path.join(self.base_dir, filename)
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(self.columns)
            writer.writerows(self.rows)
        return path


# --- Bloch Sphere Operations ---

def rotate_pillar(state: PillarState, idx: int, delta_theta: float, delta_phi: float = 0.0):
    """Rotate a single pillar by delta_theta (and optionally delta_phi)."""
    state.theta[idx] = (state.theta[idx] + delta_theta) % PI
    state.phi[idx] = (state.phi[idx] + delta_phi) % TAU


def apply_harm(actor: PillarState, subject: PillarState, target_pillar: int,
               interaction_matrix: Optional[List[List[float]]] = None) -> float:
    """TRANSFORM algorithm: Harm rotates, doesn't delete."""
    alignment = actor.similarity(subject)
    harm_torque = actor.theta[12]  # Harm pillar
    influence_force = actor.theta[3]  # Influence pillar
    willpower = subject.theta[1] + 0.01  # Willpower (avoid div by zero)
    depth = subject.theta[15] + 0.01  # Depth buffer

    delta_theta = (harm_torque * influence_force * alignment) / (willpower * depth)

    if delta_theta > subject.theta[1]:
        subject.theta[15] -= (delta_theta - subject.theta[1]) * 0.1
        rotate_pillar(subject, 5, delta_theta * (1 - subject.theta[4]))
        rotate_pillar(subject, 0, delta_theta * subject.theta[13])
    else:
        rotate_pillar(subject, 8, delta_theta * 0.01)

    subject.clamp()
    return delta_theta


# --- WHT (Walsh-Hadamard Transform) ---

def wht_forward(signal: List[float]) -> List[float]:
    n = len(signal)
    h = signal[:]
    step = 1
    while step < n:
        for i in range(0, n, step * 2):
            for j in range(i, i + step):
                u = h[j]
                v = h[j + step]
                h[j] = u + v
                h[j + step] = u - v
        step *= 2
    return h


def wht_inverse(transform: List[float]) -> List[float]:
    n = len(transform)
    h = wht_forward(transform)
    return [x / n for x in h]


# --- FLL Graph (lightweight) ---

@dataclass
class FLLNode:
    uid: int
    embedding: List[float]  # 32D WHT embedding
    edges: List[Tuple[int, float]] = field(default_factory=list)  # (target_uid, weight)


class FLLGraph:
    """Fractal Latent Learning graph — similarity-based edge weighting."""
    def __init__(self):
        self.nodes: dict[int, FLLNode] = {}

    def add_node(self, uid: int, embedding: List[float]) -> FLLNode:
        node = FLLNode(uid=uid, embedding=embedding)
        self.nodes[uid] = node
        return node

    def cosine_sim(self, a: List[float], b: List[float]) -> float:
        dot = sum(ai * bi for ai, bi in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na < 1e-12 or nb < 1e-12:
            return 0.0
        return dot / (na * nb)

    def connect(self, uid_a: int, uid_b: int, weight: Optional[float] = None):
        if weight is None:
            emb_a = self.nodes[uid_a].embedding
            emb_b = self.nodes[uid_b].embedding
            weight = self.cosine_sim(emb_a, emb_b)
        self.nodes[uid_a].edges.append((uid_b, weight))
        self.nodes[uid_b].edges.append((uid_a, weight))

    def diameter(self) -> float:
        if len(self.nodes) < 2:
            return 0.0
        # Approximate diameter via greedy BFS
        max_dist = 0.0
        uids = list(self.nodes.keys())
        for start in uids[:min(10, len(uids))]:
            visited = {start: 0.0}
            queue = [start]
            while queue:
                cur = queue.pop(0)
                for neighbor, w in self.nodes[cur].edges:
                    if neighbor not in visited:
                        visited[neighbor] = visited[cur] + 1.0
                        queue.append(neighbor)
            if visited:
                max_dist = max(max_dist, max(visited.values()))
        return max_dist


# --- Hopf-PID Controller ---

class HopfPID:
    """512D thought space -> 32D manifest via Hopf fibration approximation."""
    def __init__(self, kp: float = 0.5, ki: float = 0.1, kd: float = 0.05):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral = [0.0] * 16
        self.prev_error = [0.0] * 16

    def compute(self, current: PillarState, target: PillarState, dt: float = 1.0) -> PillarState:
        correction = current.copy()
        for i in range(NUM_PILLARS):
            error = target.theta[i] - current.theta[i]
            self.integral[i] += error * dt
            # Anti-windup: clamp integral to prevent overshoot buildup
            max_integral = PI / max(self.ki, 1e-12)
            self.integral[i] = max(-max_integral, min(max_integral, self.integral[i]))
            derivative = (error - self.prev_error[i]) / max(dt, 1e-12)
            # Low-pass filter on derivative to reduce noise amplification
            derivative *= 0.7
            output = self.kp * error + self.ki * self.integral[i] + self.kd * derivative
            correction.theta[i] += output * dt
            self.prev_error[i] = error
        correction.clamp()
        return correction


# --- Scale Router ---

def scale_attention(state: PillarState, current_scale: int, target_scale: int) -> float:
    """Attenuation factor for cross-scale influence."""
    delta = abs(target_scale - current_scale)
    return 1.0 / (1.0 + delta * 0.5)


def project_across_scales(state: PillarState, from_scale: int, to_scale: int) -> PillarState:
    """Project a PSV from one scale to another using fractal aggregation."""
    factor = 2 ** ((to_scale - from_scale) / 2.0)
    return PillarState(
        theta=[max(0.0, min(PI, t * factor)) for t in state.theta],
        phi=state.phi[:],
    )
