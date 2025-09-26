#include "DQM/inc/DqmTool.hh"
#include "Offline/DbService/inc/DbIdList.hh"
#include "Offline/GeneralUtilities/inc/splitString.hh"
#include <boost/algorithm/string.hpp>
#include <boost/algorithm/string/classification.hpp>
#include <boost/algorithm/string/split.hpp>
#include <boost/tokenizer.hpp>
#include <fstream>
#include <iostream>
#include <map>
#include <string>


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
                               const std::string& valuestr) {
  int rc;

  // **** interpret source (process/stream/aggregation/version)

  std::string ss = sources;
  if (ss.empty()) {
    std::cout << "ERROR - commit-value requires --source" << std::endl;
    return 1;
  }

  // take the ss string and parse it into proces/stream, etc, fields,
  // whether it is a file name with a standard form, or csv string
  // runs will be filled if the aources was a file with a runs type sequencer
  DqmSource source(ss);
  std::string runs = source.run();

  // **** interpret time interval

  std::string rn = runss;
  std::string st = start;
  std::string en = end;

  // if we got a start run from the file name, and the
  // explicit run range parameter does not overwrite it, then use it
  if (rn.empty() && !runs.empty()) rn = runs;

  // must have some time or run restriction
  if (rn.empty() && st.empty()) {
    std::cout << "ERROR - commit-source requires one of --runs, --start, or a "
                 "file name with a run_subrun sequencer"
              << std::endl;
    return 1;
  }
  if (st.empty() && !en.empty()) {
    std::cout << "ERROR - commit-source --end is non-empty but --start is "
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
    std::cout << "Running commit-source with parameters:" << std::endl;
    std::cout << "source :" << ss << std::endl;
    std::cout << "runs   :" << rn << std::endl;
    std::cout << "start  :" << st << std::endl;
    std::cout << "end    :" << en << std::endl;
    std::cout << "value : " << vv << std::endl;
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

  // take the ss string and parse it into proces/stream, etc, fields,
  // whether it is a file name with a standard form, or csv string
  // runs will be filled if the sources was a file with a runs type sequencer
  DqmSource source(ss);
  std::string runs = source.run();

  // **** interpret time interval

  std::string rn = runss;
  std::string st = start;
  std::string en = end;

  // if we got a start run from the file name, and the
  // explicit run range parameter does not overwrite it, then use it
  if (rn.empty() && !runs.empty()) rn = runs;

  // must have some time or run restriction
  if (rn.empty() && st.empty()) {
    std::cout << "ERROR - commit-limit requires one of --runs, --start, or a "
                 "file name with a run_subrun sequencer"
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
    std::cout << "Running commit-source with parameters:" << std::endl;
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

int mu2e::DqmTool::printNumbers(const std::string& name, bool heading, const std::string& sources,
                                const std::string& values, const bool& expand) {
  int rc = 0;

  int sid = -1;
  if (!sources.empty()) {
    std::string ss = sources;
    if (ss.find_first_not_of("0123456789") == std::string::npos) {
      sid = std::stoi(ss);  // was an integer
    } else {                // is file name or csv
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
        _result = "nid, sid, iid, vid, value, sigma, code\n" + result;
      } else {
        _result = "nid, sid, iid, vid, llimit, ulimit, sigma, alarmcode\n" + result;
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
    if (heading) {
      if(name=="numbers") {
        _result = "nid, value, sigma, code, sid, proc, stream, agg, ver, vid, group, hist, metric, iid, sid, start_run, start_sub, stop_run, stop_sub, start_time, stop_time\n"+_result;
      } else {
        _result = "nid, lower_lim, upper_lim, sigma, alarmcode, sid, proc, stream, agg, ver, vid, group, hist, metric, iid, sid, start_run, start_sub, stop_run, stop_sub, start_time, stop_time\n"+_result;
      }
    }

  return 0;
}

//***********************************************************
int mu2e::DqmTool::readTable(const std::string& table, std::string& result) {
  std::string select("*");
  StringVec where;
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
