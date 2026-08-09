"""Friday test suite (stdlib unittest - zero extra dependencies).

Run:  ./.venv/bin/python -m unittest discover -s tests -v
Proof: gates/test_suite.py runs the same discovery and captures the raw
output into gates/TESTS_PROOF.md, in the gate-proof tradition.
"""

from __future__ import annotations

import sys
from pathlib import Path

# unittest discovery runs with cwd == project root, but make the package
# importable no matter how the suite is launched.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
