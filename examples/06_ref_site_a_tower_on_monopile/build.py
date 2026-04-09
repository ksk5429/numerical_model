"""
Example 06: SiteA RT1 tower on equivalent monopile (Op^3 isolation test)

Composes the Op^3 TowerModel for this example. Returns a model
object ready for .eigen() or .extract_6x6_stiffness().
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from op3 import build_foundation, compose_tower_model


def build():
    """Return a TowerModel for example 06."""
    # Make foundation args paths absolute relative to the repo root
    fnd_kwargs = {'stiffness_matrix': 'data/fem_results/K_6x6_oc3_monopile.csv'}
    for k, v in list(fnd_kwargs.items()):
        if isinstance(v, str) and v.endswith(('.csv', '.sacs')):
            fnd_kwargs[k] = str((REPO_ROOT / v).resolve())

    foundation = build_foundation(
        mode="stiffness_6x6",
        **{k: v for k, v in fnd_kwargs.items() if k in
              ('spring_profile', 'stiffness_matrix', 'ogx_dissipation',
               'ogx_capacity', 'scour_depth')},
    )

    return compose_tower_model(
        rotor="ref_4mw_owt",
        tower="site_a_rt1_tower",
        foundation=foundation,
    )


if __name__ == "__main__":
    model = build()
    print(f"Built example: SiteA RT1 tower on equivalent monopile (Op^3 isolation test)")
    print(f"  Rotor:      {model.rotor_name}")
    print(f"  Tower:      {model.tower_name}")
    print(f"  Foundation: {model.foundation.mode.value}")
    print(f"  Source:     {model.foundation.source}")
