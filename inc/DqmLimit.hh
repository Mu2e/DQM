#ifndef DQM_DqmLimit_hh
#define DQM_DqmLimit_hh

//
// holds a single Dqm limit, its name and uncertainty
//

#include "DQM/inc/DqmValue.hh"
#include <string>
#include <vector>

namespace mu2e {

class DqmLimit {
 public:
  enum alarmValues { ignore = 0, warnOnly = 1, standard = 2, critical = 3 };

  // allowed strings:
  // value,sigma,code
  // lid,sid,iid,vid,value,signma,code
  DqmLimit(const std::string& csv);
  DqmLimit(const std::string& llimit, const std::string& ulimit, const std::string& sigma, const std::string& alarmcode,
            int sid = -1, int iid = -1, int vid = -1, int lid = -1 ) :
      _lid(lid),_sid(sid),_iid(iid),_vid(vid),
      _llimitStr(llimit), _llimit(std::stof(llimit)),
      _ulimitStr(ulimit), _ulimit(std::stof(ulimit)),
      _sigmaStr(sigma),_sigma(std::stof(sigma)),
      _alarmcodeStr(alarmcode), _alarmcode(std::stoi(alarmcode)) {}

  int lid() const { return _lid; }
  int sid() const { return _sid; }
  int iid() const { return _iid; }
  int vid() const { return _vid; }
  const std::string& llimitStr() const { return _llimitStr; }
  float llimit() const { return _llimit; }
  const std::string& ulimitStr() const { return _ulimitStr; }
  float ulimit() const { return _ulimit; }
  const std::string& sigmaStr() const { return _sigmaStr; }
  float sigma() const { return _sigma; }
  const std::string& alarmcodeStr() const { return _alarmcodeStr; }
  int alarmcode() const { return _alarmcode; }
  std::string csv() const {
    return _llimitStr + "," + _ulimitStr + "," + _sigmaStr + "," + _alarmcodeStr;
  }
  const DqmValue& dqmValue() const { return _dqmvalue;}

  void setLid(int lid) { _lid = lid; }
  void setSid(int sid) { _sid = sid; }
  void setIid(int iid) { _iid = iid; }
  void setVid(int vid) { _vid = vid; }
  void setDqmValue(const DqmValue& value) { _dqmvalue=value; }

 private:
  int _lid;
  int _sid;
  int _iid;
  int _vid;
  std::string _llimitStr;
  float _llimit;
  std::string _ulimitStr;
  float _ulimit;
  std::string _sigmaStr;
  float _sigma;
  std::string _alarmcodeStr;
  int _alarmcode;
  DqmValue _dqmvalue;
};

typedef std::vector<DqmLimit> DqmLimitCollection;

}  // namespace mu2e

#endif
