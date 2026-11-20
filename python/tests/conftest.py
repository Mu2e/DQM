"""Shared test setup.

The tests run against the checkout, not an installed wheel: the directory
holding the `dqm` package is put first on sys.path so that `import dqm` finds
the code under test even when an older mu2e-dqm is installed.
"""

import os
import stat
import sys
from pathlib import Path
from typing import List

import pytest

PYTHON_DIR = Path(__file__).resolve().parents[1]
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))


@pytest.fixture
def fake_dqmtool(tmp_path, monkeypatch):
    """A stand-in for `dqmTool commit-alarm`, so no database is needed.

    Records the --cause argument of every call, prefixed OK or FAIL. Exits 1
    for any cause whose iid was passed to fail_iids(), which is how a test
    makes one commit fail all its retries.
    """
    from dqm.evaluate import driver as driver_mod

    log = tmp_path / "dqmtool-calls.txt"
    script = tmp_path / "fake-dqmTool"
    script.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "args = sys.argv[1:]\n"
        "cause = args[args.index('--cause') + 1]\n"
        "fail = set(filter(None, os.environ.get('FAKE_DQMTOOL_FAIL_IIDS', '').split(',')))\n"
        "iid = cause.split(',')[0]\n"
        "with open(os.environ['FAKE_DQMTOOL_LOG'], 'a') as fh:\n"
        "    fh.write(('FAIL ' if iid in fail else 'OK ') + cause + '\\n')\n"
        "sys.exit(1 if iid in fail else 0)\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("FAKE_DQMTOOL_LOG", str(log))
    monkeypatch.setenv("FAKE_DQMTOOL_FAIL_IIDS", "")
    # The retries are part of the behaviour under test; the wait is not.
    monkeypatch.setattr(driver_mod, "COMMIT_RETRY_WAIT", 0.0)

    class Tool:
        path = str(script)

        @staticmethod
        def fail_iids(*iids: int) -> None:
            os.environ["FAKE_DQMTOOL_FAIL_IIDS"] = ",".join(str(i) for i in iids)

        @staticmethod
        def calls() -> List[str]:
            return log.read_text().splitlines() if log.exists() else []

    return Tool()
