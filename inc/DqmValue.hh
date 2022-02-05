#ifndef DQM_DqmValue_hh
#define DQM_DqmValue_hh

//
// holds a single Dqm value, its name and uncertainty
//

#include <string>
#include <vector>

namespace mu2e {

  class DqmValue {
  public:

    enum codeValues { OK=0, lowStats=1, missing=2, error=3 };

    DqmValue() {}
    DqmValue(const std::string& group, 
             const std::string& subgroup,
             const std::string& name,
             const std::string& value, 
             const std::string& sigma, 
             int code=0):
             _group(group),_subgroup(subgroup),_name(name),
             _valueStr(value),_value(std::stof(value)),
             _sigmaStr(sigma),_sigma(std::stof(value)),_code(code) {}

    const std::string& group() const { return _group; }
    const std::string& subgroup() const { return _subgroup; }
    const std::string& name() const { return _name; }
    const std::string& valueStr() const { return _valueStr; }
    float value() const { return _value; }
    const std::string& sigmaStr() const { return _sigmaStr; }
    float sigma() const { return _sigma; }
    int   code() const { return _code; }
    std::string csv() const { return _group+","+_subgroup+","+_name+","
        +_valueStr+","+_sigmaStr+","+std::to_string(_code);}
    
  private:
    std::string _group;
    std::string _subgroup;
    std::string _name;
    std::string _valueStr;
    float _value;
    std::string _sigmaStr;
    float _sigma;
    int   _code;
  };
  
  typedef std::vector<DqmValue> DqmValueCollection;
  
}

#endif
