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
