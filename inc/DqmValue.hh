#ifndef DQM_DqmValue_hh
#define DQM_DqmValue_hh

//
// holds a single Dqm value label
//

#include <string>
#include <vector>

namespace mu2e {

class DqmValue {
 public:
  DqmValue():_vid(-1) {}
  // allowed strings:
  // vid,group,subgroup,name
  // group,subgroup,name
  DqmValue(const std::string& csv);
  DqmValue(const std::string& group, const std::string& subgroup,
           const std::string& name, int vid = -1) :
    _vid(vid), _group(group),
      _subgroup(subgroup), _name(name) {}

  int vid() const { return _vid; }
  const std::string& group() const { return _group; }
  const std::string& subgroup() const { return _subgroup; }
  const std::string& name() const { return _name; }
  std::string csv() const { return _group + "," + _subgroup + "," + _name; }

  void setVid(int vid) { _vid = vid; }

 private:
  int _vid;
  std::string _group;
  std::string _subgroup;
  std::string _name;
};

typedef std::vector<DqmValue> DqmValueCollection;

}  // namespace mu2e

#endif
