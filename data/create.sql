--
-- should run as admin_role, which should own all objects
SET ROLE admin_role;

--
--
CREATE SCHEMA dqm;
GRANT USAGE ON SCHEMA dqm TO PUBLIC;

-- rows are sources of DQM values, typically files
CREATE TABLE dqm.sources (
  sid SERIAL, 
  process TEXT NOT NULL, 
  stream TEXT NOT NULL, 
  aggregation TEXT NOT NULL, 
  version TEXT NOT NULL,
  CONSTRAINT sources_unique_combo UNIQUE (process,stream,aggregation,version),
  CONSTRAINT sources_pk PRIMARY KEY (sid) 
  );
GRANT SELECT ON dqm.sources TO PUBLIC;
GRANT INSERT ON dqm.sources TO dqmwrite;
GRANT UPDATE ON dqm.sources_sid_seq TO dqmwrite;


-- rows are run/time intervals for an entry
CREATE TABLE dqm.intervals (
  iid SERIAL, 
  sid INTEGER NOT NULL, 
  start_run    INTEGER,
  start_subrun INTEGER,
  end_run    INTEGER,
  end_subrun INTEGER,
  start_time TIMESTAMP WITH TIME ZONE,
  end_time   TIMESTAMP WITH TIME ZONE,
  CONSTRAINT intervals_unique UNIQUE (
    sid,start_run,start_subrun,end_run,end_subrun,start_time,end_time),
  CONSTRAINT intervals_pk PRIMARY KEY (iid),
  CONSTRAINT intervals_sid_fk FOREIGN KEY (sid) REFERENCES dqm.sources(sid) 
  );
GRANT SELECT ON dqm.intervals TO PUBLIC;
GRANT INSERT ON dqm.intervals TO dqmwrite;
GRANT UPDATE ON dqm.intervals_iid_seq TO dqmwrite;


-- rows are files that the metrics of a source and interval were derived
-- from.  A sid,iid pair may have more than one file.
CREATE TABLE dqm.files (
  fid SERIAL,
  sid INTEGER NOT NULL,
  iid INTEGER NOT NULL,
  filename TEXT NOT NULL,
  CONSTRAINT files_pk PRIMARY KEY (fid),
  CONSTRAINT files_sid_fk FOREIGN KEY (sid) REFERENCES dqm.sources(sid),
  CONSTRAINT files_iid_fk FOREIGN KEY (iid) REFERENCES dqm.intervals(iid),
  CONSTRAINT files_unique UNIQUE (sid,iid,filename)
  );
GRANT SELECT ON dqm.files TO PUBLIC;
GRANT INSERT ON dqm.files TO dqmwrite;
GRANT UPDATE ON dqm.files_fid_seq TO dqmwrite;


-- rows are labels for DQM values
CREATE TABLE dqm.values
  (vid SERIAL,
  groupx TEXT NOT NULL, 
  subgroup TEXT NOT NULL, 
  namex TEXT NOT NULL, 
  CONSTRAINT values_pk PRIMARY KEY (vid),
  CONSTRAINT values_unique UNIQUE (groupx,subgroup,namex)
  );
GRANT SELECT ON dqm.values TO PUBLIC;
GRANT INSERT ON dqm.values TO dqmwrite;
GRANT UPDATE ON dqm.values_vid_seq TO dqmwrite;

-- rows are entries for DQM values
CREATE TABLE dqm.numbers (
  nid SERIAL,
  sid INTEGER NOT NULL, 
  iid INTEGER NOT NULL, 
  vid INTEGER NOT NULL, 
  valuex NUMERIC NOT NULL, 
  sigma NUMERIC, 
  code INTEGER,
  CONSTRAINT numbers_pk PRIMARY KEY (nid),
  CONSTRAINT numbers_vid_fk FOREIGN KEY (vid) REFERENCES dqm.values(vid),
  CONSTRAINT numbers_sid_fk FOREIGN KEY (sid) REFERENCES dqm.sources(sid),
  CONSTRAINT numbers_iid_fk FOREIGN KEY (iid) REFERENCES dqm.intervals(iid),
  CONSTRAINT numbers_unique UNIQUE (vid,sid,iid)
  );
