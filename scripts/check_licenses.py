"""Refuse a copyleft dependency before it reaches anybody's product.

This repo is MIT so that people can drop it into whatever they are
building. A GPL or AGPL dependency would quietly undo that, and the kind
of project that vendors a demo host is exactly the kind that would not
notice until much later.
"""

from __future__ import annotations

import json
import subprocess
import sys

FORBIDDEN = ("GPL", "AGPL", "SSPL", "CC BY-NC")
#: LGPL and the GPL-with-exception licences are permissive enough to link
#: against, and "GPL" appears inside both strings, so they are named here
#: rather than caught by the substring test above.
ALLOWED_EXACT = ("LGPL", "GPL-2.0-with", "GNU Library")


def main() -> int:
    raw = subprocess.run(
        [sys.executable, "-m", "piplicenses", "--format=json", "--with-urls"],
        capture_output=True,
        text=True,
        check=False,
    )
    if raw.returncode != 0:
        print(raw.stderr.strip() or "pip-licenses failed")
        return 1

    bad: list[str] = []
    for package in json.loads(raw.stdout or "[]"):
        licence = str(package.get("License") or "")
        if any(ok in licence for ok in ALLOWED_EXACT):
            continue
        if any(flag in licence.upper() for flag in FORBIDDEN):
            bad.append(f"{package.get('Name')} {package.get('Version')}: {licence}")

    if bad:
        print("copyleft dependencies, which this MIT repo cannot carry:")
        for line in bad:
            print(f"  {line}")
        return 1

    print("dependency licences clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
