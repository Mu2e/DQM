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
            const std::string &aggregation, int version)
      : sid_(sid), process_(process), stream_(stream),
        aggregation_(aggregation), version_(version) {}

  int sid() const { return sid_; }
  const std::string &process() const { return process_; }
  const std::string &stream() const { return stream_; }
  const std::string &aggregation() const { return aggregation_; }
  int version() const { return version_; }

  void setSid(int sid) { sid_ = sid; }

private:
  int sid_;
  std::string process_;
  std::string stream_;
  std::string aggregation_;
  int version_;

};

typedef std::vector<DqmSource> DqmSourceCollection;

} // namespace mu2e

#endif