GRANT SELECT ON dqm.numbers TO PUBLIC;
GRANT INSERT ON dqm.numbers TO dqmwrite;
GRANT UPDATE ON dqm.numbers_nid_seq TO dqmwrite;

-- rows are entries for DQM limits
CREATE TABLE dqm.limits (
 lid SERIAL,
 sid INTEGER NOT NULL,
 iid INTEGER NOT NULL,
 vid INTEGER NOT NULL,
 llimit NUMERIC NOT NULL,
 ulimit NUMERIC NOT NULL,
 sigma NUMERIC,
 alarmcode INTEGER,
 CONSTRAINT limits_pk PRIMARY KEY (lid),
 CONSTRAINT limits_vid_fk FOREIGN KEY (vid) REFERENCES dqm.values(vid),
 CONSTRAINT limits_sid_fk FOREIGN KEY (sid) REFERENCES dqm.sources(sid),
 CONSTRAINT limits_iid_fk FOREIGN KEY (iid) REFERENCES dqm.intervals(iid),
 CONSTRAINT limits_unique UNIQUE (vid,sid,iid)
 );
GRANT SELECT ON dqm.limits TO PUBLIC;
GRANT INSERT ON dqm.limits TO dqmwrite;
GRANT UPDATE ON dqm.limits_lid_seq TO dqmwrite;


-- rows are alarm episodes.  One row covers a condition from when it
-- was first seen until it stopped being extended, however many
-- intervals that spans.
CREATE TABLE dqm.alarms (
  aid SERIAL,
  -- identity: these four are what make two reports "the same alarm".
  -- None is nullable, which is what lets the uniqueness rule below be
  -- a single plain index.
  algo    TEXT NOT NULL,
  config  TEXT NOT NULL,
  subject TEXT NOT NULL,
  sid     INTEGER NOT NULL,
  -- max over this episode's causes, maintained on every extension
  level   INTEGER NOT NULL,
  -- Hull of what fired: run range, time range, or both, never neither.
  -- It does not claim that every run inside it alarmed; the causes are
  -- the ground truth.  NULL means no range of this kind, unlike
  -- dqm.intervals which stores -infinity.  These are queried by time
  -- overlap, where -infinity gives degenerate ranges.
  start_run    INTEGER,
  start_subrun INTEGER,
  end_run      INTEGER,
  end_subrun   INTEGER,
  start_time TIMESTAMP WITH TIME ZONE,
  end_time   TIMESTAMP WITH TIME ZONE,
  -- ctime: when the episode was opened.  mtime: when it was last
  -- extended.  The grace window is measured from mtime; its length is
  -- DqmAlarm::graceHours.
  ctime TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  mtime TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  -- merge machinery: true while the episode can still be extended.
  -- Separate from status, which is operator workflow: an episode stays
  -- active until someone acknowledges it, long past its window.
  open BOOLEAN NOT NULL DEFAULT true,
  -- operator workflow: active, acknowledged, silenced, retired,
  -- deleted.  Free text rather than a CHECK so the vocabulary grows
  -- without a migration; DqmAlarm enforces it.  retired and deleted
  -- are terminal and also clear open.
  status      TEXT NOT NULL DEFAULT 'active',
  status_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  -- algo-internal json, not queryable by contract.  print-alarms
  -- omits it unless asked: its commas and newlines make the csv hard
  -- to parse.
  note TEXT,
  CONSTRAINT alarms_pk PRIMARY KEY (aid),
  CONSTRAINT alarms_sid_fk FOREIGN KEY (sid) REFERENCES dqm.sources(sid),
  -- 0,1,2,3 = message, warn, alarm, severe
  CONSTRAINT alarms_level CHECK (level BETWEEN 0 AND 3),
  -- the same rule DqmInterval enforces in C++
  CONSTRAINT alarms_has_range
    CHECK (start_run IS NOT NULL OR start_time IS NOT NULL)
  );

