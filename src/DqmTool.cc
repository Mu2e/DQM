#include "DQM/inc/DqmTool.hh"
#include "Offline/DbService/inc/DbIdList.hh"
#include "Offline/GeneralUtilities/inc/splitString.hh"
#include <boost/algorithm/string.hpp>
#include <boost/algorithm/string/classification.hpp>
#include <boost/algorithm/string/split.hpp>
#include <boost/tokenizer.hpp>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <string>

namespace {
// wrap a string in single quotes for use as an SQL literal, doubling
// any single quote it contains, as postgres expects
std::string sqlQuote(const std::string& str) {
  std::string out("'");
  for (char cc : str) {
    if (cc == '\'') out += '\'';
    out += cc;
  }
  out += "'";
  return out;
}

// an sql literal for a value that may be absent, where an empty string
// means database NULL.  quote=false for numeric columns.
std::string sqlOrNull(const std::string& str, bool quote = true) {
  if (str.empty()) return "NULL";
  return quote ? sqlQuote(str) : str;
}
}  // namespace

//***********************************************************

int mu2e::DqmTool::init() {
  DbIdList idList;  // read the connections info file
  DbId id = idList.getDbId("mu2e_dqm_prd");

  _reader.setDbId(id);
  _reader.setUseCache(false);
  _reader.setVerbose(_verbose);
  _reader.setTimeVerbose(_verbose);

  _sql.setDbId(id);
  _sql.setVerbose(_verbose);

  return 0;
}

//***********************************************************

int mu2e::DqmTool::commitValue(const std::string& sources,
                               const std::string& runss,
                               const std::string& start, const std::string& end,
                               const std::string& valuestr,
                               const std::string& filestr) {
  int rc;

  // **** interpret source (process/stream/aggregation/version)

  std::string ss = sources;
  if (ss.empty()) {
    std::cout << "ERROR - commit-value requires --source" << std::endl;
    return 1;
  }

  // take the ss string and parse it into proces/stream, etc, fields
  DqmSource source(ss);

  // **** interpret time interval

  std::string rn = runss;
  std::string st = start;
  std::string en = end;

  // must have some time or run restriction
  if (rn.empty() && st.empty()) {
    std::cout << "ERROR - commit-value requires one of --runs or --start"
              << std::endl;
    return 1;
  }
  if (st.empty() && !en.empty()) {
    std::cout << "ERROR - commit-value --end is non-empty but --start is "
                 "empty (opposite is allowed)"
              << std::endl;
    return 1;
  }
  // if there is a start time, but no end time, then set end to start
  if (!st.empty() && en.empty()) en = st;
  // if no times, set to irrelevent (there should still be a run range)
  if (st.empty() && en.empty()) {
    st = "-infinity";
    en = "-infinity";
  }
  // if no run info given, set start and stop to 0
  if (rn.empty()) rn = "EMPTY";

  // container for time
  DqmInterval interval(rn, st, en);

  // **** interpret values
  std::string vv = valuestr;

  if (vv.empty()) {
    std::cout << "ERROR - commit-value requires --value" << std::endl;
    return 1;
  }

  if (_verbose > 2) {
    std::cout << "Running commit-value with parameters:" << std::endl;
    std::cout << "source :" << ss << std::endl;
    std::cout << "runs   :" << rn << std::endl;
    std::cout << "start  :" << st << std::endl;
    std::cout << "end    :" << en << std::endl;
    std::cout << "value : " << vv << std::endl;
    std::cout << "file  : " << filestr << std::endl;
  }

  // collect the list of values from a file, if needed
  StringVec values;

  int nComm = std::count(vv.begin(), vv.end(), ',');

  if (nComm > 0) {
    values.emplace_back(vv);
  } else {
    std::ifstream myfile;
    myfile.open(vv);
    if (!myfile.is_open()) {
      std::cout << "ERROR - failed to open file " << vv << std::endl;
      return 1;
    }
    std::string line;
    while (std::getline(myfile, line)) {
      if (!line.empty()) values.emplace_back(line);
    }
    if (_verbose > 2) {
      std::cout << "Read " << values.size() << " values from " << vv
                << std::endl;
    }
  }

  // lookup or create, if necessary, the 4 table entries
  // this doesn't need to be a transaction since each step is atomic

  std::string command, result;
  rc = _sql.connect();
  if (rc) return rc;

  command = "SET ROLE dqmWrite;";
  rc = _sql.execute(command, result);
  if (rc) return rc;

  rc = locateSource(source);
  if (rc) return rc;

  interval.setSid(source.sid());
  rc = locateInterval(interval);
  if (rc) return rc;

  // now that we have the sid and iid, record which file, if any,
  // these metrics were derived from
  if (!filestr.empty()) {
    DqmFile file(filestr, source.sid(), interval.iid());
    rc = locateFile(file);
    if (rc) return rc;
  }

  for (auto const& vvs : values) {
    // take a string like "cal,disk0,menaE,20.0,0.1,0"
    // validate and split it into fields
    StringVec sv = splitString(vvs);
    if (sv.size() != 6) {
      std::cout << "Error - input value is not 6 fields " << vvs << "\n";
      return 1;
    }
    DqmValue value(sv[0], sv[1], sv[2]);
    rc = locateValue(value);
    if (rc) return rc;
    DqmNumber number(sv[3], sv[4], sv[5]);
    number.setSid(source.sid());
    number.setIid(interval.iid());
    number.setVid(value.vid());
    rc = insertNumber(number);
    if (rc) return rc;
  }

  rc = _sql.disconnect();
  if (rc) return rc;

  return 0;
}

