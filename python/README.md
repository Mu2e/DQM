# mu2e-dqm

The Python side of Mu2e Data Quality Monitoring: database access, metric
extraction, evaluation, and display.

One installable distribution, `mu2e-dqm`, with components as subpackages of
`dqm`. Install it from this directory (note `subdirectory=python`, since the
packaging metadata lives here rather than at the repository root):

```bash
uv pip install "mu2e-dqm @ git+https://github.com/Mu2e/DQM@<ref>#subdirectory=python"
uv pip install "mu2e-dqm[web] @ git+..."   # the full display application
```

Extras, kept deliberately coarse — an understandable stack is worth more here
than a minimal one:

| Extra | Adds | For |
|---|---|---|
| *(none)* | pandas, requests | `dqm.reader`, `dqm.schema` — the MCP host |
| `hist` | uproot, hist, xrootd, scipy | reading and comparing ROOT files |
| `fit` | lmfit | fitting histograms here rather than reading a stored fit |
| `plot` | plotly, matplotlib, mplhep | figures, interactive and static |
| `catalog` | metacat, mu2e-mdh | finding files by dataset, name → path |
| `web` | all the above + dash, gunicorn | the Dash application |
| `all` | everything | a development checkout |

The whole lot is about 500 MB and installs in seconds — all pip wheels, no
cvmfs, no spack, no compilation.

From a checkout: `uv pip install /path/to/DQM/python`, or `-e` for an editable
install while developing. The version comes from the nearest git tag via
`setuptools_scm`, so `dqm.__version__` names the revision running.

## Layout

```
dqm/
  schema.py     tables, columns, dtypes, enums -- the shared contract
  timeutil.py   time normalization and the DQM wire formats
  frames.py     DataFrame conventions: truncation flags, JSON conversion
  errors.py     the exception hierarchy, rooted at DqmError

  reader/       read the database over Query Engine HTTP
  hist/         read, fit and compare ROOT histograms -- no ROOT needed
                  read.py     uproot -> hist.Hist, file walking
                  stats.py    mean/RMS matching ROOT's fill-time accumulators
                  fit.py      a stored fit, or one computed with lmfit
                  compare.py  KolmogorovTest port, file-vs-file comparison
  plot/         build a figure once, render it twice
                  spec.py        PlotSpec -- renderer-independent
                  interactive.py -> plotly, for the app
                  static.py      -> matplotlib/mplhep, for reports
  catalog.py    find files via metacat; file name -> path via mdh
  web/          the single Dash application
                  app.py     the Dash/Flask app, one tab per activity
                  timeline/  histogram/  alarms/   (tab modules)
                  routes.py  Flask routes for static image export
  writer/       write the database, by driving dqmTool             [planned]
  extract/      histograms -> metrics -> writer                    [planned]
  evaluate/     driver, evaluators, and alarm findings             [planned]
```

## Why one distribution

Because the components share a schema. The extractor writes metrics, the
evaluator reads them and compares against limits, the driver commits alarm
findings, and the web app displays all of it. They have to agree on table
shapes and on what `code=1` means. With one version, "mu2e-dqm 1.5.0" names a
coherent set; split across independently-versioned distributions, a stale
evaluator and a fresh extractor could disagree with nothing to catch it.

`dqm/schema.py` is where that agreement lives. Several of its definitions
mirror C++ headers in this repository, which remain the source of truth:

| Python | C++ |
|---|---|
| `NumberCode` | `DqmNumber::codeValues` — `DQM/inc/DqmNumber.hh` |
| `AlarmCode` | `DqmLimit::alarmValues` — `DQM/inc/DqmLimit.hh` |
| `ALARM_STATUSES`, `ALARM_GRACE_HOURS` | `DqmAlarm::statusValues`, `graceHours` — `DQM/inc/DqmAlarm.hh` |

Keeping a Python copy is deliberate duplication — the alternative is parsing
headers at runtime — so a header change has to be mirrored here.

## Why that does not force one environment

`dqm/__init__.py` imports **no** subpackage. That is load-bearing: a plain venv
installs the same distribution and gets `dqm.web` and `dqm.extract` as inert
files it never imports, while dash and ROOT are simply absent. So one
distribution serves two very different deployments:

| Environment | Components | Needs |
|---|---|---|
| Plain venv | `reader`, `hist`, `plot`, `web` | pip only |
| + `dqmTool` on PATH | `writer`, `extract`, `evaluate` | Muse build, Kerberos credential |

Reading ROOT files goes through **uproot**, not PyROOT, so none of the read,
fit, display or comparison code needs a Muse or Offline environment. That is
what makes the display application a plain pip install.