-- At most one extendable episode per identity.  If two evaluators race
-- to open the same episode, the loser fails cleanly rather than
-- inserting a duplicate: it takes a unique violation, its transaction
-- rolls back, and commit-alarm returns non-zero.  That is deliberate.
-- The race needs two evaluators on one identity, which already means
-- something upstream is wrong, and a driver must not record a period
-- as done unless the commit returned 0.
CREATE UNIQUE INDEX alarms_one_open
  ON dqm.alarms (algo,config,subject,sid) WHERE open;

-- the usual display query: what is alarming, worst first
CREATE INDEX alarms_status_idx ON dqm.alarms (status,level,mtime);

GRANT SELECT ON dqm.alarms TO PUBLIC;
GRANT INSERT ON dqm.alarms TO dqmwrite;
-- unlike every other dqm table, alarm rows are mutable: episodes get
-- extended and operators change status
GRANT UPDATE ON dqm.alarms TO dqmwrite;
GRANT UPDATE ON dqm.alarms_aid_seq TO dqmwrite;


-- rows are the evidence for an episode: which interval, and which
-- variable if the test was about one variable.  This is the ground
-- truth that the episode's hull span only approximates.
-- No sid column: it would duplicate dqm.alarms.sid with nothing able
-- to keep them consistent.  No nid column: dqm.numbers is unique on
-- (vid,sid,iid), so a cause already identifies the number, and no
-- constraint could assert a stored nid matched this row.
CREATE TABLE dqm.alarm_causes (
  cid SERIAL,
  aid INTEGER NOT NULL,
  iid INTEGER NOT NULL,
  -- NULL for a global test: one about the interval as a whole, not
  -- about any single variable
  vid INTEGER,
  level INTEGER NOT NULL,
  CONSTRAINT causes_pk PRIMARY KEY (cid),
  CONSTRAINT causes_aid_fk FOREIGN KEY (aid) REFERENCES dqm.alarms(aid),
  CONSTRAINT causes_iid_fk FOREIGN KEY (iid) REFERENCES dqm.intervals(iid),
  CONSTRAINT causes_vid_fk FOREIGN KEY (vid) REFERENCES dqm.values(vid),
  CONSTRAINT causes_level CHECK (level BETWEEN 0 AND 3)
  );

-- Two partial indexes rather than one UNIQUE (aid,iid,vid): postgres
-- treats NULLs as distinct in a unique constraint, so a plain one
-- accepts duplicate global causes.  UNIQUE NULLS NOT DISTINCT does it
-- in one line but needs postgres 15; this server is 14.23.
CREATE UNIQUE INDEX causes_unique_var
  ON dqm.alarm_causes (aid,iid,vid) WHERE vid IS NOT NULL;
CREATE UNIQUE INDEX causes_unique_global
  ON dqm.alarm_causes (aid,iid) WHERE vid IS NULL;

GRANT SELECT ON dqm.alarm_causes TO PUBLIC;
GRANT INSERT ON dqm.alarm_causes TO dqmwrite;
GRANT UPDATE ON dqm.alarm_causes_cid_seq TO dqmwrite;


-- The triage query: an alarm's causes plus the measurements that
-- triggered them.  LEFT JOIN so global causes survive with a null
-- nid, since a null vid matches nothing.
CREATE VIEW dqm.alarm_cause_numbers AS
  SELECT c.cid, c.aid, a.sid, c.iid, c.vid, c.level,
         n.nid, n.valuex, n.sigma, n.code
  FROM dqm.alarm_causes c
  JOIN dqm.alarms a USING (aid)
  LEFT JOIN dqm.numbers n
    ON n.sid = a.sid AND n.iid = c.iid AND n.vid = c.vid;

GRANT SELECT ON dqm.alarm_cause_numbers TO PUBLIC;
