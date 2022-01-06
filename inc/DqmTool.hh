#ifndef Dqm_DqmTool_hh
#define Dqm_DqmTool_hh

//
// A class to take DQM values as text and insert them in the database.
// This class is wrapped by a main function and can be called as bin called
// dqmTool which is the primary expected use pattern.
//

#include "dqm/inc/DqmSource.hh"
#include "dqm/inc/DqmValue.hh"
#include "Offline/DbTables/inc/DbIoV.hh"
#include "Offline/DbService/inc/DbReader.hh"
#include "Offline/DbService/inc/DbSql.hh"
#include <map>
#include <string>
#include <vector>

namespace mu2e {

class DqmTool {
public:
  typedef std::vector<std::string> StringVec;

  DqmTool();

  int run(const std::string& arg);
  int run(const StringVec&  args);
  std::string getResult() { return result_; }

private:
  typedef std::map<std::string, std::string> ArgMap;

  void usage(bool inAction=false);
  int init();

  int commitValue();

  int printSources();
  int printIntervals();
  int printValues();
  int printNumbers();

  int lookupSid(DqmSource& source);
  int parseSource(DqmSource& source, std::string& runs, const std::string& ss);
  int parseValue(DqmValue& value, const std::string& vv);
  StringVec splitString(const std::string& command, char del='X');
  int parseGeneral();
  int parseAction();

  StringVec args_;
  std::string action_;
  StringVec actionArgs_;
  ArgMap argMap_;
  int verbose_;
  int dryrun_;
  std::string result_;

  DbReader reader_;
  DbSql sql_;
};

} // namespace mu2e

#endif
