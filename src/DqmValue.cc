#include "DQM/inc/DqmValue.hh"
#include "Offline/GeneralUtilities/inc/splitString.hh"
#include <algorithm>
#include <stdexcept>

//****************************************************
mu2e::DqmValue::DqmValue(const std::string& csv) {
  StringVec sv = splitString(csv);
  if (sv.size() == 3) {
    _vid = -1;
    _group = sv[0];
    _subgroup = sv[1];
    _name = sv[2];
  } else if (sv.size() == 4) {
    _vid = std::stoi(sv[0]);
    _group = sv[1];
    _subgroup = sv[2];
    _name = sv[3];
  } else {
    throw std::invalid_argument(
        "DqmValue csv string field count is not 3 or 4: " + sv.size());
  }
  if (_group.empty() || _subgroup.empty() || _name.empty()) {
    throw std::invalid_argument("DqmValue missing csv fields " + csv);
  }
}