//***********************************************************

int mu2e::DqmTool::commitLimit(const std::string& sources,
                               const std::string& runss,
                               const std::string& start, const std::string& end,
                               const std::string& limitstr) {
  int rc;

  // **** interpret source (process/stream/aggregation/version)

  std::string ss = sources;
  if (ss.empty()) {
    std::cout << "ERROR - commit-limit requires --source" << std::endl;
    return 1;
  }

  // take the ss string and parse it into proces/stream, etc, fields
  DqmSource source(ss);

  // **** interpret time interval

  std::string rn = runss;
  std::string st = start;
  std::string en = end;

  // must have some time or run restriction
  if (rn.empty() && st.empty()) {
    std::cout << "ERROR - commit-limit requires one of --runs or --start"
              << std::endl;
    return 1;
  }
  if (st.empty() && !en.empty()) {
    std::cout << "ERROR - commit-limit --end is non-empty but --start is "
                 "empty (opposite is allowed)"
              << std::endl;
    return 1;
  }
  // if there is a start time, but no end time, then set end to start
  if (!st.empty() && en.empty()) en = st;
  // if no times, set to irrelevent (there should still be a run range)
  if (st.empty() && en.empty()) {
    st = "-infinity";
    en = "-infinity";
  }
  // if no run info given, set start and stop to 0
  if (rn.empty()) rn = "EMPTY";

  // container for time
  DqmInterval interval(rn, st, en);

  // **** interpret values
  std::string vv = limitstr;

  if (vv.empty()) {
    std::cout << "ERROR - commit-limit requires --limit" << std::endl;
    return 1;
  }

  if (_verbose > 2) {
    std::cout << "Running commit-limit with parameters:" << std::endl;
    std::cout << "source :" << ss << std::endl;
    std::cout << "runs   :" << rn << std::endl;
    std::cout << "start  :" << st << std::endl;
    std::cout << "end    :" << en << std::endl;
    std::cout << "limit : " << vv << std::endl;
  }

  // collect the list of values from a file, if needed
  StringVec limits;

  int nComm = std::count(vv.begin(), vv.end(), ',');

  if (nComm > 0) {
    limits.emplace_back(vv);
  } else {
    std::ifstream myfile;
    myfile.open(vv);
    if (!myfile.is_open()) {
      std::cout << "ERROR - failed to open file " << vv << std::endl;
      return 1;
    }
    std::string line;
    while (std::getline(myfile, line)) {
      if (!line.empty()) limits.emplace_back(line);
    }
    if (_verbose > 2) {
      std::cout << "Read " << limits.size() << " limits from " << vv
                << std::endl;
    }
  }

  // lookup or create, if necessary, the 4 table entries
  // this doesn't need to be a transaction since each step is atomic

  std::string command, result;
  rc = _sql.connect();
  if (rc) return rc;

  command = "SET ROLE dqmWrite;";
  rc = _sql.execute(command, result);
  if (rc) return rc;

  rc = locateSource(source);
  if (rc) return rc;

  interval.setSid(source.sid());
  rc = locateInterval(interval);
  if (rc) return rc;

  for (auto const& vvs : limits) {
    // take a string like "cal,disk0,meanE,10.0,30.0,2.5,0"
    // validate and split it into fields
    StringVec sv = splitString(vvs);
    if (sv.size() != 7) {
      std::cout << "Error - input value is not 7 fields " << vvs << "\n";
      return 1;
    }
    DqmValue value(sv[0], sv[1], sv[2]);
    rc = locateValue(value);
    if (rc) return rc;
    DqmLimit limit(sv[3], sv[4], sv[5], sv[6]);
    limit.setSid(source.sid());
    limit.setIid(interval.iid());
    limit.setVid(value.vid());
    rc = insertLimit(limit);
    if (rc) return rc;
  }

  rc = _sql.disconnect();
  if (rc) return rc;

  return 0;
}

//***********************************************************

// Take one finding from one evaluator instance and record it.  The
// evaluator supplies the subject and the causes; algo, config and sid
// identify the instance.  Identity is the four together, and a finding
// either extends the episode it matches inside the grace window or
// opens a new one.

