//
// Offline CRV digi DQM: fills mu2e::CRVDigiDQM (Offline/CRVDQM) from
// CrvDigis and CrvStatus. Binning is fixed in the client; this module supplies
// the inputs, the geometry-derived layout, and the output directory.
//

#include "art/Framework/Core/EDAnalyzer.h"
#include "art/Framework/Core/ModuleMacros.h"
#include "art/Framework/Principal/Event.h"
#include "art/Framework/Principal/SubRun.h"
#include "art/Framework/Services/Registry/ServiceHandle.h"
#include "art_root_io/TFileService.h"
#include "fhiclcpp/types/Atom.h"
#include "fhiclcpp/types/Table.h"

#include "Offline/CRVConditions/inc/CRVOrdinal.hh"
#include "Offline/CRVConditions/inc/CRVStatus.hh"
#include "Offline/CosmicRayShieldGeom/inc/CosmicRayShield.hh"
#include "Offline/CRVDQM/inc/CRVDigiDQM.hh"
#include "Offline/CRVDQM/inc/CRVDQMLayout.hh"
#include "Offline/DQMHelpers/inc/DQMHistSetConfig.hh"
#include "Offline/GeometryService/inc/GeomHandle.hh"
#include "Offline/ProditionsService/inc/ProditionsHandle.hh"
#include "Offline/RecoDataProducts/inc/CrvDigi.hh"
#include "Offline/RecoDataProducts/inc/CrvStatus.hh"

#include <fstream>
#include <string>
#include <vector>

namespace mu2e {

class DqmCrvDigi : public art::EDAnalyzer {
 public:
  struct Config {
    using Name = fhicl::Name;
    using Comment = fhicl::Comment;
    fhicl::Atom<art::InputTag> digiTag{Name("digiTag"), Comment("CrvDigi collection")};
    fhicl::Atom<art::InputTag> statusTag{
        Name("statusTag"),
        Comment("CrvStatus collection, the window clock (EWT); empty for MC, which has none"),
        art::InputTag()};
    fhicl::Table<DQMClientFhicl> dqm{
        Name("dqm"), Comment("CRVDigiDQM configuration; see Offline/CRVDQM/fcl/prolog.fcl")};
    fhicl::Atom<std::string> catalogueFile{
        Name("catalogueFile"),
        Comment("write the histogram catalogue (name, type, axes) here at end of job; empty skips it"),
        ""};
  };
  typedef art::EDAnalyzer::Table<Config> Parameters;

  explicit DqmCrvDigi(const Parameters& conf);

  void beginJob() override;
  void beginSubRun(const art::SubRun& sr) override;
  void endSubRun(const art::SubRun& sr) override;
  void analyze(const art::Event& event) override;
  void endJob() override;

 private:
  art::InputTag _digiTag;
  art::InputTag _statusTag;
  std::string _catalogueFile;
  ProditionsHandle<CRVOrdinal> _channelMap;
  ProditionsHandle<CRVStatus> _sipmStatus;
  CRVDigiDQM _dqm;
  int _layoutRun{-1};
};

DqmCrvDigi::DqmCrvDigi(const Parameters& conf) :
    art::EDAnalyzer(conf), _digiTag(conf().digiTag()), _statusTag(conf().statusTag()),
    _catalogueFile(conf().catalogueFile()), _dqm(toConfig(conf().dqm().hists())) {}

void DqmCrvDigi::beginJob() {
  art::ServiceHandle<art::TFileService> tfs;
  _dqm.Book(*tfs);
}

void DqmCrvDigi::beginSubRun(const art::SubRun& sr) { _dqm.BeginSubRun(sr.run(), sr.subRun()); }

void DqmCrvDigi::endSubRun(const art::SubRun&) { _dqm.EndSubRun(); }

void DqmCrvDigi::analyze(const art::Event& event) {
  //missing inputs throw: an empty DQM file must not look like a quiet detector
  const auto& digis = *event.getValidHandle<CrvDigiCollection>(_digiTag);
  const CrvStatusCollection noStatus;
  const auto& status =
      _statusTag.empty() ? noStatus : *event.getValidHandle<CrvStatusCollection>(_statusTag);

  //the channel map and status can change between runs
  if (static_cast<int>(event.run()) != _layoutRun) {
    _layoutRun = event.run();
    GeomHandle<CosmicRayShield> crs;
    const int configuration = CRVDQMLayout::configuration(*crs);
    _dqm.SetConfiguration(configuration, CRVDQMLayout::channelToSector(
                                             *crs, configuration, &_sipmStatus.get(event.id())));
    std::vector<CRVDigiDQM::FebTopology> topology;
    std::vector<int> channelToLayer;
    CRVDQMLayout::febTopology(*crs, _channelMap.get(event.id()), topology, channelToLayer);
    _dqm.SetFebTopology(topology, channelToLayer);
  }

  _dqm.Fill(digis, status);
}

void DqmCrvDigi::endJob() {
  _dqm.EndJob();
  if (!_catalogueFile.empty()) {
    std::ofstream out(_catalogueFile);
    _dqm.hists().WriteCatalogue(out);
  }
}

}  // namespace mu2e

DEFINE_ART_MODULE(mu2e::DqmCrvDigi)
