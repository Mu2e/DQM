#ifndef DQM_DqmCause_hh
#define DQM_DqmCause_hh

//
// one piece of evidence for an alarm episode: the interval it was seen
// in, and the variable it concerns if it concerns a single variable.
// A cause with no vid is a global test - one about the interval as a
// whole.
//

#include <string>
#include <vector>

namespace mu2e {

class DqmCause {
 public:
  DqmCause() : _cid(-1), _iid(-1), _vid(-1), _level(0) {}
  DqmCause(int iid, int vid, int level) :
      _cid(-1), _iid(iid), _vid(vid), _level(level) {}
  // allowed strings:
  // iid,vid,level
  // iid,level        (a global test; an empty vid field means the same)
  DqmCause(const std::string& csv);

  int cid() const { return _cid; }
  int iid() const { return _iid; }
  int vid() const { return _vid; }
  int level() const { return _level; }
  // true if this is about the interval as a whole, not one variable
  bool global() const { return _vid < 0; }
  std::string csv() const {
    return std::to_string(_iid) + "," + (global() ? "" : std::to_string(_vid)) +
           "," + std::to_string(_level);
  }

  void setCid(int cid) { _cid = cid; }

 private:
  int _cid;
  int _iid;
  int _vid;
  int _level;
};

typedef std::vector<DqmCause> DqmCauseCollection;

}  // namespace mu2e

#endif
