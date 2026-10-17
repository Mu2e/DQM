"""Read the Mu2e DQM database through Query Engine.

    from dqm.reader import DqmReader

    r = DqmReader()
    df = r.numbers(sid=5, vid=15)

Needs pandas and requests, both base dependencies of mu2e-dqm, so this
subpackage imports anywhere the distribution is installed -- no Muse
environment, no credentials, no ROOT.

The enums and table definitions are re-exported for convenience, but they
belong to dqm.schema; import them from there in code that does not otherwise
need a reader.
"""

from dqm.errors import (  # noqa: F401
    DqmConfigError,
    DqmError,
    DqmReadError,
    QueryEngineError,
    TooManyQueriesError,
)
from dqm.frames import is_truncated, to_records  # noqa: F401
from dqm.schema import (  # noqa: F401
    ALARM_VALUES,
    CODE_VALUES,
    AlarmCode,
    NumberCode,
)
from dqm.reader.reader import (  # noqa: F401
    DEFAULT_LIMIT,
    DEFAULT_MAX_PUSHDOWN_QUERIES,
    DqmReader,
)
from dqm.reader.transport import (  # noqa: F401
    DEFAULT_DBNAME,
    DEFAULT_QE_NOCACHE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    QEClient,
)

__all__ = [
    "DqmReader",
    "QEClient",
    "DEFAULT_LIMIT",
    "DEFAULT_MAX_PUSHDOWN_QUERIES",
    "DEFAULT_QE_NOCACHE_URL",
    "DEFAULT_DBNAME",
    "DEFAULT_TIMEOUT_SECONDS",
    "DqmError",
    "DqmConfigError",
    "DqmReadError",
    "QueryEngineError",
    "TooManyQueriesError",
    "NumberCode",
    "AlarmCode",
    "CODE_VALUES",
    "ALARM_VALUES",
    "to_records",
    "is_truncated",
]
