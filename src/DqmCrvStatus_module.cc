//
// Offline CRV ROC-status DQM: fills mu2e::CRVStatusDQM (Offline/CRVDQM)
// from CrvStatus and CrvDAQerror. Needs no geometry.
//

#include "art/Framework/Core/EDAnalyzer.h"
#include "art/Framework/Core/ModuleMacros.h"
#include "art/Framework/Principal/Event.h"
#include "art/Framework/Principal/SubRun.h"
#include "art/Framework/Services/Registry/ServiceHandle.h"
#include "art_root_io/TFileService.h"
#include "fhiclcpp/types/Atom.h"
#include "fhiclcpp/types/Table.h"

#include "Offline/CRVDQM/inc/CRVStatusDQM.hh"
#include "Offline/DQMHelpers/inc/DQMHistSetConfig.hh"
#include "Offline/RecoDataProducts/inc/CrvDAQerror.hh"
#include "Offline/RecoDataProducts/inc/CrvStatus.hh"

#include <fstream>
#include <string>

namespace mu2e {

class DqmCrvStatus : public art::EDAnalyzer {
 public:
  struct Config {
    using Name = fhicl::Name;
    using Comment = fhicl::Comment;
    fhicl::Atom<art::InputTag> statusTag{Name("statusTag"), Comment("CrvStatus collection")};
    fhicl::Atom<art::InputTag> daqErrorTag{Name("daqErrorTag"), Comment("CrvDAQerror collection")};
    fhicl::Table<DQMClientFhicl> dqm{
        Name("dqm"), Comment("CRVStatusDQM configuration; see Offline/CRVDQM/fcl/prolog.fcl")};
    fhicl::Atom<std::string> catalogueFile{
        Name("catalogueFile"),
        Comment("write the histogram catalogue (name, type, axes) here at end of job; empty skips it"),
        ""};
  };
  typedef art::EDAnalyzer::Table<Config> Parameters;

  explicit DqmCrvStatus(const Parameters& conf);

  void beginJob() override;
  void beginSubRun(const art::SubRun& sr) override;
  void endSubRun(const art::SubRun& sr) override;
  void analyze(const art::Event& event) override;
  void endJob() override;

 private:
  art::InputTag _statusTag;
  art::InputTag _daqErrorTag;
  std::string _catalogueFile;
  CRVStatusDQM _dqm;
};

DqmCrvStatus::DqmCrvStatus(const Parameters& conf) :
    art::EDAnalyzer(conf), _statusTag(conf().statusTag()), _daqErrorTag(conf().daqErrorTag()),
    _catalogueFile(conf().catalogueFile()), _dqm(toConfig(conf().dqm().hists())) {}

void DqmCrvStatus::beginJob() {
  art::ServiceHandle<art::TFileService> tfs;
  _dqm.Book(*tfs);
}

void DqmCrvStatus::beginSubRun(const art::SubRun& sr) { _dqm.BeginSubRun(sr.run(), sr.subRun()); }

void DqmCrvStatus::endSubRun(const art::SubRun&) { _dqm.EndSubRun(); }

void DqmCrvStatus::analyze(const art::Event& event) {
  //missing inputs throw: an empty DQM file must not look like a healthy DAQ
  _dqm.Fill(*event.getValidHandle<CrvStatusCollection>(_statusTag),
            *event.getValidHandle<CrvDAQerrorCollection>(_daqErrorTag));
}

void DqmCrvStatus::endJob() {
  _dqm.EndJob();
  if (!_catalogueFile.empty()) {
    std::ofstream out(_catalogueFile);
    _dqm.hists().WriteCatalogue(out);
  }
}

}  // namespace mu2e

DEFINE_ART_MODULE(mu2e::DqmCrvStatus)