int mu2e::DqmTool::commitAlarm(const std::string& algos,
                               const std::string& configs,
                               const std::string& subjects,
                               const std::string& sids,
                               const std::string& causestr,
                               const std::string& note) {
  int rc;

  // **** interpret the evaluator identity

  if (algos.empty() || configs.empty() || subjects.empty() || sids.empty()) {
    std::cout << "ERROR - commit-alarm requires --algo, --config, --subject "
                 "and --sid"
              << std::endl;
    return 1;
  }
  if (sids.find_first_not_of("0123456789") != std::string::npos) {
    std::cout << "ERROR - commit-alarm --sid is not an integer: " << sids
              << std::endl;
    return 1;
  }
  int sid = std::stoi(sids);

  DqmAlarm alarm(algos, configs, subjects, sid);
  alarm.setNote(note);

  // **** interpret the causes

  if (causestr.empty()) {
    std::cout << "ERROR - commit-alarm requires --cause" << std::endl;
    return 1;
  }

  // a csv string, or a filespec of a text file of them, as --value does
  StringVec lines;
  if (std::count(causestr.begin(), causestr.end(), ',') > 0) {
    lines.emplace_back(causestr);
  } else {
    std::ifstream myfile;
    myfile.open(causestr);
    if (!myfile.is_open()) {
      std::cout << "ERROR - failed to open file " << causestr << std::endl;
      return 1;
    }
    std::string line;
    while (std::getline(myfile, line)) {
      if (!line.empty()) lines.emplace_back(line);
    }
  }

  DqmCauseCollection causes;
  for (auto const& line : lines) {
    causes.emplace_back(DqmCause(line));
  }

  // a finding must have at least one cause
  if (causes.empty()) {
    std::cout << "ERROR - commit-alarm found no causes in " << causestr
              << std::endl;
    return 1;
  }

  if (_verbose > 2) {
    std::cout << "Running commit-alarm with parameters:" << std::endl;
    std::cout << "algo    :" << algos << std::endl;
    std::cout << "config  :" << configs << std::endl;
    std::cout << "subject :" << subjects << std::endl;
    std::cout << "sid     :" << sids << std::endl;
    std::cout << "causes  :" << causes.size() << std::endl;
    std::cout << "note    :" << note << std::endl;
  }

  // **** write it

  std::string command, result;
  rc = _sql.connect();
  if (rc) return rc;

  command = "SET ROLE dqmWrite;";
  rc = _sql.execute(command, result);
  if (rc) return rc;

  // Level and hull span come from the causes' own intervals, so they
  // cannot drift from the evidence.  This also validates the causes,
  // and runs before BEGIN: it is the one step that fails on a check of
  // ours rather than an sql error, and must leave no open transaction.
  rc = spanFromCauses(alarm, causes);
  if (rc) return rc;

  // Unlike the other commit paths this one needs a transaction, since
  // matching an episode and then extending or inserting it is not one
  // atomic step.  Every failure past here is an sql error, and
  // DbSql::execute disconnects on those, aborting the transaction, so
  // the early returns cannot leave a half-written episode.
  command = "BEGIN;";
  rc = _sql.execute(command, result);
  if (rc) return rc;

  rc = matchAlarm(alarm);
  if (rc) return rc;

  if (alarm.aid() >= 0) {
    rc = extendAlarm(alarm);
    if (rc) return rc;
  } else {
    rc = insertAlarm(alarm);
    if (rc) return rc;
  }

  for (auto& cause : causes) {
    rc = insertCause(cause, alarm.aid());
    if (rc) return rc;
  }

  command = "COMMIT;";
  rc = _sql.execute(command, result);
  if (rc) return rc;

  rc = _sql.disconnect();
  if (rc) return rc;

  return 0;
}

//***********************************************************

// set an episode's operator status.  This is deliberately independent
// of open, which is merge machinery - acknowledging an alarm does not
// make it extendable or unextendable.

int mu2e::DqmTool::alarmStatus(const std::string& aids,
                               const std::string& status) {
  if (aids.empty() || status.empty()) {
    std::cout << "ERROR - alarm-status requires --aid and --status"
              << std::endl;
    return 1;
  }
  if (aids.find_first_not_of("0123456789") != std::string::npos) {
    std::cout << "ERROR - alarm-status --aid is not an integer: " << aids
              << std::endl;
    return 1;
  }
  if (!DqmAlarm::validStatus(status)) {
    std::cout << "ERROR - alarm-status --status must be one of "
              << DqmAlarm::statusList() << ", got " << status << std::endl;
    return 1;
  }

  std::string command, result;
  int rc = _sql.connect();
  if (rc) return rc;

  command = "SET ROLE dqmWrite;";
  rc = _sql.execute(command, result);
  if (rc) return rc;

  // retired and deleted are terminal, so they close the episode too: a
  // later matching finding starts a fresh one rather than resurrecting
  // this one.  active, acknowledged and silenced leave open alone, so
  // an acknowledged problem that is still going on keeps extending
  // rather than spawning duplicate episodes.
  bool terminal = DqmAlarm::terminalStatus(status);

  // RETURNING so that an aid matching no row is reported rather than
  // silently doing nothing
  command = "UPDATE dqm.alarms SET status=" + sqlQuote(status) +
            ", status_time=now()";
  if (terminal) command += ", open=false";
  command += " WHERE aid=" + aids + " RETURNING aid;";

  rc = _sql.execute(command, result);
  if (rc) return rc;

  if (result.empty()) {
    std::cout << "ERROR - no alarm with aid " << aids << std::endl;
    return 1;
  }

  if (_verbose > 0) {
    std::cout << "aid " << aids << " status set to " << status
              << (terminal ? " and closed" : "") << std::endl;
  }

  rc = _sql.disconnect();
  if (rc) return rc;

  return 0;
}

