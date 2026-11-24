#ifndef DQM_DqmGolden_hh
#define DQM_DqmGolden_hh

//
// holds the name of a golden, or reference, file for a source: the file
// its metrics should be compared against over one range of runs or time
//
// Like a limit, the interval this carries is one of validity rather than
// of measurement, and it is keyed by source and range only - one
// reference file covers every metric the source reports, so unlike a
// limit there is no vid.  The note is for how a hand-made reference,
// an average say, was arrived at.
//

#include <string>
#include <vector>

namespace mu2e {

class DqmGolden {
 public:
  DqmGolden() : _gid(-1), _sid(-1), _iid(-1) {}
  DqmGolden(const std::string& name, const std::string& note = "",
            int sid = -1, int iid = -1, int gid = -1) :
      _gid(gid), _sid(sid), _iid(iid), _name(name), _note(note) {}

  int gid() const { return _gid; }
  int sid() const { return _sid; }
  int iid() const { return _iid; }
  const std::string& name() const { return _name; }
  const std::string& note() const { return _note; }
  std::string csv() const {
    return std::to_string(_sid) + "," + std::to_string(_iid) + "," + _name;
  }

  void setGid(int gid) { _gid = gid; }
  void setSid(int sid) { _sid = sid; }
  void setIid(int iid) { _iid = iid; }

 private:
  int _gid;
  int _sid;
  int _iid;
  std::string _name;
  std::string _note;
};

typedef std::vector<DqmGolden> DqmGoldenCollection;

}  // namespace mu2e

#endif
