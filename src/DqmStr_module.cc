//
// analyzer module producing DQM histograms for Str subsystem
//
//

#include "art/Framework/Core/EDAnalyzer.h"
#include "art/Framework/Core/ModuleMacros.h"
#include "art/Framework/Principal/Event.h"
#include "art_root_io/TFileService.h"

#include "Offline/RecoDataProducts/inc/StrawDigi.hh"
#include "Offline/RecoDataProducts/inc/StrawHit.hh"
#include "Offline/RecoDataProducts/inc/StrawHitFlag.hh"

#include "TH1F.h"

#include <string>
#include <vector>

namespace mu2e {

class DqmStr : public art::EDAnalyzer {
 public:
  struct Config {
    using Name = fhicl::Name;
    using Comment = fhicl::Comment;
    fhicl::Atom<art::InputTag> digiTag{
        Name("digiTag"), Comment("StrawDigi Collection"), art::InputTag()};
    fhicl::Atom<art::InputTag> adcTag{
        Name("adcTag"), Comment("ADCWaveform Collection"), art::InputTag()};
    // fhicl::Atom<art::InputTag> hitTag{Name("hitTag"),
    //   Comment("StrawHit Collection"), art::InputTag()};
    fhicl::Atom<art::InputTag> flagTag{
        Name("flagTag"), Comment("StrawHitFlag Collection"), art::InputTag()};
  };
  typedef art::EDAnalyzer::Table<Config> Parameters;

  explicit DqmStr(const Parameters& conf);
  virtual ~DqmStr() {}

  virtual void beginJob();
  virtual void endJob(){};
  virtual void analyze(const art::Event& e);

 private:
  Config _conf;