//***********************************************************

int mu2e::DqmTool::printSources(bool heading) {
  int rc = readTable("dqm.sources", _result);
  if (heading) {
    _result = "sid, process, stream, aggregation, version\n" + _result;
  }
  return rc;
}

//***********************************************************
int mu2e::DqmTool::printIntervals(bool heading) {
  int rc = readTable("dqm.intervals", _result);
  if (heading) {
    _result =
        "iid, sid, start_run, start_subrun, end_run, end_subrun, start_time, "
        "end_time\n" +
        _result;
  }
  return rc;
}

//***********************************************************

int mu2e::DqmTool::printValues(bool heading) {
  int rc = readTable("dqm.values", _result);
  if (heading) {
    _result = "vid, group, subgroup, name\n" + _result;
  }
  return rc;
}

//***********************************************************

int mu2e::DqmTool::printFiles(bool heading) {
  int rc = readTable("dqm.files", _result);
  if (heading) {
    _result = "fid, sid, iid, filename\n" + _result;
  }
  return rc;
}

//***********************************************************

int mu2e::DqmTool::printAlarms(bool heading, bool note, bool live) {
  // note holds algo-internal json, whose commas and newlines make the
  // query engine's csv awkward to parse downstream, so it is named
  // explicitly rather than arriving with a select *
  std::string select(
      "aid,algo,config,subject,sid,level,"
      "start_run,start_subrun,end_run,end_subrun,start_time,end_time,"
      "ctime,mtime,open,status,status_time");
  if (note) select += ",note";

  // live means not in a terminal state.  The terminal statuses come
  // from the vocabulary rather than being repeated here, so a status
  // added there is picked up by this selection too.
  StringVec where;
  if (live) {
    for (auto const& sv : DqmAlarm::statusValues()) {
      if (DqmAlarm::terminalStatus(sv)) where.emplace_back("status:ne:" + sv);
    }
  }

  int rc = readTable("dqm.alarms", _result, select, where);
  if (heading) {
    _result = select + "\n" + _result;
  }
  return rc;
}

//***********************************************************

int mu2e::DqmTool::printCauses(bool heading, bool numbers,
                               const std::string& aid) {
  // the view joins each cause to the measurement that triggered it
  std::string table(numbers ? "dqm.alarm_cause_numbers" : "dqm.alarm_causes");
  std::string select(numbers ? "cid,aid,sid,iid,vid,level,nid,valuex,sigma,code"
                             : "cid,aid,iid,vid,level");

  StringVec where;
  if (!aid.empty()) {
    if (aid.find_first_not_of("0123456789") != std::string::npos) {
      std::cout << "ERROR - print-causes --aid is not an integer: " << aid
                << std::endl;
      return 1;
    }
    where.emplace_back("aid:eq:" + aid);
  }

  int rc = readTable(table, _result, select, where);
  if (heading) {
    _result = select + "\n" + _result;
  }
  return rc;
}

//***********************************************************

