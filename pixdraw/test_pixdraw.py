# SPDX-License-Identifier: AGPL-3.0-or-later
"""pytest entry: `pytest pixdraw/test_pixdraw.py` (the same checks `python -m pixdraw selftest` and `python -m pixdraw golden` run, no pytest needed)."""
from pixdraw import golden
from pixdraw.selftest import run

def test_selftest(): assert run() == 0
def test_golden():
    ok, msg = golden.check(); assert ok, msg
