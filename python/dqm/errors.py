"""The DQM exception hierarchy.

Everything raised deliberately by a dqm component derives from DqmError, so a
driver running several components can catch that one class and still
distinguish causes by subclass. Components define their own subclasses here
rather than locally, which keeps the hierarchy visible in one place -- a
caller can see what might come at it without reading every subpackage.
"""


class DqmError(Exception):
    """Base class for every error raised deliberately by a dqm component."""


class DqmConfigError(DqmError):
    """A caller asked for something inconsistent -- a bad table name, an
    unsupported option, a filter that cannot be expressed."""


class DqmDependencyError(DqmError, ImportError):
    """An optional dependency for this component is not installed.

    The components ship in one distribution but have very different
    requirements, so a plain venv holds dqm.hist and dqm.web as files it never
    imports. Reaching for one anyway should say which extra to install, not
    produce a bare ImportError. Deriving from ImportError as well means code
    that already catches that keeps working.
    """


# --------------------------------------------------------------------- reading


class DqmReadError(DqmError):
    """Base for failures reading the database."""


class QueryEngineError(DqmReadError):
    """Query Engine returned something other than the CSV that was requested.

    Covers an HTTP error status and a 200 response whose body is not the CSV
    asked for -- QE reports some failures as an HTML page under 200, which a
    CSV parser would otherwise turn into a frame of nonsense.
    """


class TooManyQueriesError(DqmReadError):
    """A filter resolved to more ids than one call is willing to fan out over.

    QE has no IN operator, so a multi-id filter costs one query per id; past
    some count the caller should narrow the filter rather than wait.
    """


# -------------------------------------------------------------- histograms


class DqmHistError(DqmError):
    """Base for failures reading or working with histogram files."""


class DqmFitError(DqmHistError):
    """A fit could not be obtained, read, or evaluated.

    Deliberately distinct from "this histogram carries no fit", which is a
    normal condition reported by returning None. Collapsing the two is how a
    fit that stopped being readable would get written to the database as a
    legitimate-looking zero.
    """


# --------------------------------------------------------------------- writing


class DqmWriteError(DqmError):
    """Base for failures writing the database.

    Writes go through the dqmTool executable rather than SQL from Python, so
    these wrap a subprocess outcome: a nonzero exit, output that could not be
    parsed, or a missing Kerberos credential.
    """
