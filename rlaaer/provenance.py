"""Provenance — capture the full chain of artifact origins.

Every artifact records:
  spec_hash → git commit → engine version → dataset hashes
                                            → compiler version
                                            → CUDA version
                                            → model version
"""

import hashlib
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from typing import Any

from rlaaer.config import REPO_ROOT


def git_commit() -> str:
    """Return current git commit SHA, or 'unknown' if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=REPO_ROOT,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return "unknown"


def git_branch() -> str:
    """Return current git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=REPO_ROOT,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return "unknown"


def git_dirty() -> bool:
    """Return True if working tree has uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
            cwd=REPO_ROOT,
        )
        return bool(result.stdout.strip())
    except (subprocess.SubprocessError, FileNotFoundError):
        return True  # conservative: assume dirty if can't check


def python_version() -> str:
    return platform.python_version()


def platform_info() -> dict:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": python_version(),
    }


def engine_version() -> str:
    """Query engine version from REST API. Returns 'unknown' if unreachable."""
    try:
        import requests
        from rlaaer.config import ENGINE
        import socket
        host = ENGINE["rest_api"].replace("http://", "").replace("https://", "").split(":")[0]
        port = int(ENGINE["rest_api"].split(":")[-1]) if ":" in ENGINE["rest_api"].split("//")[-1] else 80
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        try:
            s.connect((host, port))
            s.close()
            resp = requests.get(f"{ENGINE['rest_api']}/version", timeout=1)
            if resp.status_code == 200:
                return resp.json().get("version", "unknown")
        except (socket.timeout, ConnectionRefusedError, OSError):
            s.close()
    except Exception:
        pass
    return "unknown"


def cuda_version() -> str:
    """Attempt to read CUDA version from nvcc or version file."""
    try:
        result = subprocess.run(
            ["nvcc", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            match = re.search(r'release (\d+\.\d+)', result.stdout)
            if match:
                return match.group(1)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    # Fallback: environment variable
    return os.environ.get("CUDA_VERSION", "unknown")


def compiler_version() -> str:
    """Detect MSVC or GCC/Clang version."""
    # MSVC
    msvc = os.environ.get("VCToolsVersion") or os.environ.get("VisualStudioVersion")
    if msvc:
        return f"MSVC {msvc}"
    # GCC
    try:
        result = subprocess.run(
            ["gcc", "--version"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            return result.stdout.split("\n")[0].strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    # Clang
    try:
        result = subprocess.run(
            ["clang", "--version"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            return result.stdout.split("\n")[0].strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return "unknown"


def spec_hash(spec: dict) -> str:
    """Deterministic SHA256 of a canonicalized spec."""
    import yaml
    canonical = yaml.dump(spec, default_flow_style=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ProvenanceTracker:
    """Collects and records full provenance for an experiment execution."""

    def __init__(self):
        self._cache = {}

    def capture(self, spec: dict | None = None) -> dict:
        """Capture full provenance snapshot."""
        record = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "git": {
                "commit": git_commit(),
                "branch": git_branch(),
                "dirty": git_dirty(),
                "repo_root": REPO_ROOT,
            },
            "platform": platform_info(),
            "toolchain": {
                "cuda": cuda_version(),
                "compiler": compiler_version(),
            },
            "engine": {
                "version": engine_version(),
            },
        }

        if spec is not None:
            record["spec"] = {
                "hash": spec_hash(spec),
                "id": spec.get("experiment", {}).get("id", "unknown"),
                "title": spec.get("experiment", {}).get("title", ""),
            }

        return record

    def merge_dataset_hashes(self, provenance: dict, dataset_hashes: list[dict]) -> dict:
        """Merge dataset hashes into provenance record."""
        provenance["datasets"] = dataset_hashes
        return provenance

    def to_appendix(self, provenance: dict) -> str:
        """Render provenance as a manuscript appendix section."""
        lines = [
            "## Provenance Appendix\n",
            "| Component | Value |",
            "|-----------|-------|",
        ]

        git_info = provenance.get("git", {})
        lines.append(f"| Git Commit | `{git_info.get('commit', 'unknown')}` |")
        lines.append(f"| Git Branch | {git_info.get('branch', 'unknown')} |")
        lines.append(f"| Working Tree Dirty | {git_info.get('dirty', 'unknown')} |")

        toolchain = provenance.get("toolchain", {})
        lines.append(f"| CUDA Version | {toolchain.get('cuda', 'unknown')} |")
        lines.append(f"| Compiler | {toolchain.get('compiler', 'unknown')} |")

        engine = provenance.get("engine", {})
        lines.append(f"| Engine Version | {engine.get('version', 'unknown')} |")

        plat = provenance.get("platform", {})
        lines.append(f"| OS | {plat.get('system', 'unknown')} {plat.get('release', '')} |")
        lines.append(f"| Python | {plat.get('python', 'unknown')} |")

        spec_info = provenance.get("spec", {})
        if spec_info:
            lines.append(f"| Spec Hash | `{spec_info.get('hash', 'unknown')}` |")

        datasets = provenance.get("datasets", [])
        if datasets:
            for ds in datasets:
                lines.append(f"| Dataset: {ds.get('source', '?')} | hash=`{ds.get('hash', '?')}` |")

        lines.append("")
        return "\n".join(lines)
