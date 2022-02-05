#ifndef DQM_DqmTime_hh
#define DQM_DqmTime_hh

//
// the interval of time and range of run/subrun for data going into a source
//

#include "Offline/DbTables/inc/DbIoV.hh"
#include <string>

namespace mu2e {

class DqmTime {
public:
  DqmTime(int startRun, int startSubrun, int endRun, int endSubrun,
          const std::string& startTime, const std::string& endTime )
    : _iov(startRun,startSubrun,endRun,endSubrun),
        _startTime(startTime), _endTime(endTime) {}

  DqmTime(const std::string& runRange,
          const std::string& startTime, const std::string& endTime )
    : _iov(runRange), _startTime(startTime), _endTime(endTime) {}

  const DbIoV& iov() const { return _iov; }
  const std::string& startTime() const { return _startTime; }
  const std::string& endTime() const { return _endTime; }
  std::string csv() const { return std::to_string(_startRun)+","
      +std::to_string(_startSubrun)+","+std::to_string(_endRun)+","
      +std::to_string(_endSubrun)+","+_startTime+","+_endTime;}

private:
  DbIoV _iov;
  std::string _startTime;
  int _startRun;
  int _startSubrun;
  std::string _endTime;
  int _endRun;
  int _endSubrun;
};

typedef std::vector<DqmTime> DqmTimeCollection;

} // namespace mu2e

#endif
