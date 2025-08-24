#include "DQM/inc/DqmNumber.hh"
#include "Offline/GeneralUtilities/inc/splitString.hh"
#include <algorithm>
#include <stdexcept>

//****************************************************
mu2e::DqmNumber::DqmNumber(const std::string& csv) {
  StringVec sv = splitString(csv);
  if (sv.size() == 3) {
    _nid = -1;
    _valueStr = sv[0];
    _value = std::stof(sv[0]);
    _sigmaStr = sv[1];
    _sigma = std::stof(sv[1]);
    _codeStr = sv[2];
    _code = std::stoi(sv[2]);
  } else if (sv.size() == 7) {
    _nid = std::stoi(sv[0]);
    _sid = std::stoi(sv[1]);
    _iid = std::stoi(sv[2]);
    _vid = std::stoi(sv[3]);
    _valueStr = sv[4];
    _value = std::stof(sv[4]);
    _sigmaStr = sv[5];
    _sigma = std::stof(sv[5]);
    _codeStr = sv[6];
    _code = std::stoi(sv[6]);
  }
  if (_valueStr.empty()) {
    throw std::invalid_argument("DqmNumber no value " + csv);
  }
}