The one remaining precondition is `dqmTool`, the compiled executable every
write goes through — the lookup-or-create and alarm-episode logic lives there
(`DqmTool.hh` calls it "the primary expected use pattern"), and it already
accepts batch input from a file, so a subprocess per (source, interval) is not
a per-metric cost. No dependency declaration can express "this binary must be
on PATH", which is why nothing is imported eagerly.

## dqm.reader

The read path every consumer shares — the `dqm` MCP server, the display
applications, the evaluators, and bulk analysis.

```python
from dqm.reader import DqmReader

r = DqmReader()                       # production DB, QE nocache endpoint
src = r.sources(process="valNightly", stream="reco", aggregation="day")
val = r.values(groupx="cal", namex="meanE0")
df  = r.numbers(sid=int(src.sid.iloc[0]), vid=int(val.vid.iloc[0]))
```

`df` is a DataFrame: one row per interval, with the measurement and the
interval's run range and timestamps — a timeline ready to plot.

A CLI comes with it, installed as `dqm-reader` (also `python -m dqm`), for
looking at the database by hand:

```bash
dqm-reader --sources
dqm-reader --sid 5 --vid 15 --summary
dqm-reader --count
```

### Returning DataFrames

`dqm.numbers` holds ~480k rows and is expected to reach millions. As per-row
dicts that is roughly a kilobyte per row — near a gigabyte at a million rows;
as a DataFrame with numeric dtypes it is about 100 MB and a second or two,
because `read_csv` goes from the response stream straight into typed columns.
Measured on the full current table: 480,272 rows in ~5 s, a 30 MB frame.

Callers needing JSON convert at their own boundary with
`dqm.frames.to_records`, which handles the numpy scalars and `pd.NA`/`NaT` the
standard json encoder rejects.

### Three properties worth knowing

**Limits are explicit.** Query Engine returns the *entire* table when given no
limit, so every entry point defaults to `DEFAULT_LIMIT` (100,000). Pass
`limit=None` to ask for everything deliberately.

**Truncation is labeled.** Frames carry a truncation flag, set by fetching one
row past the limit and seeing whether it came back. A short result with
`is_truncated(df)` true means the query stopped early — a different claim from
"this is all the data there is". `count_metrics(...)` gives the exact total
when you need to report one.

**Filters are pushed into the database.** A multi-id filter becomes one query
per id, because QE has no `IN` operator; the fan-out is capped by
`max_pushdown_queries` (default 200), which raises rather than silently issuing
hundreds of round trips. The alternative — scanning the most recent N rows and
filtering afterwards — silently misses a low-rate source sharing a table with
high-rate ones, no matter how large the window, because the window needed
depends on every *other* source's insertion rate rather than on the query's own
selectivity.

Operators in where clauses are validated against the six QE supports, because
an unsupported one is absorbed into the value and returns zero rows under HTTP
200 on a text column — counterfeiting exactly the "no data" claim the
truncation flag exists to protect. See the aitools skill
`coding-with-query-engine`.

### Large results

Too large to hold — stream it:

```python
for chunk in r.iter_metrics(sid=5, limit=None, chunksize=100_000):
    ...
```

Too large to read — reduce it:

```python
r.summarize(df)            # count, mean/std/min/max/median, span, endpoints
r.downsample(df, n=200)    # ~200 time bins, each with mean, min and max
```

`downsample` keeps per-bin min and max rather than striding, so an excursion
between sample points survives.

### Tables without a dedicated method

`dqm.alarms`, `dqm.alarm_causes` and `dqm.files` have no typed entry point yet;
reach them through `read_table`, which takes any table in `dqm.schema`:

```python
r.read_table("alarms", limit=50)
r.read_table("alarm_causes")
```

## dqm.hist

Reading ROOT histograms without ROOT. uproot parses the file format directly,
so this is a pip install, not a Muse environment.

```python
from dqm.hist import open_file, statistics, fit_histogram, compare_files

with open_file(path) as f:
    for entry in f.histograms(ndim=1):
        h = f.read(entry.path)              # a hist.Hist
```

`hist.Hist` is the internal representation throughout: it keeps bin edges,
axis metadata and per-bin variances together, so nothing downstream passes
parallel arrays around or has to guess whether flow bins are included.

### Statistics match ROOT exactly

`statistics()` reads ROOT's fill-time accumulators (`fTsumw`, `fTsumwx`,
`fTsumwx2`) rather than recomputing from bin centres. That is not pedantry:
on a real CRV histogram the two differ by 0.017, and since these numbers get
written to the database as metrics, the easy implementation would silently
shift every value away from the existing rows. Verified against ROOT 6.40 to
full double precision.

