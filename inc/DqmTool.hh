#ifndef DQM_DqmTool_hh
#define DQM_DqmTool_hh

//
// A class to take DQM values as text and insert them in the database.
// This class is wrapped by a main function and can be called as bin called
// dqmTool which is the primary expected use pattern.
//

#include "DQM/inc/DqmAlarm.hh"
#include "DQM/inc/DqmCause.hh"
#include "DQM/inc/DqmFile.hh"
#include "DQM/inc/DqmInterval.hh"
#include "DQM/inc/DqmLimit.hh"
#include "DQM/inc/DqmNumber.hh"
#include "DQM/inc/DqmSource.hh"
#include "DQM/inc/DqmValue.hh"
#include "Offline/DbService/inc/DbReader.hh"
#include "Offline/DbService/inc/DbSql.hh"
#include "Offline/DbTables/inc/DbIoV.hh"
#include "Offline/GeneralUtilities/inc/StringVec.hh"
#include <map>
#include <string>
#include <vector>

namespace mu2e {

class DqmTool {
 public:
  DqmTool() : _verbose(0) {}

  // initialize the database connections before any other calls
  int init();
  int printSources(bool heading = false);
  int printIntervals(bool heading = false);
  int printValues(bool heading = false);
  int printFiles(bool heading = false);
  int printAlarms(bool heading = false, bool note = false, bool live = false);
  int printCauses(bool heading = false, bool numbers = false,
                  const std::string& aid = "");
  int printNumbers(const std::string& name = "numbers", bool heading = false,
                   const std::string& source = "",
                   const std::string& value = "", const bool& expand = false);
  int commitValue(const std::string& source = "", const std::string& runs = "",
                  const std::string& start = "", const std::string& end = "",
                  const std::string& value = "", const std::string& file = "");
  int commitLimit(const std::string& source = "", const std::string& runs = "",
                  const std::string& start = "", const std::string& end = "",
                  const std::string& limit = "");
  // take a finding from one evaluator instance and either extend the
  // episode it continues or open a new one; see checker_spec.txt
  int commitAlarm(const std::string& algo = "", const std::string& config = "",
                  const std::string& subject = "", const std::string& sid = "",
                  const std::string& causes = "",
                  const std::string& note = "");
  int alarmStatus(const std::string& aid = "", const std::string& status = "");
  void setVerbose(int verbose) { _verbose = verbose; }

  // retrieve text output from a print command call
  const std::string& getResult() const { return _result; }

 private:
  // read a table into a string.  select defaults to all columns; pass
  // a column list where that is not wanted, as print-alarms does to
  // keep the json note out of the csv.  where clauses are "col:op:val"
  // and are ANDed together.  Note the query engine accepts only
  // certain ops - eq and ne are known to work, and an unsupported one
  // returns no rows rather than an error, so do not guess.
  int readTable(const std::string& table, std::string& result,
                const std::string& select = "*",
                const StringVec& where = StringVec());
  // fill in an alarm's level and hull span from the intervals of its
  // causes, validating that those intervals exist and belong to its sid
  int spanFromCauses(DqmAlarm& alarm, const DqmCauseCollection& causes);
  // find the episode this finding continues, if any; sets aid when found
  int matchAlarm(DqmAlarm& alarm);
  int extendAlarm(const DqmAlarm& alarm);
  int insertAlarm(DqmAlarm& alarm);
  int insertCause(DqmCause& cause, int aid);
  // give the process, stream etc in a source, lookup sid in db
  int lookupSid(DqmSource& source);
  // give the parameters in an interval, lookup iid in db
  int lookupIid(DqmInterval& interval);
  // give the group, subgroup etc in a value, lookup vid in db
  int lookupVid(DqmValue& value);
  // lookup or create in database based on object parameters
  int locateSource(DqmSource& source);
  int locateInterval(DqmInterval& interval);
  int locateValue(DqmValue& value);
  int locateFile(DqmFile& file);
  int insertNumber(DqmNumber& number);
  int insertLimit(DqmLimit& limit);

  int _verbose;
  int _dryrun;
  std::string _result;

  DbReader _reader;
  DbSql _sql;
};

}  // namespace mu2e

#endif
