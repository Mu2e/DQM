#ifndef DQM_DqmTool_hh
#define DQM_DqmTool_hh

//
// A class to take DQM values as text and insert them in the database.
// This class is wrapped by a main function and can be called as bin called
// dqmTool which is the primary expected use pattern.
//

#include "DQM/inc/DqmSource.hh"
#include "DQM/inc/DqmValue.hh"
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

  // run a database command (see actions)
  int run(const std::string& arg);
  int run(const StringVec&  args);
  // the result of the command, in a string with embedded '\n'
  std::string getResult() { return _result; }

private:
  typedef std::map<std::string, std::string> ArgMap;

  void usage(bool inAction=false);
  int init();

  int commitValue();

  int printSources();
  int printIntervals();
  int printValues();
  int printNumbers();

  // give the process, stream etc in a source, lookup sid in db
  int lookupSid(DqmSource& source);
  // give the grou, subgroup etc in a value, lookup vid in db
  int lookupVid(DqmValue& value);
  // given a string, a file name or csv, parse it into a DqmSource
  int parseSource(DqmSource& source, std::string& runs, const std::string& ss);
  // given a string, csv, parse it into a DqmValue
  int parseValue(DqmValue& value, const std::string& vv);
  // tokenize a string, if del=='X' try several
  StringVec splitString(const std::string& command, char del='X');
  // parse the general arguments, like "verbose"
  int parseGeneral();
  // parse the action argument (like "print-values")
  int parseAction();

  StringVec _args; // all the args
  std::string _action;  // action, parsed from arg
  StringVec _actionArgs; // args to the action
  ArgMap _argMap;  // map of ["option"] = value 
  int _verbose;
  int _dryrun;
  std::string _result;

  DbReader _reader;
  DbSql _sql;
};

} // namespace mu2e

#endif
