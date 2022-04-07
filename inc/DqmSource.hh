#ifndef DQM_DqmSource_hh
#define DQM_DqmSource_hh

//
// details for a single source of Dqm metrics (generally a file)
//

#include <string>
#include <vector>

namespace mu2e {

class DqmSource {
 public:
  DqmSource() {}
  DqmSource(int sid, const std::string &process, const std::string &stream,
            const std::string &aggregation, int version) :
      _sid(sid),
      _process(process), _stream(stream), _aggregation(aggregation),
      _version(version) {}

  int sid() const { return _sid; }
  const std::string &process() const { return _process; }
  const std::string &stream() const { return _stream; }
  const std::string &aggregation() const { return _aggregation; }
  int version() const { return _version; }
  std::string csv() const {
    return _process + "," + _stream + "," + _aggregation + "," +
           std::to_string(_version);
  }

  void setSid(int sid) { _sid = sid; }

 private:
  int _sid;
  std::string _process;
  std::string _stream;
  std::string _aggregation;
  int _version;
};

typedef std::vector<DqmSource> DqmSourceCollection;

}  // namespace mu2e

#endif
