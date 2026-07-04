"""rlaaer config — data source URLs, agent endpoints, pipeline defaults."""

import os

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))

# ── Data Source Endpoints ───────────────────────────────────
DATA_SOURCES = {
    "arxiv": {
        "base_url": "https://export.arxiv.org/api/query",
        "max_results_default": 10,
        "tier": 1,
    },
    "semantic_scholar": {
        "base_url": "https://api.semanticscholar.org/graph/v1",
        "tier": 1,
    },
    "nasa": {
        "base_url": "https://api.nasa.gov",
        "tier": 1,
        "api_key_env": "NASA_API_KEY",
    },
    "noaa": {
        "base_url": "https://www.ncdc.noaa.gov/cdo-web/api/v2",
        "tier": 1,
        "api_key_env": "NOAA_API_KEY",
    },
    "census": {
        "base_url": "https://api.census.gov/data",
        "tier": 1,
        "api_key_env": "CENSUS_API_KEY",
    },
    "kaggle": {
        "base_url": "https://www.kaggle.com/api/v1",
        "tier": 2,
        "api_key_env": "KAGGLE_API_KEY",
    },
    "uci": {
        "base_url": "https://archive.ics.uci.edu/ml/datasets",
        "tier": 2,
    },
    "web": {
        "tier": 3,
        "note": "semantic extraction only, no direct parameter injection",
    },
}

# ── Engine Connection ───────────────────────────────────────
ENGINE = {
    "rest_api": "http://localhost:8080",
    "websocket": "ws://localhost:8081",
    "llm_bridge": "http://localhost:11434",
    "llm_timeout_sec": 120,
    "pillar_bridge": "http://localhost:8888",
    "startup_timeout_sec": 30,
    "headless_mode": True,
}

# ── Council Defaults ────────────────────────────────────────
COUNCIL = {
    "pillar_required_approvals": 12,
    "pillar_total": 16,
    "adversarial_max_revision_rounds": 3,
    "default_alpha": 0.05,
    "default_power": 0.80,
    "default_minimum_effect_size": 0.30,
}

# ── Pipeline Defaults ───────────────────────────────────────
PIPELINE = {
    "checkpoint_interval_ticks": 1000,
    "rollback_on_failure": True,
    "max_duration_minutes": 30,
    "cache_dir": os.path.join(REPO_ROOT, "rlaaer", "data", "cache"),
}

# ── Experiment Lifecycle ────────────────────────────────────
STATUS_FLOW = [
    "draft",
    "registered",
    "executing",
    "review",
    "published",
    "rejected",
]

SPEC_FILENAME = "spec.yaml"