int mu2e::DqmTool::printNumbers(const std::string& name, bool heading, const std::string& sources,
                                const std::string& values, const bool& expand) {
  int rc = 0;

  int sid = -1;
  if (!sources.empty()) {
    std::string ss = sources;
    if (ss.find_first_not_of("0123456789") == std::string::npos) {
      sid = std::stoi(ss);  // was an integer
    } else {                // is csv
      DqmSource source(ss);
      lookupSid(source);
      sid = source.sid();
      if (sid < 0) {
        std::cout << "ERROR - source could not be interpreted:" << ss << "\n";
        return 1;
      }
    }
  }

  int vid = -1;
  if (!values.empty()) {
    std::string vv = values;
    if (vv.find_first_not_of("0123456789") == std::string::npos) {
      vid = std::stoi(vv);  // was an integer
    } else {                // is csv
      DqmValue value(vv);
      lookupVid(value);
      vid = value.vid();
      if (vid < 0) {
        std::cout << "ERROR - value could not be interpreted" << std::endl;
        return 1;
      }
    }
  }

  std::string table = "dqm."+name;
  std::string select,order;
  StringVec where;
  if (sid >= 0) where.emplace_back("sid:eq:" + std::to_string(sid));
  if (vid >= 0) where.emplace_back("vid:eq:" + std::to_string(vid));
  if(name=="numbers") {
    order = std::string("sid,nid,iid");
  } else {
    order = std::string("sid,lid,iid");
  }

  std::string result;
  rc = _reader.query(result, select, table, where, order);
  if (rc) return rc;

  if (!expand) {
    if (heading) {
      if(name=="numbers") {
        _result = "nid,sid,iid,vid,value,sigma,code\n" + result;
      } else {
        _result = "nid,sid,iid,vid,llimit,ulimit,sigma,alarmcode\n" + result;
      }
    } else {
      _result = result;
    }
    return 0;
  }

  // if we came here, then we have to --expand the printout
  // to include the text of source, value and interval
  std::map<int, std::string> smap, vmap, imap;
  std::string csv;
  StringVec lines, cols;

  csv.clear();
  readTable("dqm.sources", csv);
  lines = splitString(csv, "\n");
  lines.pop_back();  // last entry is blank
  for (auto const& line : lines) {
    cols = splitString(line);
    smap[std::stoi(cols[0])] = line;
  }

  csv.clear();
  readTable("dqm.values", csv);
  lines = splitString(csv, "\n");
  lines.pop_back();  // last entry is blank
  for (auto const& line : lines) {
    cols = splitString(line);
    vmap[std::stoi(cols[0])] = line;
  }

  csv.clear();
  readTable("dqm.intervals", csv);
  lines = splitString(csv, "\n");
  lines.pop_back();  // last entry is blank
  for (auto const& line : lines) {
    cols = splitString(line);
    imap[std::stoi(cols[0])] = line;
  }

  _result.clear();
  if (heading) {
    if(name=="numbers") {
      _result = "nid,value,sigma,code,sid,proc,stream,agg,ver,vid,group,hist,metric,iid,sid,start_run,start_sub,stop_run,stop_sub,start_time,stop_time\n";
    } else {
      _result = "nid,lower_lim,upper_lim,sigma,alarmcode,sid,proc,stream,agg,ver,vid,group,hist,metric,iid,sid,start_run,start_sub,stop_run,stop_sub,start_time,stop_time\n";
    }
  }

  auto rsv = splitString(result, "\n");
  rsv.pop_back();  // last entry is blank
  std::ostringstream oss;
  for (auto const& rs : rsv) {
    // numbers
    // nid,sid,iid,vid,valuex,sigma,code
    // limits
    // lid,sid,iid,vid,llimit,ulimit,sigma,alarmcode
    auto rss = splitString(rs, ",");
    oss.clear();
    oss.str("");
    if(name=="numbers") {
      oss << rss[0] << "," << rss[4] << "," << rss[5] << "," << rss[6];
    } else {
      oss << rss[0] << "," << rss[4] << "," << rss[5] << "," << rss[6] << "," << rss[7];
    }
    int ind;
    ind = std::stoi(rss[1]);
    oss << ", " << smap[ind];
    ind = std::stoi(rss[3]);
    oss << ", " << vmap[ind];
    ind = std::stoi(rss[2]);
    oss << ", " << imap[ind] << "\n";
    _result.append(oss.str());
  }

  return 0;
}

//***********************************************************
int mu2e::DqmTool::readTable(const std::string& table, std::string& result,
                             const std::string& select,
                             const StringVec& where) {
  std::string order;
  int rc = _reader.query(result, select, table, where, order);
  return rc;
}

//***********************************************************

int mu2e::DqmTool::lookupSid(DqmSource& source) {
  if (source.sid() >= 0) return 0;
  std::string table = "dqm.sources";
  std::string select = "sid";
  StringVec where;
  std::string order;
  std::string csv;
  where.emplace_back("process:eq:" + source.process());
  where.emplace_back("stream:eq:" + source.stream());
  where.emplace_back("aggregation:eq:" + source.aggregation());
  where.emplace_back("version:eq:" + source.version());
  int rc = _reader.query(csv, select, table, where, order);
  if (rc) return rc;
  if (_verbose > 4) {
    std::cout << "lookupSid sends " << source.csv() << "\n";
    std::cout << "    and gets " << csv << "\n";
  }
  if (!csv.empty()) {
    source.setSid(std::stoi(csv));
  }
  return 0;
}

//***********************************************************

int mu2e::DqmTool::locateSource(DqmSource& source) {
  std::string command, result;

  command = "select sid from dqm.sources where process='" + source.process() +
            "' and stream='" + source.stream() + "' and aggregation='" +
            source.aggregation() + "' and version='" + source.version() + "';";

  int rc = _sql.execute(command, result);
  if (rc) return rc;

  if (result.empty()) {
    command =
        "INSERT INTO dqm.sources (process,stream,aggregation,version)  "
        "VALUES "
        "('" +
        source.process() + "','" + source.stream() + "','" +
        source.aggregation() + "','" + source.version() + "') RETURNING sid;";

    rc = _sql.execute(command, result);
    if (rc) return rc;
  }

  int sid = std::stoi(result);

  if (_verbose > 1) {
    std::cout << "sid is " << sid << std::endl;
  }
  source.setSid(sid);
  return 0;
}

//***********************************************************
int mu2e::DqmTool::lookupIid(DqmInterval& interval) {
  if (interval.iid() >= 0) return 0;
  std::string table = "dqm.intervals";
  std::string select = "iid";
  StringVec where;
  std::string order;
  std::string csv;
  where.emplace_back("sid:eq:" + std::to_string(interval.sid()));
  where.emplace_back("start_run:eq:" +
                     std::to_string(interval.iov().startRun()));
  where.emplace_back("start_subrun:eq:" +
                     std::to_string(interval.iov().startSubrun()));
  where.emplace_back("end_run:eq:" + std::to_string(interval.iov().endRun()));
  where.emplace_back("end_subrun:eq:" +
                     std::to_string(interval.iov().endRun()));
  where.emplace_back("start_time:eq:" + interval.startTime());
  where.emplace_back("end_time:eq:" + interval.endTime());

  int rc = _reader.query(csv, select, table, where, order);
  if (rc) return rc;
  if (_verbose > 4) {
    std::cout << "lookupIid sends " << interval.csv() << "\n";
    std::cout << "    and gets " << csv << "\n";
  }
  if (!csv.empty()) {
    interval.setIid(std::stoi(csv));
  }
  return 0;
}

