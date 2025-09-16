#ifndef DQM_DqmNumber_hh
#define DQM_DqmNumber_hh

//
// holds a single Dqm number, its name and uncertainty
//

#include "DQM/inc/DqmValue.hh"
#include <string>
#include <vector>

namespace mu2e {

class DqmNumber {
 public:
  enum codeValues { OK = 0, lowStats = 1, missing = 2, error = 3 };

  // allowed strings:
  // value,sigma,code
  // nid,sid,iid,vid,value,signma,code
  DqmNumber(const std::string& csv);
  DqmNumber(const std::string& value, const std::string& sigma, const std::string& code,
            int sid = -1, int iid = -1, int vid = -1, int nid = -1 ) :
      _nid(nid),_sid(sid),_iid(iid),_vid(vid),
      _valueStr(value), _value(std::stof(value)), _sigmaStr(sigma),
      _sigma(std::stof(sigma)), _codeStr(code), _code(std::stoi(code)) {}

  int nid() const { return _nid; }
  int sid() const { return _sid; }
  int iid() const { return _iid; }
  int vid() const { return _vid; }
  const std::string& valueStr() const { return _valueStr; }
  float value() const { return _value; }
  const std::string& sigmaStr() const { return _sigmaStr; }
  float sigma() const { return _sigma; }
  const std::string& codeStr() const { return _codeStr; }
  int code() const { return _code; }
  std::string csv() const {
    return _valueStr + "," + _sigmaStr + "," + _codeStr;
  }
  const DqmValue& dqmValue() const { return _dqmvalue;}

  void setNid(int nid) { _nid = nid; }
  void setSid(int sid) { _sid = sid; }
  void setIid(int iid) { _iid = iid; }
  void setVid(int vid) { _vid = vid; }
  void setDqmValue(const DqmValue& value) { _dqmvalue=value; }

 private:
  int _nid;
  int _sid;
  int _iid;
  int _vid;
  std::string _valueStr;
  float _value;
  std::string _sigmaStr;
  float _sigma;
  std::string _codeStr;
  int _code;
  DqmValue _dqmvalue;
};

typedef std::vector<DqmNumber> DqmNumberCollection;

}  // namespace mu2e

#endif
