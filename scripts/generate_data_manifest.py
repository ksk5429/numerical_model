"""
Generate a data_manifest.yaml at the repository root listing every
committed data artefact with its SHA-256, byte size, licence, and
provenance.

The manifest is the single source of truth for reviewers who want
to verify that the data shipped with a tagged release of Op^3 has
not drifted. At runtime the framework can optionally consult the
manifest to refuse stale data.

Usage:
    python scripts/generate_data_manifest.py
    # writes data_manifest.yaml + prints a summary

Fields per entry:
    path:      relative path from the repository root
    sha256:    hex digest
    bytes:     file size
    licence:   SPDX identifier or URL
    source:    short description of who produced the file
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List

import yaml

REPO = Path(__file__).resolve().parents[1]

# Glob patterns for tracked data files worth including in the manifest.
# Generated artefacts (build outputs, caches) are intentionally excluded.
INCLUDE_GLOBS = [
    "data/**/*.csv",
    "data/**/*.json",
    "data/**/*.yaml",
    "data/**/*.yml",
    "nrel_reference/**/*.dat",
    "nrel_reference/**/*.fst",
    "nrel_reference/**/*.inp",
    "nrel_reference/**/*.3",
    "nrel_reference/**/*.txt",
    "nrel_reference/**/*.csv",
    "ref_site_a/**/*.dat",
    "ref_site_a/**/*.fst",
    "ref_site_a/**/*.yaml",
    "ref_site_a/**/*.IN",
    "sample_projects/*.op3proj",
    "validation/benchmarks/*.csv",
    "validation/benchmarks/*.json",
    "validation/benchmarks/*.md",
]

EXCLUDE_GLOBS = [
    "**/__pycache__/**",
    "**/.git/**",
    "**/_book/**",
    "**/.quarto/**",
    "**/*.outb",   # large binaries; enumerated separately if needed
    "**/*.out",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def guess_licence(rel: str) -> str:
    if rel.startswith("nrel_reference/"):
        return "Apache-2.0 (NREL OpenFAST + r-test)"
    if rel.startswith("sample_projects/"):
        return "MIT (Op^3 framework)"
    if rel.startswith("validation/benchmarks/"):
        return "MIT (Op^3 framework)"
    if rel.startswith("ref_site_a/"):
        return "Academic-use (KEPCO research agreement; runtime-loaded)"
    return "MIT (Op^3 framework)"


def guess_source(rel: str) -> str:
    if rel.startswith("nrel_reference/openfast_rtest/"):
        return "NREL OpenFAST r-test regression suite"
    if rel.startswith("nrel_reference/"):
        return "NREL reference wind turbine library"
    if rel.startswith("sample_projects/"):
        return "Op^3 framework sample library"
    if rel.startswith("ref_site_a/openfast_deck"):
        return "Op^3 framework OpenFAST deck (ref site A)"
    if rel.startswith("validation/"):
        return "Op^3 release validation suite"
    return "Op^3 framework"


def main() -> None:
    entries: List[Dict] = []
    seen = set()
    for pat in INCLUDE_GLOBS:
        for p in REPO.glob(pat):
            if not p.is_file():
                continue
            rel = p.relative_to(REPO).as_posix()
            if any(p.match(ex) for ex in EXCLUDE_GLOBS):
                continue
            if rel in seen:
                continue
            seen.add(rel)
            entries.append({
                "path": rel,
                "sha256": sha256(p),
                "bytes": p.stat().st_size,
                "licence": guess_licence(rel),
                "source": guess_source(rel),
            })

    entries.sort(key=lambda e: e["path"])
    manifest = {
        "schema_version": "1.0",
        "op3_version": "1.0.0-rc1",
        "total_entries": len(entries),
        "total_bytes": sum(e["bytes"] for e in entries),
        "entries": entries,
    }

    out = REPO / "data_manifest.yaml"
    with out.open("w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, sort_keys=False, default_flow_style=False)

    print(f"wrote {out}")
    print(f"  {len(entries)} entries, {manifest['total_bytes']/1e6:.2f} MB total")


if __name__ == "__main__":
    main()