  TH1D* _hVer;
  // digi
  TH1D* _hdN;
  TH1D* _hdN2;
  TH1D* _hdtdc;
  TH1D* _hdtdc2;
  TH1D* _hdtot;
  TH1D* _hdpmp;
  TH1D* _hdDI;
  TH1D* _hdSI;
  // adc
  TH1D* _haN;
  TH1D* _haN2;
  TH1D* _halen;
  TH1D* _haadc;
  TH1D* _hapmp;
  // hit
  // TH1D* _hhN;
  // TH1D* _hhN2;
  // TH1D* _hht;
  // TH1D* _hhdt;
  // TH1D* _hhE;
  // TH1D* _hhDI;
  // TH1D* _hhSI;
  // flags
  TH1D* _hfN;
  TH1D* _hfN2;
  TH1D* _hfBits;
};

/********************************************************/

DqmStr::DqmStr(const Parameters& conf) : art::EDAnalyzer(conf), _conf(conf()) {
  mayConsume<StrawDigiCollection>(_conf.digiTag());
  mayConsume<StrawDigiADCWaveformCollection>(_conf.adcTag());
  // mayConsume<StrawHitCollection>(_conf.hitTag());
  mayConsume<StrawHitFlagCollection>(_conf.flagTag());
}

/********************************************************/

void DqmStr::beginJob() {
  art::ServiceHandle<art::TFileService> tfs;

  _hVer = tfs->make<TH1D>("Ver", "Version Number", 101, -0.5, 100.0);

  if (!_conf.digiTag().empty()) {
    _hdN = tfs->make<TH1D>("NDigi", "N Digi", 101, -0.5, 100.0);
    _hdN2 = tfs->make<TH1D>("NDigi2", "N Digi", 100, -0.5, 9999.5);
    _hdtdc = tfs->make<TH1D>("TDC", "Digi TDC", 100, 0.0, 80.0e3);
    _hdtdc2 = tfs->make<TH1D>("TDC2", "Digi TDC2", 100, 0.0, 5.0e6);
    _hdtot = tfs->make<TH1D>("TOT", "Digi TOT", 21, -0.5, 20.5);
    _hdpmp = tfs->make<TH1D>("PMP", "Digi PMP", 50, -0.5, 1000.0);
    _hdDI = tfs->make<TH1D>("DPlanePanel", "Digi Plane*6+Panel Index", 240,
                            -0.5, 239.5);
    _hdSI = tfs->make<TH1D>("DStraw", "Digi Straw Index", 96, -0.5, 95.5);
  }

  if (!_conf.adcTag().empty()) {
    _haN = tfs->make<TH1D>("NAdc", "N ADC Waveform", 101, -0.5, 100.0);
    _haN2 = tfs->make<TH1D>("NAdc2", "N ADC Waveform", 100, -0.5, 9999.5);
    _halen = tfs->make<TH1D>("len", "ADC len", 51, -0.5, 50.5);
    _haadc = tfs->make<TH1D>("ADC", "ADC value", 100, 200.0, 1200.0);
    _hapmp = tfs->make<TH1D>("aPMP", "ADC PMP", 100, -0.5, 1000.0);
  }

  // if(!_conf.hitTag().empty()) {
  //  _hhN = tfs->make<TH1D>( "NHit", "N Straw Hits", 101, -0.5, 100.0);
  //  _hhN2 = tfs->make<TH1D>( "NHit2", "N Straw Hits", 100, -0.5, 9999.5);
  //  _hht = tfs->make<TH1D>( "t", "Hit time", 100, 0.0, 2000.0);
  //  _hhdt = tfs->make<TH1D>( "dt", "Hit d-time", 100, -15.0, 15.0);
  //  _hhE = tfs->make<TH1D>( "E", "Hit Energy",50, 0.0, 0.01);
  //  _hhDI = tfs->make<TH1D>( "HPlanePanel", "Hit Plane*6+Panel Index",240,
  //  -0.5, 239.5); _hhSI = tfs->make<TH1D>( "HStraw", "Hit Straw Index",96,
  //  -0.5, 95.5);
  //}

  if (!_conf.flagTag().empty()) {
    _hfN = tfs->make<TH1D>("NFlag", "N Straw Hit flags", 101, -0.5, 100.5);
    _hfN2 = tfs->make<TH1D>("NFlag2", "N Straw Hit flags", 100, -0.5, 9999.5);
    _hfBits = tfs->make<TH1D>("Bits", "Bits", 32, -0.5, 31.5);
  }
}

/********************************************************/

void DqmStr::analyze(const art::Event& event) {
  _hVer->Fill(0.0);

  if (!_conf.digiTag().empty()) {
    auto digiH = event.getValidHandle<StrawDigiCollection>(_conf.digiTag());
    const auto& digis = *digiH;
    _hdN->Fill(digis.size());
    _hdN2->Fill(digis.size());
    for (auto sd : digis) {
      const mu2e::StrawId& id = sd.strawId();
      for (size_t ie = 0; ie < StrawEnd::nends;
           ie++) {  // for the two straw ends
        _hdtdc->Fill(sd.TDC()[ie]);
        _hdtdc2->Fill(sd.TDC()[ie]);
        _hdtot->Fill(sd.TOT()[ie]);
      }
      _hdpmp->Fill(sd.PMP());  // ADC value as peak minus pedestal
      _hdDI->Fill(6 * id.getPlane() + id.getPanel());
      _hdSI->Fill(id.getStraw());
    }
  }

  if (!_conf.adcTag().empty()) {
    auto adcH =
        event.getValidHandle<StrawDigiADCWaveformCollection>(_conf.adcTag());
    const auto& adcs = *adcH;

    _haN->Fill(adcs.size());
    _haN2->Fill(adcs.size());
    for (auto wf : adcs) {
      _halen->Fill(wf.samples().size());
      int max = 0;
      for (auto const a : wf.samples()) {  // for the two straw ends
        max = std::max(max, int(a) - int(wf.samples()[0]));
        _haadc->Fill(a);
      }
      _hapmp->Fill(max);  // ADC value as peak minus pedestal
    }
  }

  if (!_conf.flagTag().empty()) {
    auto flagH = event.getValidHandle<StrawHitFlagCollection>(_conf.flagTag());
    const auto& flags = *flagH;
    _hfN->Fill(flags.size());
    _hfN2->Fill(flags.size());
    for (auto f : flags) {
      for (auto sn : f.bitNames()) {
        if (f.hasAnyProperty(StrawHitFlag(sn.first)))
          _hfBits->Fill(std::log2(sn.second));
      }
    }
  }
}
}  // namespace mu2e

DEFINE_ART_MODULE(mu2e::DqmStr);
