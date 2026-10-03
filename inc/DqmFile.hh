#ifndef DQM_DqmFile_hh
#define DQM_DqmFile_hh

//
// holds the name of a file that the metrics of a source and interval
// were derived from, so an anomalous metric can be traced back to it
//

#include <string>
#include <vector>

namespace mu2e {

class DqmFile {
 public:
  DqmFile() : _fid(-1), _sid(-1), _iid(-1) {}
  DqmFile(const std::string& name, int sid = -1, int iid = -1, int fid = -1) :
      _fid(fid), _sid(sid), _iid(iid), _name(name) {}

  int fid() const { return _fid; }
  int sid() const { return _sid; }
  int iid() const { return _iid; }
  const std::string& name() const { return _name; }
  std::string csv() const {
    return std::to_string(_sid) + "," + std::to_string(_iid) + "," + _name;
  }

  void setFid(int fid) { _fid = fid; }
  void setSid(int sid) { _sid = sid; }
  void setIid(int iid) { _iid = iid; }

 private:
  int _fid;
  int _sid;
  int _iid;
  std::string _name;
};

typedef std::vector<DqmFile> DqmFileCollection;

}  // namespace mu2e

#endif