//***********************************************************
int mu2e::DqmTool::locateInterval(DqmInterval& interval) {
  std::string command, result;

  if (interval.sid() < 0) {
    std::cout << "Error - can't locate interval with no sid\n";
    return 1;
  }

  command =
      "select iid from dqm.intervals where sid=" +
      std::to_string(interval.sid()) +
      " and start_run=" + std::to_string(interval.iov().startRun()) +
      " and start_subrun=" + std::to_string(interval.iov().startSubrun()) +
      " and end_run=" + std::to_string(interval.iov().endRun()) +
      " and end_subrun=" + std::to_string(interval.iov().endSubrun()) +
      " and start_time='" + interval.startTime() + "'" + " and end_time='" +
      interval.endTime() + "';";
  int rc = _sql.execute(command, result);
  if (rc) return rc;

  if (result.empty()) {
    std::string command =
        "INSERT INTO dqm.intervals "
        "(sid,start_run,start_subrun,end_run,end_subrun,start_time,end_time) "
        " "
        "VALUES (" +
        std::to_string(interval.sid()) + "," +
        std::to_string(interval.iov().startRun()) + "," +
        std::to_string(interval.iov().startSubrun()) + "," +
        std::to_string(interval.iov().endRun()) + "," +
        std::to_string(interval.iov().endSubrun()) + ",'" +
        interval.startTime() + "','" + interval.endTime() + "') RETURNING iid;";
    rc = _sql.execute(command, result);
    if (rc) return rc;
  }

  int iid = std::stoi(result);

  if (_verbose > 0) {
    std::cout << "iid is " << iid << std::endl;
  }
  interval.setIid(iid);
  return 0;
}

//***********************************************************

int mu2e::DqmTool::lookupVid(DqmValue& value) {
  if (value.vid() >= 0) return 0;
  std::string table = "dqm.values";
  std::string select = "vid";
  StringVec where;
  std::string order;
  std::string csv;
  where.emplace_back("groupx:eq:" + value.group());
  where.emplace_back("subgroup:eq:" + value.subgroup());
  where.emplace_back("namex:eq:" + value.name());
  int rc = _reader.query(csv, select, table, where, order);
  if (rc) return rc;

  if (_verbose > 4) {
    std::cout << "lookupVid sends " << value.csv() << "\n";
    std::cout << "    and gets " << csv << "\n";
  }
  if (!csv.empty()) {
    value.setVid(std::stoi(csv));
  }

  return 0;
}

//***********************************************************

int mu2e::DqmTool::locateValue(DqmValue& value) {
  std::string command, result;

  command = "select vid from dqm.values where groupx='" + value.group() +
            "' and subgroup='" + value.subgroup() + "' and namex='" +
            value.name() + "';";
  int rc = _sql.execute(command, result);
  if (rc) return rc;

  if (result.empty()) {
    std::string command =
        "INSERT INTO dqm.values (groupx,subgroup,namex)  VALUES ('" +
        value.group() + "','" + value.subgroup() + "','" + value.name() +
        "') RETURNING vid;";
    rc = _sql.execute(command, result);
    if (rc) return rc;
  }

  int vid = std::stoi(result);

  if (_verbose > 1) {
    std::cout << "vid is " << vid << std::endl;
  }
  value.setVid(vid);
  return 0;
}

//***********************************************************

// A sid,iid pair may have several files, so this does not replace any
// row already there.  Committing the same file again is not an error,
// it simply finds the existing row instead of inserting a duplicate.

int mu2e::DqmTool::locateFile(DqmFile& file) {
  std::string command, result;

  if (file.sid() < 0 || file.iid() < 0) {
    std::cout << "Error - can't locate file with no sid or iid\n";
    return 1;
  }

  std::string name = sqlQuote(file.name());

  command = "select fid from dqm.files where sid=" +
            std::to_string(file.sid()) +
            " and iid=" + std::to_string(file.iid()) + " and filename=" + name +
            ";";
  int rc = _sql.execute(command, result);
  if (rc) return rc;

  if (result.empty()) {
    command = "INSERT INTO dqm.files (sid,iid,filename)  VALUES (" +
              std::to_string(file.sid()) + "," + std::to_string(file.iid()) +
              "," + name + ") RETURNING fid;";
    rc = _sql.execute(command, result);
    if (rc) return rc;
  }

  int fid = std::stoi(result);

  if (_verbose > 0) {
    std::cout << "fid is " << fid << std::endl;
  }
  file.setFid(fid);
  return 0;
}

