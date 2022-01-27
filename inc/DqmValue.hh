#ifndef DQM_DqmValue_hh
#define DQM_DqmValue_hh

//
// holds a single Dqm value, its name and uncertainty
//

#include <string>

namespace mu2e {

  class DqmValue {
  public:

    enum codeValues { OK=0, lowStats=1, missing=2 };

    DqmValue() {}
    DqmValue(const std::string& group, 
             const std::string& subgroup,
             const std::string& name,
             const std::string& value, 
             const std::string& sigma, 
             int code=0):
             group_(group),subgroup_(subgroup),name_(name),
             valueStr_(value),value_(std::stof(value)),
             sigmaStr_(sigma),sigma_(std::stof(value)),code_(code) {}

    const std::string& group() const { return group_; }
    const std::string& subgroup() const { return subgroup_; }
    const std::string& name() const { return name_; }
    const std::string& valueStr() const { return valueStr_; }
    float value() const { return value_; }
    const std::string& sigmaStr() const { return sigmaStr_; }
    float sigma() const { return sigma_; }
    int   code() const { return code_; }
    std::string csv() const { return group_+","+subgroup_+","+name_+","
        +valueStr_+","+sigmaStr_+","+std::to_string(code_);}
    
  private:
    std::string group_;
    std::string subgroup_;
    std::string name_;
    std::string valueStr_;
    float value_;
    std::string sigmaStr_;
    float sigma_;
    int   code_;
  };
  
  typedef std::vector<DqmValue> DqmValueCollection;
  
}

#endif