It takes the uproot object, not the Hist — converting drops the accumulators:

```python
st = statistics(f.read_raw(path), f.read(path))
st.mean, st.mean_error, st.std_dev        # exactly ROOT's GetMean() etc.
st.from_accumulators                      # False if it had to fall back
```

### Fits, from either source

A fit can already be attached to a histogram by whatever wrote the file, or it
can be computed here. Both produce the same `FitResult` with `source` saying
which, so everything downstream is written once:

```python
fit = stored_fit(raw)          # None if the histogram carries no fit
fit = fit_histogram(h)         # computed with lmfit
fit = get_fit(raw)             # stored if present, otherwise fitted
fit.value("center"), fit.error("center"), fit.redchi
```

Parameter names are canonical, not ROOT's: a Gaussian always has `center`,
`sigma` and `height` whichever way it was obtained. ROOT calls those Mean,
Sigma and Constant, and stores the values in `fFormula.fClingParameters` while
leaving the obvious-looking `fParams` empty.

**`stored_fit` returns `None` for "no fit attached" and raises for "a fit is
there but unreadable."** The code this replaced collapsed both into
`except: value = 0.0`, and since zero is also a legitimate measurement, a fit
that stopped being readable would have been indistinguishable from data.

Fits use lmfit rather than Minuit. On a real histogram it agrees with ROOT to
0.001 in centre and 0.000 in sigma with an identical reduced chi-square, so
the choice is about readability.

### Comparison

`compare_histograms` and `compare_files` port the ROOT implementation,
keeping both measures and the status vocabulary so existing judgements stay
comparable. The Kolmogorov test is reproduced in numpy and scipy —
`scipy.special.kolmogorov` *is* the series `TMath::KolmogorovProb` evaluates —
and agrees with ROOT to 1.5e-10 on real histograms.

Three bugs in the original are fixed rather than carried over, each marked
`FIXED` at the point it mattered. The serious one: histograms with **different
binning were reported as `perfect`**, the most misleading verdict available,
because the early return left the status at its initial value. They are now
`cantCompare`. The second: comparing against an empty histogram raised
`NameError`, since `math` was used but never imported.

## dqm.plot

DQM needs the same figure twice — interactive in the browser, and as a static
image for a note or an elog post. Writing each one twice is how the two
quietly stop agreeing, so a figure is built once as a `PlotSpec` that knows
nothing about either rendering library:

```python
from dqm.plot import PlotSpec, to_plotly, save_image

spec = PlotSpec(title="crvPEsMPV sector 0", xlabel="PEs")
spec.add_hist(h0, label="reference", style="step")
spec.add_hist(h1, label="candidate", style="errorbar")
spec.add_fit(fit)
spec.add_band(low, high, label="limits")

fig = to_plotly(spec)                  # for the Dash app
save_image(spec, "report.pdf")         # for the note
```

Each renderer is a thin translation, so content lives in exactly one place.
`save_image` takes the format from the extension — PDF and SVG are vector and
are what a document wants; `to_png_bytes` and `to_data_uri` serve a web
response without a temporary file.

The renderers are imported lazily, so a batch job writing PNGs does not need
plotly installed, and the app does not need matplotlib unless it exports.

A fit whose formula cannot be reconstructed still contributes its parameters
to the annotation box — only the curve is omitted, and the histograms still
draw.

## dqm.web

The application: one Dash app with a tab per activity -- timelines from the
database, histogram overlays from ROOT files, and alarm episodes. Dash is
built on Flask, so `dqm.web.app.server` is a real Flask application; that is
what lets the static-image export routes live in the same process as the
interactive UI.

### Install and run

```bash
uv venv /path/to/dqm-web
uv pip install --python /path/to/dqm-web/bin/python \
  "mu2e-dqm[web] @ git+https://github.com/Mu2e/DQM@<tag>#subdirectory=python"

/path/to/dqm-web/bin/dqm-web --check          # build the app, bind nothing
/path/to/dqm-web/bin/dqm-web --port 8100      # development server
```

Then open `http://<host>:8100/`. `--check` is worth running first: it
constructs the app and exits, so a missing dependency or an unreachable
database surfaces without waiting for a browser.

For anything beyond trying it out, use a real WSGI server -- `dqm-web` runs
Dash's development server, which is single-threaded and says so on startup:

```bash
/path/to/dqm-web/bin/gunicorn --bind 127.0.0.1:8100 --workers 4 \
    --timeout 120 'dqm.web.app:server'
```

`--timeout 120` because a cold "all histograms" render over a large file can
take longer than gunicorn's 30-second default and would otherwise be killed
mid-request.

### Options

