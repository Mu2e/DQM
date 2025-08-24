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
  DqmSource():_sid(-1) {}
  // possible constructions:
  // process, stream, aggregation, version
  // sid, process, stream, aggregation, version
  // ntd.dqm_PROCESS.STREAM_AGGREGATION_VERSION.RUN_SUBRUN.root
  DqmSource(const std::string& str);
  DqmSource(const std::string& process, const std::string& stream,
            const std::string& aggregation, const std::string& version,
            int sid = -1);

  int sid() const { return _sid; }
  const std::string& process() const { return _process; }
  const std::string& stream() const { return _stream; }
  const std::string& aggregation() const { return _aggregation; }
  const std::string& version() const { return _version; }

  // like RUN:SUBRUN, only if initialized from a file name
  const std::string& run() const { return _run; }
  std::string csv() const {
    return _process + "," + _stream + "," + _aggregation + "," + _version;
  }

  void setSid(int sid) { _sid = sid; }

 private:
  int _sid;
  std::string _process;
  std::string _stream;
  std::string _aggregation;
  std::string _version;
  std::string _run;
};

typedef std::vector<DqmSource> DqmSourceCollection;

}  // namespace mu2e

#endif
