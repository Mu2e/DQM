#ifndef DQM_DqmAlarm_hh
#define DQM_DqmAlarm_hh

//
// one alarm episode.  Identity is (algo, config, subject, sid) - that
// is what makes two reports the same alarm.  The run and time spans
// are a hull of what fired and do not claim that every run inside them
// alarmed; DqmCause is the ground truth.
//

#include <algorithm>
#include <string>
#include <vector>

namespace mu2e {

class DqmAlarm {
 public:
  // An episode stays extendable for this long after its last
  // extension, measured from mtime.  Wall clock rather than run
  // adjacency, because an evaluator sees runs out of order and cannot
  // know whether a run it has not seen will ever arrive.  A finding
  // arriving later opens a new episode instead.  One value for all
  // evaluators for now; it belongs per (algo, config) eventually.
  static constexpr int graceHours = 24;

  // The operator workflow vocabulary.  Kept here rather than as a sql
  // CHECK constraint so it can grow without a migration, but enforced
  // in code: terminalStatus below is an exact match, so a misspelling
  // would otherwise store and silently leave an episode open.
  static const std::vector<std::string>& statusValues() {
    static const std::vector<std::string> values{
        "active", "acknowledged", "silenced", "retired", "deleted"};
    return values;
  }
  static bool validStatus(const std::string& status) {
    auto const& vv = statusValues();
    return std::find(vv.begin(), vv.end(), status) != vv.end();
  }
  // retired and deleted are terminal: setting either also closes the
  // episode, so a later matching finding starts a fresh one rather
  // than resurrecting this one
  static bool terminalStatus(const std::string& status) {
    return status == "retired" || status == "deleted";
  }
  // the vocabulary as a readable list, for help text and messages
  static std::string statusList() {
    std::string out;
    for (auto const& vv : statusValues()) {
      if (!out.empty()) out += ", ";
      out += vv;
    }
    return out;
  }

  DqmAlarm() : _aid(-1), _sid(-1), _level(0) {}
  DqmAlarm(const std::string& algo, const std::string& config,
           const std::string& subject, int sid, int aid = -1) :
      _aid(aid),
      _sid(sid), _level(0), _algo(algo), _config(config), _subject(subject) {}

  int aid() const { return _aid; }
  int sid() const { return _sid; }
  int level() const { return _level; }
  const std::string& algo() const { return _algo; }
  const std::string& config() const { return _config; }
  const std::string& subject() const { return _subject; }
  const std::string& note() const { return _note; }

  // The span fields are held as strings because each one is either a
  // value or a database NULL, and an empty string says NULL
  // unambiguously - an int could not, since 0 is a legal run number and
  // the epoch is a legal time.  They pass straight back into sql.
  const std::string& startRun() const { return _startRun; }
  const std::string& startSubrun() const { return _startSubrun; }
  const std::string& endRun() const { return _endRun; }
  const std::string& endSubrun() const { return _endSubrun; }
  const std::string& startTime() const { return _startTime; }
  const std::string& endTime() const { return _endTime; }

  bool hasRuns() const { return !_startRun.empty(); }
  bool hasTimes() const { return !_startTime.empty(); }
  // the database requires one or the other, or both, but never neither
  bool hasRange() const { return hasRuns() || hasTimes(); }

  std::string csv() const {
    return _algo + "," + _config + "," + _subject + "," + std::to_string(_sid);
  }

  void setAid(int aid) { _aid = aid; }
  void setLevel(int level) { _level = level; }
  void setNote(const std::string& note) { _note = note; }
  void setRuns(const std::string& startRun, const std::string& startSubrun,
               const std::string& endRun, const std::string& endSubrun) {
    _startRun = startRun;
    _startSubrun = startSubrun;
    _endRun = endRun;
    _endSubrun = endSubrun;
  }
  void setTimes(const std::string& startTime, const std::string& endTime) {
    _startTime = startTime;
    _endTime = endTime;
  }

 private:
  int _aid;
  int _sid;
  int _level;
  std::string _algo;
  std::string _config;
  std::string _subject;
  std::string _startRun;
  std::string _startSubrun;
  std::string _endRun;
  std::string _endSubrun;
  std::string _startTime;
  std::string _endTime;
  std::string _note;
};

typedef std::vector<DqmAlarm> DqmAlarmCollection;

}  // namespace mu2e

#endif
