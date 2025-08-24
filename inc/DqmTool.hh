#ifndef DQM_DqmTool_hh
#define DQM_DqmTool_hh

//
// A class to take DQM values as text and insert them in the database.
// This class is wrapped by a main function and can be called as bin called
// dqmTool which is the primary expected use pattern.
//

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
  int printNumbers(const std::string& name = "numbers", bool heading = false,
                   const std::string& source = "",
                   const std::string& value = "", const bool& expand = false);
  int commitValue(const std::string& source = "", const std::string& runs = "",
                  const std::string& start = "", const std::string& end = "",
                  const std::string& value = "");
  int commitLimit(const std::string& source = "", const std::string& runs = "",
                  const std::string& start = "", const std::string& end = "",
                  const std::string& limit = "");
  void setVerbose(int verbose) { _verbose = verbose; }

  // retrieve text output from a print command call
  const std::string& getResult() const { return _result; }

 private:
  // read a full table in a string
  int readTable(const std::string& table, std::string& result);
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
