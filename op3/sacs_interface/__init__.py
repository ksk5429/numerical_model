"""
Op^3 SACS jacket deck parser.

Reads Bentley SACS (Structural Analysis Computer System) input decks
and produces a neutral Python data structure that the Op^3
OpenSeesPy jacket builder can consume. Read-only — no SACS writer.

Usage:

    from op3.sacs_interface import parse_sacs
    jacket = parse_sacs('nrel_reference/sacs_jackets/nrel_oc4/NREL_OC4.sacs')
    print(f"Joints: {len(jacket.joints)}")
    print(f"Members: {len(jacket.members)}")
    print(f"Seabed elevation: {jacket.seabed_elev_m} m")

    # Hand off to OpenSeesPy
    from op3.opensees_foundations.jacket_builder import build_from_sacs
    model = build_from_sacs(jacket, rna_mass=1_017_000)
    f1 = model.eigen(1)[0]
"""
from op3.sacs_interface.parser import parse_sacs, SacsJacket, SacsJoint, SacsMember, SacsSection

__all__ = [
    "parse_sacs",
    "SacsJacket",
    "SacsJoint",
    "SacsMember",
    "SacsSection",
]