//***********************************************************

int mu2e::DqmTool::insertNumber(DqmNumber& number) {
  std::string command =
      "INSERT INTO dqm.numbers (sid,iid,vid,valuex,sigma,code)  VALUES (" +
      std::to_string(number.sid()) + "," + std::to_string(number.iid()) + "," +
      std::to_string(number.vid()) + ",'" + number.valueStr() + "','" +
      number.sigmaStr() + "'," + number.codeStr() + ") RETURNING nid;";

  std::string result;
  int rc = _sql.execute(command, result);
  if (rc) return rc;

  int nid = std::stoi(result);

  if (_verbose > 0) {
    std::cout << "new nid is " << nid << std::endl;
  }

  number.setNid(nid);
  return 0;
}

//***********************************************************

int mu2e::DqmTool::insertLimit(DqmLimit& limit) {
  std::string command =
      "INSERT INTO dqm.limits (sid,iid,vid,llimit,ulimit,sigma,alarmcode)  VALUES (" +
      std::to_string(limit.sid()) + "," + std::to_string(limit.iid()) + "," +
      std::to_string(limit.vid()) + ",'" +
    limit.llimitStr() + "','" +
    limit.ulimitStr() + "','" +
    limit.sigmaStr() + "'," + limit.alarmcodeStr() + ") RETURNING lid;";

  std::string result;
  int rc = _sql.execute(command, result);
  if (rc) return rc;

  int lid = std::stoi(result);

  if (_verbose > 0) {
    std::cout << "new lid is " << lid << std::endl;
  }

  limit.setLid(lid);
  return 0;
}

//***********************************************************

// Fill in the episode's level and hull span from the intervals its
// causes point at, so neither can drift from the evidence.  Also the
// only place a cause pointing at another source's interval is caught,
// since dqm.alarm_causes has no sid of its own.

int mu2e::DqmTool::spanFromCauses(DqmAlarm& alarm,
                                  const DqmCauseCollection& causes) {
  std::set<int> iids;
  for (auto const& cause : causes) iids.insert(cause.iid());

  std::string list;
  for (auto iid : iids) {
    if (!list.empty()) list += ",";
    list += std::to_string(iid);
  }

  // The hull takes min/max of each column independently, which can be
  // slightly wider than the true extreme (run,subrun) pair.  That is
  // acceptable: it is a hull, and the causes are the ground truth.
  // start_run=0 is DbIoV's null and -infinity is how dqm.intervals
  // records an absent time range; both become NULL, which is what
  // dqm.alarms uses for an absent range.
  std::string command =
      "SELECT count(*), count(*) FILTER (WHERE sid=" +
      std::to_string(alarm.sid()) +
      "),"
      " min(start_run) FILTER (WHERE start_run>0),"
      " min(start_subrun) FILTER (WHERE start_run>0),"
      " max(end_run) FILTER (WHERE start_run>0),"
      " max(end_subrun) FILTER (WHERE start_run>0),"
      " min(start_time) FILTER (WHERE start_time<>'-infinity'),"
      " max(end_time) FILTER (WHERE end_time<>'-infinity')"
      " FROM dqm.intervals WHERE iid IN (" +
      list + ");";

  std::string result;
  int rc = _sql.execute(command, result);
  if (rc) return rc;

  StringVec sv = splitString(result, ",");
  if (sv.size() != 8) {
    std::cout << "Error - unexpected interval span result: " << result << "\n";
    return 1;
  }

  if (std::stoul(sv[0]) != iids.size()) {
    std::cout << "Error - some cause iids do not exist, found " << sv[0]
              << " of " << iids.size() << "\n";
    return 1;
  }
  if (sv[1] != sv[0]) {
    std::cout << "Error - some cause intervals do not belong to sid "
              << alarm.sid() << "\n";
    return 1;
  }

  alarm.setRuns(sv[2], sv[3], sv[4], sv[5]);
  alarm.setTimes(sv[6], sv[7]);

  if (!alarm.hasRange()) {
    std::cout << "Error - the cause intervals have neither a run range nor a "
                 "time range\n";
    return 1;
  }

  int level = 0;
  for (auto const& cause : causes) level = std::max(level, cause.level());
  alarm.setLevel(level);

  if (_verbose > 1) {
    std::cout << "span runs " << sv[2] << ":" << sv[3] << "-" << sv[4] << ":"
              << sv[5] << " times " << sv[6] << " to " << sv[7] << " level "
              << level << std::endl;
  }

  return 0;
}

//***********************************************************

// Find the episode this finding continues, if there is one.  The grace
// window is wall clock, measured from mtime, not run adjacency: an
// evaluator sees runs out of order and cannot know whether a run it
// has not seen will ever arrive.

