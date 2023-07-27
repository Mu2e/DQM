//
// analyzer module producing DQM histograms for Crv subsystem
//
//

#include "art/Framework/Core/EDAnalyzer.h"
#include "art/Framework/Core/ModuleMacros.h"
#include "art/Framework/Principal/Event.h"
#include "art_root_io/TFileService.h"

#include "Offline/RecoDataProducts/inc/CrvCoincidenceCluster.hh"
#include "Offline/RecoDataProducts/inc/CrvDigi.hh"
#include "Offline/RecoDataProducts/inc/CrvRecoPulse.hh"

#include "TH1F.h"

#include <string>
#include <vector>

namespace mu2e {

class DqmCrv : public art::EDAnalyzer {
 public:
  struct Config {
    using Name = fhicl::Name;
    using Comment = fhicl::Comment;
    fhicl::Atom<art::InputTag> digiTag{
        Name("digiTag"), Comment("CrvDigi Collection"), art::InputTag()};
    fhicl::Atom<art::InputTag> recoTag{
        Name("recoTag"), Comment("CrvRecoPulses Collection"), art::InputTag()};
    fhicl::Atom<art::InputTag> clusTag{
        Name("clusTag"), Comment("CrvCoincidenceClusters Collection"),
        art::InputTag()};
  };
  typedef art::EDAnalyzer::Table<Config> Parameters;

  explicit DqmCrv(const Parameters& conf);
  virtual ~DqmCrv() {}

  virtual void beginJob();
  virtual void endJob(){};
  virtual void analyze(const art::Event& e);

 private:
  Config _conf;

  TH1D* _hVer;

  // digi
  TH1D* _hdN;
  TH1D* _hdN2;
  TH1D* _hdI;
  TH1D* _hdIS;
  TH1D* _hdt;
  TH1D* _hdt2;
  TH1D* _hdA;

  // reco pulses
  TH1D* _hrN;
  TH1D* _hrN2;
  TH1D* _hrI;
  TH1D* _hrPE;
  TH1D* _hrPH;
  TH1D* _hrt;
  TH1D* _hrt2;
  TH1D* _hrChi2;
  TH1D* _hrLChi2;
  TH1D* _hrLE;
  TH1D* _hrLE2;

