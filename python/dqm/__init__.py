"""Mu2e Data Quality Monitoring.

The DQM components live as subpackages here, grouped by what they do and, just
as importantly, by what environment they can run in:

    dqm.schema      table, column and enum definitions -- the shared contract
    dqm.timeutil    time normalization and the DQM wire formats
    dqm.frames      DataFrame conventions shared by producers and consumers
    dqm.errors      the exception hierarchy

    dqm.reader      read the DQM database over Query Engine HTTP
    dqm.hist        read, fit and compare ROOT histograms    [hist, fit extras]
    dqm.plot        figures, interactive or as images             [plot extra]
    dqm.writer      write the database, via dqmTool                    [dqmTool]
    dqm.extract     histograms -> metrics -> writer                    [planned]
    dqm.evaluate    driver, evaluators and alarm findings              [planned]
    dqm.web         the Dash application                           [web extra]

**This module imports none of them.** That is load-bearing, not an oversight.
A single distribution ships every component, so a plain venv -- an MCP server,
a cron host -- gets dqm.web and dqm.plot as inert files it never imports,
while dash and matplotlib are simply absent. Each deployment installs the same
`mu2e-dqm` and imports only the parts its environment can satisfy. Importing a
subpackage from here would drag every dependency into every deployment and
undo that.

Reading ROOT files goes through uproot rather than PyROOT, so dqm.hist needs
no Muse or Offline environment. The only component that does is dqm.writer,
which drives the compiled dqmTool executable.

So reach for what you need directly:

    from dqm.reader import DqmReader
    from dqm.schema import NumberCode
"""

try:
    from importlib.metadata import version as _dist_version

    __version__ = _dist_version("mu2e-dqm")
except Exception:  # not pip-installed -- e.g. imported from a checkout via PYTHONPATH
    __version__ = "unknown (not installed as a package)"

__all__ = ["__version__"]
