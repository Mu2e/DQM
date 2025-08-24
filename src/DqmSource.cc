#include "DQM/inc/DqmSource.hh"
#include "Offline/GeneralUtilities/inc/splitString.hh"
#include <algorithm>
#include <stdexcept>

//****************************************************
mu2e::DqmSource::DqmSource(const std::string& str) {
  StringVec sv = splitString(str);
  if (sv.size() == 4) {
    // process, stream, aggregation, version
    _sid = -1;
    _process = sv[0];
    _stream = sv[1];
    _aggregation = sv[2];
    _version = sv[3];
  } else if (sv.size() == 5) {
    // sid, process, stream, aggregation, version
    _sid = std::stoi(sv[0]);
    _process = sv[1];
    _stream = sv[2];
    _aggregation = sv[3];
    _version = sv[4];
  } else {
    _sid = -1;
    sv = splitString(str, ".");
    if (sv.size() == 6) {
      StringVec sv2;
      sv2 = splitString(sv[2], "_");
      if (sv2.size() < 2)
        throw std::invalid_argument(
            "DqMSource could not parse file description " + sv[2]);
      _process = sv2[1];
      sv2 = splitString(sv[3], "_");
      if (sv2.size() < 3)
        throw std::invalid_argument(
            "DqMSource could not parse file configuration " + sv[3]);
      _stream = sv2[0];
      _aggregation = sv2[1];
      _version = sv2[2];
      sv2 = splitString(sv[4], "_");
      if (sv2.size() < 2)
        throw std::invalid_argument(
            "DqMSource could not parse file sequencer " + sv[4]);
      _run = sv2[0] + ":" + sv2[1];
    } else {
      throw std::invalid_argument(
          "DqMSource string does not match any pattern " + str);
    }
  }

  if (_process.empty() || _stream.empty() || _aggregation.empty() ||
      _version.empty()) {
    throw std::invalid_argument("DqmSource failed to construct from " + str);
  }
}

//****************************************************
mu2e::DqmSource::DqmSource(const std::string& process,
                           const std::string& stream,
                           const std::string& aggregation,
                           const std::string& version, int sid) :
    _sid(sid),
    _process(process), _stream(stream), _aggregation(aggregation),
    _version(version) {
  if (_process.empty() || _stream.empty() || _aggregation.empty() ||
      _version.empty()) {
    throw std::invalid_argument("DqmSource failed to construct from strings");
  }
}
