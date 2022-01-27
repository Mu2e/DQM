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
    : iov_(startRun,startSubrun,endRun,endSubrun),
        startTime_(startTime), endTime_(endTime) {}

  DqmTime(const std::string& runRange,
          const std::string& startTime, const std::string& endTime )
    : iov_(runRange), startTime_(startTime), endTime_(endTime) {}

  const DbIoV& iov() const { return iov_; }
  const std::string& startTime() const { return startTime_; }
  const std::string& endTime() const { return endTime_; }
  std::string csv() const { return std::to_string(startRun_)+","
      +std::to_string(startSubrun_)+","+std::to_string(endRun_)+","
      +std::to_string(endSubrun_)+","+startTime_+","+endTime_;}

private:
  DbIoV iov_;
  std::string startTime_;
  int startRun_;
  int startSubrun_;
  std::string endTime_;
  int endRun_;
  int endSubrun_;
};

typedef std::vector<DqmTime> DqmTimeCollection;

} // namespace mu2e

#endif
