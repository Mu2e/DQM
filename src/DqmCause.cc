#include "DQM/inc/DqmCause.hh"
#include "Offline/GeneralUtilities/inc/splitString.hh"
#include <stdexcept>

//****************************************************
mu2e::DqmCause::DqmCause(const std::string& csv) :
    _cid(-1), _iid(-1), _vid(-1), _level(0) {
  StringVec sv = splitString(csv);
  if (sv.size() == 2) {
    // iid,level - a global test, about the interval and not one variable
    _iid = std::stoi(sv[0]);
    _level = std::stoi(sv[1]);
  } else if (sv.size() == 3) {
    // iid,vid,level - an empty vid field is also a global test
    _iid = std::stoi(sv[0]);
    if (!sv[1].empty()) _vid = std::stoi(sv[1]);
    _level = std::stoi(sv[2]);
  } else {
    throw std::invalid_argument(
        "DqmCause requires csv iid,vid,level or iid,level, got " + csv);
  }

  // 0,1,2,3 = message, warn, alarm, severe; the database checks this
  // too, but failing here names the offending input
  if (_level < 0 || _level > 3) {
    throw std::invalid_argument("DqmCause level must be 0-3, got " + csv);
  }
}
