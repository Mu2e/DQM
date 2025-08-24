#include "DQM/inc/DqmLimit.hh"
#include "Offline/GeneralUtilities/inc/splitString.hh"
#include <algorithm>
#include <stdexcept>

//****************************************************
mu2e::DqmLimit::DqmLimit(const std::string& csv) {
  StringVec sv = splitString(csv);
  if (sv.size() == 4) {
    _lid = -1;
    _llimitStr = sv[0];
    _llimit = std::stof(sv[0]);
    _ulimitStr = sv[1];
    _ulimit = std::stof(sv[1]);
    _sigmaStr = sv[2];
    _sigma = std::stof(sv[2]);
    _alarmcodeStr = sv[3];
    _alarmcode = std::stoi(sv[3]);
  } else if (sv.size() == 8) {
    _lid = std::stoi(sv[0]);
    _sid = std::stoi(sv[1]);
    _iid = std::stoi(sv[2]);
    _vid = std::stoi(sv[3]);
    _llimitStr = sv[4];
    _llimit = std::stof(sv[4]);
    _ulimitStr = sv[5];
    _ulimit = std::stof(sv[5]);
    _sigmaStr = sv[6];
    _sigma = std::stof(sv[6]);
    _alarmcodeStr = sv[7];
    _alarmcode = std::stoi(sv[7]);
  }
  if (_llimitStr.empty()) {
    throw std::invalid_argument("DqmLimit no value " + csv);
  }
}
