#include "DQM/inc/DqmInterval.hh"
#include "Offline/GeneralUtilities/inc/splitString.hh"
#include <algorithm>
#include <stdexcept>

//****************************************************
mu2e::DqmInterval::DqmInterval(const std::string& csv) {
  StringVec sv = splitString(csv);
  if (sv.size() != 8) {
    throw std::invalid_argument(
        "DqmInterval csv string field count is not 8: " + sv.size());
  }
  _iid = std::stoi(sv[0]);
  _sid = std::stoi(sv[1]);
  _iov = DbIoV(sv[2]+":"+sv[3]+"-"+sv[4]+":"+sv[5]);
  _startTime = sv[6];
  _endTime = sv[7];
  if (_iov.isNull() && _startTime.empty()) {
    throw std::invalid_argument("DqmInterval no actual interval " + csv);
  }
}