  // cioncidence clusters
  TH1D* _hcN;
  TH1D* _hcNP;
  TH1D* _hcPE;
  TH1D* _hct;
  TH1D* _hct2;
  TH1D* _hcx;
  TH1D* _hcy;
  TH1D* _hcz;
};

/********************************************************/

DqmCrv::DqmCrv(const Parameters& conf) : art::EDAnalyzer(conf), _conf(conf()) {
  mayConsume<CrvDigiCollection>(_conf.digiTag());
  mayConsume<CrvRecoPulseCollection>(_conf.recoTag());
  mayConsume<CrvCoincidenceClusterCollection>(_conf.clusTag());
}

/********************************************************/

void DqmCrv::beginJob() {
  art::ServiceHandle<art::TFileService> tfs;

  _hVer = tfs->make<TH1D>("Ver", "Version Number", 101, -0.5, 100.0);

  if (!_conf.digiTag().empty()) {
    _hdN = tfs->make<TH1D>("NDigis", "N Digis", 101, -0.5, 100.5);
    _hdN2 = tfs->make<TH1D>("NDigis2", "N Digis", 100, -0.5, 4999.5);
    _hdI = tfs->make<TH1D>("BarIdd", "Digi Bar ID", 200, -0.5, 5503.5);
    _hdIS = tfs->make<TH1D>("SiPM", "SiPM", 4, -0.5, 3.5);
    _hdt = tfs->make<TH1D>("td", "TDC", 100, 0.0, 250.0);
    _hdt2 = tfs->make<TH1D>("t2d", "TDC", 100, 0.0, 1.5e4);
    _hdA = tfs->make<TH1D>("ADC", "ADC in waveform", 100, 0.0, 3000.0);
  }

  if (!_conf.recoTag().empty()) {
    _hrN = tfs->make<TH1D>("NPulses", "N Pulses", 101, -0.5, 100.5);
    _hrN2 = tfs->make<TH1D>("NPulse2", "N Pulses", 100, -0.5, 2000.0);
    _hrI = tfs->make<TH1D>("BarIdr", "RPulse Bar ID", 200, -0.5, 5503.5);
    _hrPE = tfs->make<TH1D>("PEr", "Fit Photoelectrons", 100, 0.0, 400.0);
    _hrPH =
        tfs->make<TH1D>("PEHeight", "PE from Pulse Height", 100, 0.0, 400.0);
    _hrt = tfs->make<TH1D>("PulseTime", "Pulse Peak Time", 100, 0.0, 2000.0);
    _hrt2 = tfs->make<TH1D>("PulseTime2", "Pulse Peak Time", 100, 0.0, 100.0e3);
    _hrChi2 = tfs->make<TH1D>("chi2", "Pulse fit chi2", 100, 0.0, 20.0);
    _hrLChi2 =
        tfs->make<TH1D>("logchi2", "log10 Pulse fit chi2", 100, -3.0, 5.0);
    _hrLE =
        tfs->make<TH1D>("LeadingTime", "Leading Edge Time", 100, 0.0, 2000.0);
    _hrLE2 =
        tfs->make<TH1D>("LeadingTime2", "Leading Edge Time", 100, 0.0, 100.0e3);
  }

  if (!_conf.clusTag().empty()) {
    _hcN = tfs->make<TH1D>("NClus", "N Clusters", 101, -0.5, 100.5);
    _hcNP = tfs->make<TH1D>("NPc", "N Pulse", 101, -0.5, 100.5);
    _hcPE = tfs->make<TH1D>("PEc", "clus PE", 100, 0.0, 2000.0);
    _hct = tfs->make<TH1D>("tc", "clus start time", 100, 0.0, 2000.0);
    _hct2 = tfs->make<TH1D>("t2c", "clus start time", 100, 0.0, 100.0e3);
    _hcx = tfs->make<TH1D>("X", "clus X", 100, -3904 - 3000, -3904 + 3000);
    _hcy = tfs->make<TH1D>("Y", "clus Y", 100, 0, 3000);
    _hcz = tfs->make<TH1D>("Z", "clus Z", 100, -3500, 20000);
  }
}

/********************************************************/

void DqmCrv::analyze(const art::Event& event) {
  _hVer->Fill(0.0);

  if (!_conf.digiTag().empty()) {
    auto digiH = event.getValidHandle<CrvDigiCollection>(_conf.digiTag());
    const auto& digis = *digiH;
    _hdN->Fill(digis.size());
    _hdN2->Fill(digis.size());
    for (auto dg : digis) {
      _hdI->Fill(dg.GetScintillatorBarIndex().asInt());
      _hdIS->Fill(dg.GetSiPMNumber());
      _hdt->Fill(dg.GetStartTDC());
      _hdt2->Fill(dg.GetStartTDC());
      for (auto a : dg.GetADCs()) _hdA->Fill(a);
    }
  }

  if (!_conf.recoTag().empty()) {
    auto recoH = event.getValidHandle<CrvRecoPulseCollection>(_conf.recoTag());
    const auto& recos = *recoH;
    _hrN->Fill(recos.size());
    _hrN2->Fill(recos.size());
    for (auto rp : recos) {
      _hrI->Fill(rp.GetScintillatorBarIndex().asInt());
      _hrPE->Fill(rp.GetPEs());
      _hrPH->Fill(rp.GetPEsPulseHeight());
      _hrt->Fill(rp.GetPulseTime());
      _hrt2->Fill(rp.GetPulseTime());
      _hrChi2->Fill(rp.GetPulseFitChi2());
      if (rp.GetPulseFitChi2() > 0.0)
        _hrLChi2->Fill(std::log10(rp.GetPulseFitChi2()));
      _hrLE->Fill(rp.GetLEtime());
      _hrLE2->Fill(rp.GetLEtime());
    }
  }

  if (!_conf.clusTag().empty()) {
    auto clusH =
        event.getValidHandle<CrvCoincidenceClusterCollection>(_conf.clusTag());
    const auto& cluss = *clusH;
    _hcN->Fill(cluss.size());
    for (auto cc : cluss) {
      _hcNP->Fill(cc.GetCrvRecoPulses().size());
      _hcPE->Fill(cc.GetPEs());
      _hct->Fill(cc.GetStartTime());
      _hct2->Fill(cc.GetStartTime());
      _hcx->Fill(cc.GetAvgCounterPos().x());
      _hcy->Fill(cc.GetAvgCounterPos().y());
      _hcz->Fill(cc.GetAvgCounterPos().z());
    }
  }
}
}  // namespace mu2e

DEFINE_ART_MODULE(mu2e::DqmCrv)