int mu2e::DqmTool::matchAlarm(DqmAlarm& alarm) {
  std::string command =
      "select aid from dqm.alarms where algo=" + sqlQuote(alarm.algo()) +
      " and config=" + sqlQuote(alarm.config()) +
      " and subject=" + sqlQuote(alarm.subject()) +
      " and sid=" + std::to_string(alarm.sid()) +
      " and open and mtime > now() - interval '" +
      std::to_string(DqmAlarm::graceHours) + " hours'"
      " order by mtime desc limit 1;";

  std::string result;
  int rc = _sql.execute(command, result);
  if (rc) return rc;

  if (!result.empty()) {
    alarm.setAid(std::stoi(result));
    if (_verbose > 0) {
      std::cout << "extending aid " << alarm.aid() << std::endl;
    }
  }

  return 0;
}

//***********************************************************

int mu2e::DqmTool::extendAlarm(const DqmAlarm& alarm) {
  // LEAST and GREATEST ignore NULL arguments in postgres, so the hull
  // widens correctly whether or not the stored episode and the new
  // finding each have a range of that kind
  std::string command =
      "UPDATE dqm.alarms SET level=GREATEST(level," +
      std::to_string(alarm.level()) + "), start_run=LEAST(start_run," +
      sqlOrNull(alarm.startRun(), false) + "), start_subrun=LEAST(start_subrun," +
      sqlOrNull(alarm.startSubrun(), false) + "), end_run=GREATEST(end_run," +
      sqlOrNull(alarm.endRun(), false) + "), end_subrun=GREATEST(end_subrun," +
      sqlOrNull(alarm.endSubrun(), false) + "), start_time=LEAST(start_time," +
      sqlOrNull(alarm.startTime()) + "), end_time=GREATEST(end_time," +
      sqlOrNull(alarm.endTime()) + "), mtime=now() WHERE aid=" +
      std::to_string(alarm.aid()) + " RETURNING aid;";

  std::string result;
  int rc = _sql.execute(command, result);
  if (rc) return rc;

  if (result.empty()) {
    std::cout << "Error - failed to extend aid " << alarm.aid() << "\n";
    return 1;
  }

  return 0;
}

//***********************************************************

int mu2e::DqmTool::insertAlarm(DqmAlarm& alarm) {
  // Nothing extendable matched, so this finding starts a new episode.
  // Any episode with the same identity still flagged open but outside
  // the window is closed first, or alarms_one_open rejects the insert.
  // open is maintained lazily rather than by a sweeper, which is why
  // queries test mtime as well.
  std::string command =
      "UPDATE dqm.alarms SET open=false where algo=" + sqlQuote(alarm.algo()) +
      " and config=" + sqlQuote(alarm.config()) +
      " and subject=" + sqlQuote(alarm.subject()) +
      " and sid=" + std::to_string(alarm.sid()) + " and open;";

  std::string result;
  int rc = _sql.execute(command, result);
  if (rc) return rc;

  // ctime, mtime, open, status and status_time take their defaults
  command =
      "INSERT INTO dqm.alarms (algo,config,subject,sid,level,"
      "start_run,start_subrun,end_run,end_subrun,start_time,end_time,note) "
      "VALUES (" +
      sqlQuote(alarm.algo()) + "," + sqlQuote(alarm.config()) + "," +
      sqlQuote(alarm.subject()) + "," + std::to_string(alarm.sid()) + "," +
      std::to_string(alarm.level()) + "," +
      sqlOrNull(alarm.startRun(), false) + "," +
      sqlOrNull(alarm.startSubrun(), false) + "," +
      sqlOrNull(alarm.endRun(), false) + "," +
      sqlOrNull(alarm.endSubrun(), false) + "," +
      sqlOrNull(alarm.startTime()) + "," + sqlOrNull(alarm.endTime()) + "," +
      sqlOrNull(alarm.note()) + ") RETURNING aid;";

  rc = _sql.execute(command, result);
  if (rc) return rc;

  int aid = std::stoi(result);

  if (_verbose > 0) {
    std::cout << "new aid is " << aid << std::endl;
  }

  alarm.setAid(aid);
  return 0;
}

//***********************************************************

int mu2e::DqmTool::insertCause(DqmCause& cause, int aid) {
  // A repeated commit of the same cause is a no-op rather than an
  // error, since keepup scripts re-run.  An existing row is not
  // updated, so a cause keeps the level it was first reported with;
  // the episode's level still escalates through GREATEST above.
  std::string vclause = cause.global()
                            ? std::string(" and vid is null")
                            : " and vid=" + std::to_string(cause.vid());

  std::string command = "select cid from dqm.alarm_causes where aid=" +
                        std::to_string(aid) +
                        " and iid=" + std::to_string(cause.iid()) + vclause +
                        ";";

  std::string result;
  int rc = _sql.execute(command, result);
  if (rc) return rc;

  if (result.empty()) {
    command =
        "INSERT INTO dqm.alarm_causes (aid,iid,vid,level)  VALUES (" +
        std::to_string(aid) + "," + std::to_string(cause.iid()) + "," +
        (cause.global() ? std::string("NULL") : std::to_string(cause.vid())) +
        "," + std::to_string(cause.level()) + ") RETURNING cid;";
    rc = _sql.execute(command, result);
    if (rc) return rc;
  }

  int cid = std::stoi(result);

  if (_verbose > 1) {
    std::cout << "cid is " << cid << std::endl;
  }

  cause.setCid(cid);
  return 0;
}
