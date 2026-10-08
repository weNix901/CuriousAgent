"""Repo-root conftest — hardens import resolution (v0.3.7 B-1).

Root cause
----------
Another project is installed editable and injects
``/root/dev/dualLoopAgent/openharness`` onto ``sys.path`` via
``_editable_impl_openharness_ai.pth``. That directory contains its own
``tests/`` package, so a bare ``import tests`` resolves to THAT project's
tests, not ours (repro: ``python3 -c "import tests; print(tests.__file__)"``).

Fix
---
Anchor this repo's root at the FRONT of ``sys.path`` before any collection
happens. ``pytest.ini``'s ``pythonpath = .`` helps pytest's own importer, but
does NOT stop a stale ``tests`` module already resolved through a foreign
``.pth``, nor guard plain ``import tests`` inside test code. Doing it here in
the first-loaded conftest makes this repo's ``tests``/``core``/... win
unconditionally — repo-local, no cross-project changes.
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Prepend repo root so local packages shadow foreign .pth injections.
if sys.path and sys.path[0] != _REPO_ROOT:
    while _REPO_ROOT in sys.path:
        sys.path.remove(_REPO_ROOT)
    sys.path.insert(0, _REPO_ROOT)

# If a foreign `tests` package was already imported, evict it so the next
# import resolves to this repo's tests/ instead of the other project's.
_foreign_tests = sys.modules.get("tests")
if _foreign_tests is not None:
    _foreign_file = getattr(_foreign_tests, "__file__", "") or ""
    if not _foreign_file.startswith(_REPO_ROOT + os.sep):
        del sys.modules["tests"]
