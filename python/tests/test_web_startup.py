"""Importing, building and logging the application exactly once.

Two faults here were invisible in production and noisy everywhere else: the
`dqm` logger got a second handler when the CLI had already configured the root
one, and `dqm.web.app` built an application at import that `dqm-web` and these
tests then threw away. Between them the access policy -- the one startup line
an operator has to be able to trust -- was logged four times in two formats.

These run the module in a subprocess, because both faults are about what
importing does, and an import cannot be undone inside a live interpreter.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("dash")

PYTHON_DIR = Path(__file__).resolve().parents[1]


def _run(code: str) -> subprocess.CompletedProcess:
    """Run a snippet against this checkout, with no logging configured."""
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=str(PYTHON_DIR), timeout=300)
    if "DqmDependencyError" in proc.stderr:
        pytest.skip("dqm.web cannot be imported here: missing web extra")
    assert proc.returncode == 0, proc.stderr
    return proc


def _access_lines(proc: subprocess.CompletedProcess) -> list:
    out = proc.stdout + proc.stderr
    return [ln for ln in out.splitlines() if "dqm.web.access" in ln]


def test_importing_create_app_builds_nothing():
    """The package docstring promises that importing builds no application.

    It is also what keeps a test suite, or anything wanting create_app with
    its own prefixes, from paying for an app it will not use.
    """
    proc = _run("from dqm.web.app import create_app; print('ok')")
    assert "ok" in proc.stdout
    assert _access_lines(proc) == []


def test_the_wsgi_entry_point_still_resolves():
    """`gunicorn dqm.web.app:server` is attribute access on the module, so
    the lazy instance has to be reachable that way."""
    proc = _run("from dqm.web.app import server; print(type(server).__name__)")
    assert "Flask" in proc.stdout


def test_the_wsgi_entry_point_logs_its_access_policy_once():
    """Under gunicorn nothing else configures logging, so this module does --
    and the line has to appear, exactly once."""
    proc = _run("from dqm.web.app import server")
    assert len(_access_lines(proc)) == 1


def test_app_and_server_are_the_same_application():
    proc = _run("import dqm.web.app as m; print(m.server is m.app.server)")
    assert "True" in proc.stdout


def test_an_unknown_attribute_still_raises():
    """The lazy hook must not turn every typo into an application."""
    proc = _run(
        "import dqm.web.app as m\n"
        "try:\n"
        "    m.nonesuch\n"
        "except AttributeError as exc:\n"
        "    print('raised', exc)\n"
    )
    assert "raised" in proc.stdout


def test_the_cli_logs_the_access_policy_once_not_four_times():
    """--check with the CLI's own logging configured: one application, one
    handler, one line."""
    proc = _run("from dqm.web.cli import main; raise SystemExit(main(['--check']))")
    assert len(_access_lines(proc)) == 1
    assert "OK: dqm-web built" in proc.stdout


def test_an_existing_logging_configuration_is_left_alone():
    """basicConfig configures the root logger and dqm records propagate to
    it. Adding a handler to "dqm" as well is what printed every line twice,
    in two different formats."""
    proc = _run(
        "import logging\n"
        "logging.basicConfig(level=logging.INFO, format='CONFIGURED %(name)s %(message)s')\n"
        "from dqm.web.app import create_app\n"
        "create_app()\n"
    )
    lines = _access_lines(proc)
    assert len(lines) == 1
    assert lines[0].startswith("CONFIGURED")


def test_with_no_configuration_the_module_provides_one():
    proc = _run("from dqm.web.app import create_app; create_app()")
    lines = _access_lines(proc)
    assert len(lines) == 1
    assert "no DQM_WEB_ALLOW set" in lines[0]
