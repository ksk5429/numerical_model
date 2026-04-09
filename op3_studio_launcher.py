"""Op^3 Studio launcher — PyInstaller-friendly entrypoint.

Importing `op3_viz.dash_app.app` as a proper package avoids the
relative-import crash that happens when PyInstaller freezes the
inner module directly as a script.
"""
from __future__ import annotations

import os
import sys


def main() -> None:
    # Make sure the private-data resolver can still be overridden
    # via environment variable in the frozen binary.
    print("Op^3 Studio v1.0.0-rc1")
    print(f"  OP3_PHD_ROOT = {os.environ.get('OP3_PHD_ROOT', '(unset)')}")
    print(f"  Python       = {sys.version.split()[0]}")

    from op3_viz.dash_app.app import create_app
    app = create_app()
    print("  starting Dash server on http://127.0.0.1:8050/ ...")
    app.run(debug=False, host="127.0.0.1", port=8050)


if __name__ == "__main__":
    main()
