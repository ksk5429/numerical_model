"""
SACS input deck parser.

SACS (Bentley Structural Analysis Computer System) stores its model
in a fixed-column text format with multi-letter record type prefixes:

    LDOPT   global options header (includes seabed elevation)
    OPTIONS analysis options
    LCSEL   load case selection
    SECT    section property definitions (TUB = tube, CON = cone)
    GRUP    member group assignments
    MEMBER  connectivity (joint-i joint-j group-id)
    JOINT   nodal coordinates
    LOAD    load records
    LCOMB   load combinations

This parser handles the subset needed for eigenvalue analysis:
joints, members, sections, groups, and the seabed elevation. It
ignores load records, PSI (pile-structure interaction) cards,
SOIL cards, and design check records — those are not needed for
the natural frequency / mode shape comparison Op^3 uses these decks
for.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SacsSection:
    """A section property entry from a SECT card."""
    name: str
    type: str   # 'TUB', 'CON', 'PLT', etc.
    raw: str    # the raw SACS line for debugging


@dataclass
class SacsJoint:
    """A single joint (node) from a JOINT card."""
    id: str
    x: float
    y: float
    z: float
    fixity: str = "FREE"


@dataclass
class SacsMember:
    """A single member (beam element) from a MEMBER card."""
    joint_i: str
    joint_j: str
    group: str


@dataclass
class SacsJacket:
    """Complete parsed SACS jacket deck."""
    seabed_elev_m: float = 0.0
    mudline_elev_m: float = 0.0
    source_file: Optional[Path] = None
    sections: list[SacsSection] = field(default_factory=list)
    joints: list[SacsJoint] = field(default_factory=list)
    members: list[SacsMember] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"SacsJacket({self.source_file.name if self.source_file else '?'}): "
            f"{len(self.joints)} joints, {len(self.members)} members, "
            f"{len(self.sections)} sections, seabed={self.seabed_elev_m} m"
        )


def parse_sacs(path: str | Path) -> SacsJacket:
    """Parse a SACS .sacs or .txt input deck.

    Handles the LDOPT, SECT, GRUP, JOINT, and MEMBER cards with
    SACS's column-oriented format. Tolerant of small format variations.

    Parameters
    ----------
    path : str or Path
        Path to the SACS deck file.

    Returns
    -------
    SacsJacket
        A parsed jacket with joints, members, sections, and seabed
        elevation populated. Unrecognized cards are silently skipped.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"SACS deck not found: {p}")

    jacket = SacsJacket(source_file=p)
    text = p.read_text(errors="replace")
    lines = text.splitlines()

    # LDOPT header: elevation is typically in columns 33-40 (or 35-42)
    # and 41-48. Example:
    #   LDOPT       NF+Z1.0280007.849000 -42.500  42.500GLOBMN...
    # The -42.500 is the seabed elevation; 42.500 is the mudline/PSI.
    for line in lines:
        if line.startswith("LDOPT"):
            # Extract floats in a robust way: find all signed decimals
            import re
            floats = re.findall(r"-?\d+\.\d+", line)
            # The seabed elevation is typically the first negative number
            for f in floats:
                v = float(f)
                if v < -5.0:
                    jacket.seabed_elev_m = v
                    jacket.mudline_elev_m = abs(v)
                    break
            break

    # Walk every line and classify by the leading keyword
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # SECT card: "SECT CONE      CON  ..."
        if line.startswith("SECT") and not line.startswith("SECTION"):
            parts = line.split()
            if len(parts) >= 3:
                jacket.sections.append(SacsSection(
                    name=parts[1],
                    type=parts[2],
                    raw=line.rstrip(),
                ))
            continue

        # GRUP card: group ID is column 6-9 typically
        if line.startswith("GRUP"):
            parts = line.split()
            if len(parts) >= 2 and parts[1] not in jacket.groups:
                jacket.groups.append(parts[1])
            continue

        # JOINT card: "JOINT 1     X.XXX Y.YYY Z.ZZZ"
        if line.startswith("JOINT"):
            parts = line.split()
            if len(parts) >= 5:
                try:
                    jacket.joints.append(SacsJoint(
                        id=parts[1],
                        x=float(parts[2]),
                        y=float(parts[3]),
                        z=float(parts[4]),
                        fixity=parts[5] if len(parts) > 5 else "FREE",
                    ))
                except (ValueError, IndexError):
                    pass
            continue

        # MEMBER card: "MEMBER joint-i joint-j group"
        if line.startswith("MEMBER") and not line.startswith("MEMBERS"):
            parts = line.split()
            if len(parts) >= 4:
                jacket.members.append(SacsMember(
                    joint_i=parts[1],
                    joint_j=parts[2],
                    group=parts[3],
                ))
            continue

    return jacket


def parse_sacs_to_json(path: str | Path, output: str | Path) -> dict:
    """Parse a SACS deck and write its neutral representation to JSON."""
    import json
    jacket = parse_sacs(path)
    data = {
        "source_file": str(jacket.source_file),
        "seabed_elev_m": jacket.seabed_elev_m,
        "mudline_elev_m": jacket.mudline_elev_m,
        "n_sections": len(jacket.sections),
        "n_joints": len(jacket.joints),
        "n_members": len(jacket.members),
        "groups": jacket.groups,
        "sections": [
            {"name": s.name, "type": s.type} for s in jacket.sections
        ],
        "joints": [
            {"id": j.id, "x": j.x, "y": j.y, "z": j.z, "fixity": j.fixity}
            for j in jacket.joints
        ],
        "members": [
            {"i": m.joint_i, "j": m.joint_j, "group": m.group}
            for m in jacket.members
        ],
    }
    Path(output).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