| Flag | Default | Notes |
|---|---|---|
| `--host` | `127.0.0.1` | `0.0.0.0` accepts connections from other machines |
| `--port` | `8100` | |
| `--prefix` | none | serve under a path, e.g. `/dqm/` |
| `--routes-prefix` | = `--prefix` | set separately when the proxy strips the prefix |
| `--check` | | construct and exit |
| `--debug` | | Dash debug mode with hot reload |

### Behind a reverse proxy

Running the app on a machine where the environment is easy and proxying to it
is the expected arrangement -- see the note on environments above. Two
prefixes exist because they are not the same thing: `routes_` is the path this
process serves on, `requests_` is the path the browser asks for. They differ
whenever the proxy strips the prefix before forwarding, which is the usual
case and the usual cause of a blank page with 404s on every asset.

Bind `127.0.0.1` when proxying. A port bound to `0.0.0.0` is reachable
directly across the org network, which goes around whatever authentication the
front-end web server enforces -- and the histogram tab will open any file path
the service account can read.

`/healthz` returns the running version, for the proxy and for systemd.

### Running it as a service

The same pattern the dqm MCP uses -- `systemd --user` with lingering enabled,
so it survives logout:

```ini
[Unit]
Description=Mu2e DQM web application
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=MPLCONFIGDIR=/var/tmp/dqm-web-mpl
Environment=METACAT_SERVER_URL=https://metacat.fnal.gov:9443/mu2e_meta_prod/app
ExecStart=/path/to/dqm-web/bin/gunicorn --bind 127.0.0.1:8100 --workers 4 \
    --timeout 120 dqm.web.app:server
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
loginctl enable-linger                 # once per account
systemctl --user daemon-reload
systemctl --user enable --now dqm-web
```

Both `Environment=` lines matter. **`MPLCONFIGDIR`** must point somewhere
writable: matplotlib caches its font list there, and a service account with an
unwritable or over-quota home rebuilds that cache on *every* static export --
slow, but never an outright failure, so it is easy to miss.
**`METACAT_SERVER_URL`** is what the dataset browser needs; without it (or
without a valid token) the dataset dropdown is disabled and typed file paths
still work.

Do not stop the service with `pkill -f dqm-web`. `pkill` matches full command
lines, including the command line doing the matching, so it kills its own
shell. systemd tracks the real process id and has no such problem.

### Static image export

Every figure on screen can be fetched as a report-quality image from the same
process, because both come from the same PlotSpec:

```
/report/timeline.png?series=5:15&mode=time&window=365
/report/timeline.pdf?series=5:15,115:98&mode=run&window=50
/report/timeline.svg?series=5:15
```

`series` is a comma-separated list of `source:metric` pairs, mirroring the
rows in the application; omit `window` for the entire history. PDF and SVG are
vector, which is what a note or a paper wants. The links under the timeline
plot produce exactly these URLs, so a figure can be dropped into an elog entry
as a link rather than a screenshot.

## Notes

- `sigma = 0.0` means not applicable or not computed, not literally zero error.
- `dqm.numbers` and `dqm.limits` are populated independently with no foreign
  key between them. An interval can carry limits and no measurements, so an
  empty `numbers` result does not mean the interval is unused.
- `version` is a string, not a number — real values include both `"0"` and
  `"005-001"`.
- Timestamps come back tz-aware in UTC. QE renders them with a local offset
  that shifts across DST, so they are parsed with `utc=True` to keep the column
  comparable. Resolution is `ns` under pandas 2 and `us` under pandas 3; both
  work, so code should not assume either.
- The QE cache endpoint (`:8444`) is rejected at construction — a monitoring
  database wants nocache (`:9443`).
- Only `dqm` is packaged. The standalone scripts beside it in `DQM/python`
  (`compare.py`, `timeline.py`, `dqmTimelineData.py`, …) remain checkout-only
  and are pending migration into these subpackages. `dqmFileData.py` is
  superseded by `dqm.hist`.
- matplotlib caches its font list under `MPLCONFIGDIR`, defaulting to the
  user's home. A service account with an unwritable or over-quota home gets a
  warning and a full font rescan on *every* render — slow, but never an
  outright failure, so it is easy to miss. `dqm.plot.static` redirects it when
  home is not writable; a systemd unit should set it explicitly.
- `TEfficiency` is listed among the histogram classes but uproot cannot
  convert it to a `Hist` — it is a pair of histograms plus a confidence model.
  `read()` raises rather than returning something subtly wrong; use
  `read_raw()`.

## Requirements

Python 3.9+, `pandas`, `requests`. Tested against pandas 2.3 (Python 3.9) and
pandas 3.0 (Python 3.11).
