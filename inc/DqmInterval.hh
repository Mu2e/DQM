#ifndef DQM_DqmInterval_hh
#define DQM_DqmInterval_hh

//
// the interval of time and range of run/subrun for data going into a source
//

#include "Offline/DbTables/inc/DbIoV.hh"
#include <string>

namespace mu2e {

class DqmInterval {
 public:
  // iid,sid,start_run,start_subrun,end_run,end_subrun,start_time,end_time
  DqmInterval(const std::string& csv);
  // "1100:0-1101:999999", "2022-01-01T14:00:00", ..
  DqmInterval(const std::string& runRange, const std::string& startTime,
              const std::string& endTime, int sid = -1, int iid = -1) :
      _iid(iid),
      _sid(sid), _iov(runRange), _startTime(startTime), _endTime(endTime) {}

  DqmInterval(int startRun, int startSubrun, int endRun, int endSubrun,
              const std::string& startTime, const std::string& endTime,
              int sid = -1, int iid = -1) :
      _iid(iid),
      _sid(sid), _iov(startRun, startSubrun, endRun, endSubrun),
      _startTime(startTime), _endTime(endTime) {}

  int iid() const { return _iid; }
  int sid() const { return _sid; }
  const DbIoV& iov() const { return _iov; }
  const std::string& startTime() const { return _startTime; }
  const std::string& endTime() const { return _endTime; }
  std::string csv() const {
    return std::to_string(_iov.startRun()) + "," +
           std::to_string(_iov.startSubrun()) + "," +
           std::to_string(_iov.endRun()) + "," +
           std::to_string(_iov.endSubrun()) + "," + _startTime + "," + _endTime;
  }

  void setIid(int iid) { _iid = iid; }
  void setSid(int sid) { _sid = sid; }

 private:
  int _iid;
  int _sid;
  DbIoV _iov;
  std::string _startTime;
  std::string _endTime;
};

typedef std::vector<DqmInterval> DqmIntervalCollection;

}  // namespace mu2e

#endif
