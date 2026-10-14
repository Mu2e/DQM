//
// Offline CRV reco DQM: fills mu2e::CRVRecoDQM (Offline/CRVDQM) from
// coincidence clusters and reco pulses, and at end of job fits each channel's
// PE spectrum into the MPV maps.
//

#include "art/Framework/Core/EDAnalyzer.h"
#include "art/Framework/Core/ModuleMacros.h"
#include "art/Framework/Principal/Event.h"
#include "art/Framework/Principal/SubRun.h"
#include "art/Framework/Services/Registry/ServiceHandle.h"
#include "art_root_io/TFileService.h"
#include "fhiclcpp/types/Atom.h"
#include "fhiclcpp/types/Table.h"

#include "Offline/CRVConditions/inc/CRVStatus.hh"
#include "Offline/CosmicRayShieldGeom/inc/CosmicRayShield.hh"
#include "Offline/CRVDQM/inc/CRVRecoDQM.hh"
#include "Offline/CRVDQM/inc/CRVDQMLayout.hh"
#include "Offline/DQMHelpers/inc/DQMHistSetConfig.hh"
#include "Offline/GeometryService/inc/GeomHandle.hh"
#include "Offline/ProditionsService/inc/ProditionsHandle.hh"
#include "Offline/RecoDataProducts/inc/CrvCoincidenceCluster.hh"
#include "Offline/RecoDataProducts/inc/CrvRecoPulse.hh"

#include <fstream>
#include <string>

namespace mu2e {

class DqmCrvReco : public art::EDAnalyzer {
 public:
  struct Config {
    using Name = fhicl::Name;
    using Comment = fhicl::Comment;
    fhicl::Atom<art::InputTag> clusterTag{
        Name("clusterTag"), Comment("CrvCoincidenceCluster collection")};
    fhicl::Atom<art::InputTag> pulseTag{
        Name("pulseTag"),
        Comment("CrvRecoPulse collection, for the per-pulse plots; the clusters' own pulses are "
                "reached through their Ptrs")};
    fhicl::Table<DQMClientFhicl> dqm{
        Name("dqm"), Comment("CRVRecoDQM configuration; see Offline/CRVDQM/fcl/prolog.fcl")};
    fhicl::Atom<std::string> catalogueFile{
        Name("catalogueFile"),
        Comment("write the histogram catalogue (name, type, axes) here at end of job; empty skips it"),
        ""};
  };
  typedef art::EDAnalyzer::Table<Config> Parameters;

  explicit DqmCrvReco(const Parameters& conf);

  void beginJob() override;
  void beginSubRun(const art::SubRun& sr) override;
  void endSubRun(const art::SubRun& sr) override;
  void analyze(const art::Event& event) override;
  void endJob() override;

 private:
  art::InputTag _clusterTag;
  art::InputTag _pulseTag;
  std::string _catalogueFile;
  ProditionsHandle<CRVStatus> _sipmStatus;
  CRVRecoDQM _dqm;
  int _layoutRun{-1};
};

DqmCrvReco::DqmCrvReco(const Parameters& conf) :
    art::EDAnalyzer(conf), _clusterTag(conf().clusterTag()), _pulseTag(conf().pulseTag()),
    _catalogueFile(conf().catalogueFile()), _dqm(toConfig(conf().dqm().hists())) {}

void DqmCrvReco::beginJob() {
  art::ServiceHandle<art::TFileService> tfs;
  _dqm.Book(*tfs);
}

void DqmCrvReco::beginSubRun(const art::SubRun& sr) { _dqm.BeginSubRun(sr.run(), sr.subRun()); }

void DqmCrvReco::endSubRun(const art::SubRun&) { _dqm.EndSubRun(); }

void DqmCrvReco::analyze(const art::Event& event) {
  const auto& clusters = *event.getValidHandle<CrvCoincidenceClusterCollection>(_clusterTag);
  const auto& pulses = *event.getValidHandle<CrvRecoPulseCollection>(_pulseTag);

  if (static_cast<int>(event.run()) != _layoutRun) {
    _layoutRun = event.run();
    GeomHandle<CosmicRayShield> crs;
    const int configuration = CRVDQMLayout::configuration(*crs);
    _dqm.SetConfiguration(configuration, CRVDQMLayout::channelToSector(
                                             *crs, configuration, &_sipmStatus.get(event.id())));
  }

  _dqm.Fill(clusters, pulses);
}

void DqmCrvReco::endJob() {
  _dqm.EndJob();
  if (!_catalogueFile.empty()) {
    std::ofstream out(_catalogueFile);
    _dqm.hists().WriteCatalogue(out);
  }
}

}  // namespace mu2e

DEFINE_ART_MODULE(mu2e::DqmCrvReco)
