//
// analyzer module producing DQM histograms for Stm subsystem
//
//


#include "art/Framework/Core/EDAnalyzer.h"
#include "art/Framework/Core/ModuleMacros.h"
#include "art/Framework/Principal/Event.h"
#include "art_root_io/TFileService.h"

#include "Offline/RecoDataProducts/inc/STMWaveformDigi.hh"
#include "Offline/RecoDataProducts/inc/STMFragmentSummary.hh"
#include "Offline/DataProducts/inc/STMChannel.hh" 
#include "Offline/Mu2eUtilities/inc/STMUtils.hh"
#include "Offline/ProditionsService/inc/ProditionsHandle.hh"
#include "Offline/RecoDataProducts/inc/STMPHDigi.hh"
#include "Offline/STMConditions/inc/STMEnergyCalib.hh"

#include "TH1F.h"

#include <string>
#include <vector>

namespace mu2e {

class DqmStm : public art::EDAnalyzer {
 public:
  struct Config {
    using Name = fhicl::Name;
    using Comment = fhicl::Comment;
    //For now using explciit tags
    fhicl::Atom<art::InputTag> rawHPGeTag{Name("rawHPGeTag"), Comment("StmWaveform rawHPGe Collection"), art::InputTag()};
    fhicl::Atom<art::InputTag> rawLaBrTag{Name("rawLaBrTag"), Comment("StmWaveform rawLaBr Collection"), art::InputTag()};
    fhicl::Atom<art::InputTag> zsHPGeTag{Name("zsHPGeTag"), Comment("StmWaveform zsHPGe Collection"), art::InputTag()}; 
    fhicl::Atom<art::InputTag> zsLaBrTag{Name("zsLaBrTag"), Comment("StmWaveform zsLaBr Collection"), art::InputTag()};
    fhicl::Atom<art::InputTag> phHPGeTag{Name("phHPGeTag"), Comment("StmDigi phHPge Collection"), art::InputTag()};
    fhicl::Atom<art::InputTag> phLaBrTag{Name("phLaBrTag"), Comment("StmDigi phLaBr Collection"), art::InputTag()};
    fhicl::Atom<art::InputTag> HPGefragSummaryTag{Name("HPGefragSummaryTag"), Comment("STM HPGe fragment summary collection"), art::InputTag()};
    fhicl::Atom<art::InputTag> LaBrfragSummaryTag{Name("LaBrfragSummaryTag"), Comment("STM LaBr fragment summary collection"), art::InputTag()};

    //For later use
    fhicl::Atom<art::InputTag> stmDigisTag{Name("digiTag"), Comment("STM Digi Collection"), art::InputTag()};
    fhicl::Atom<art::InputTag> stmPHDigisTag{Name("stmPHDigisTag"), Comment("Input Tag fo STMPHDigiCollection"), art::InputTag()};
    // fhicl::Atom<art::InputTag> recoTag{Name("recoTag"), Comment("STMRecoPulses Collection"), art::InputTag()};
  };
  typedef art::EDAnalyzer::Table<Config> Parameters;

  explicit DqmStm(const Parameters& conf);
  virtual ~DqmStm() {}

  virtual void beginJob();
  virtual void endJob(){};
  virtual void analyze(const art::Event& e);

private:
  Config _conf;

  //Version number tracked
  TH1D* _hVer;
  // Container and Inner Frag Counts
  TH1D* _hNContainerFrags;
  TH1D* _hNTotalInnerFrags;

  //Raw
  TH1D* _hNRAWHPGe; //Raw Waveform size
  TH1D* _hNRAWLaBr;
  TH1D* _hNGoodRawHPGeInnerFrags;
  TH1D* _hNGoodRawLaBrInnerFrags;
  TH1D* _hNZeroRawHPGeInnerFrags;
  TH1D* _hNZeroRawLaBrInnerFrags;
  TH1D* _hNEmptyRawHPGeInnerFrags;
  TH1D* _hNEmptyRawLaBrInnerFrags;
  TH1D* _hRawHPGeADC;
  TH1D* _hRawLaBrADC;

  //ZS
  TH1D* _hNZSHPGe; //ZS Waveform size 
  TH1D* _hNZSLaBr;
  TH1D* _hNGoodZSHPGeInnerFrags;
  TH1D* _hNGoodZSLaBrInnerFrags;
  TH1D* _hNZeroZSHPGeInnerFrags;
  TH1D* _hNZeroZSLaBrInnerFrags;
  TH1D* _hNEmptyZSHPGeInnerFrags;
  TH1D* _hNEmptyZSLaBrInnerFrags;
  TH1D* _hZSHPGeADC;
  TH1D* _hZSLaBrADC;

  // PH digis
  // TH1D* _hNPHHPGeInnerFrags;
  // TH1D* _hNPHLaBrInnerFrags;
  TH1D* _hNPHHPGe; //Number of pulse heights for HPGe
  TH1D* _hPulseHeightHPGe; //Pulse Heigt of HPGe
  TH1D* _hNPHLaBr; //Number of pulse heights for LaBr                                                          
  TH1D* _hPulseHeightLaBr; //Pulse Heigt of LaBr
  TH1D* _hNGoodPHHPGeInnerFrags;
  TH1D* _hNGoodPHLaBrInnerFrags;
  TH1D* _hNZeroPHHPGeInnerFrags;
  TH1D* _hNZeroPHLaBrInnerFrags;
  TH1D* _hNEmptyPHHPGeInnerFrags;
  TH1D* _hNEmptyPHLaBrInnerFrags;
  
};
/*****************************/
  // configrues fcl to local variables
  //Will come back to simplify this with channel name
DqmStm::DqmStm(const Parameters& conf) : art::EDAnalyzer(conf), _conf(conf()) {
  // STMDigisFromFragments writes the waveform and pulse-height digis as
  // maps, with one entry per STM event (event window) in the art event
  mayConsume<STMPHDigiCollectionMap>(_conf.phHPGeTag()); //reads PH from the art file given in fcl
  mayConsume<STMPHDigiCollectionMap>(_conf.phLaBrTag());
  mayConsume<STMWaveformDigiCollectionMap>(_conf.rawHPGeTag());
  mayConsume<STMWaveformDigiCollectionMap>(_conf.rawLaBrTag());
  mayConsume<STMWaveformDigiCollectionMap>(_conf.zsHPGeTag());
  mayConsume<STMWaveformDigiCollectionMap>(_conf.zsLaBrTag());
  mayConsume<STMFragmentSummaryCollection>(_conf.HPGefragSummaryTag());
  mayConsume<STMFragmentSummaryCollection>(_conf.LaBrfragSummaryTag());
  //mayConsume<STMFragmentSummaryCollection>(_conf.stmPHDigisTag);
  //Will add more in time such as raw, zs, frag count etc. 
}

/*****************************************/
  // makes the hist -> working with _hNPH and _hPulseHeights
void DqmStm::beginJob() {
  art::ServiceHandle<art::TFileService> tfs;
  
  _hVer = tfs->make<TH1D>("Ver", "Version Number", 101, -0.5, 100.00);

  //histograms
  if (!_conf.rawHPGeTag().empty()){
    _hNRAWHPGe = tfs->make<TH1D>("NRawWaveformDigisHPGe", "N RAW HPGe WaveformDigis;Number of Raw WF Digis;Entries", 250, -0.5, 500.5);
    _hRawHPGeADC = tfs->make<TH1D>("RawADCHPGe","Raw HPGe ADC in Waveform;ADC;Samples", 500,-500.0,500.0); 
  }

  if (!_conf.rawLaBrTag().empty()){
    _hNRAWLaBr = tfs->make<TH1D>("NRawWaveformDigisLaBr", "N RAW LaBr WaveformDigis;Number of Raw WF Digis:Entries", 250, -0.5, 500.5);
     _hRawLaBrADC = tfs->make<TH1D>("RawADCLaBr","Raw LaBr ADC in Waveform;ADC;Samples", 500,-500.0,500.0);
  }

  if (!_conf.zsHPGeTag().empty()){
    _hNZSHPGe = tfs->make<TH1D>("NZSWaveformDigisHPGe", "N ZS HPGe WaveformDigis;Number of ZS WF Digis;Entries", 250, -0.5, 500.5);
    _hZSHPGeADC = tfs->make<TH1D>("ZSADCHPGe","ZS HPGe ADC in Waveform;ADC;Samples", 500,-500.0,500.0);
  }

  if (!_conf.zsLaBrTag().empty()){
    _hNZSLaBr = tfs->make<TH1D>("NZSWaveformDigisLaBr", "N ZS LaBr WaveformDigis;Number of ZS WF Digis;Entries", 250, -0.5, 500.5);
    _hZSLaBrADC = tfs->make<TH1D>("ZSADCLaBr","ZS LaBr ADC in Waveform;ADC;Samples", 500,-500.0,500.0);
  }

  if (!_conf.phHPGeTag().empty()){
    _hNPHHPGe = tfs->make<TH1D>("NPHDigisHPGe", "N PH HPGe Digis;Number of Pulse Heiht Digis: Entries", 20, -0.5, 30.5);
    _hPulseHeightHPGe = tfs->make<TH1D>("PulseHeightHPGe", "STM HPGe Pulse Height;Pulse Height;Entries", 1000, 0.0, 10000.0);
  }

  if (!_conf.phLaBrTag().empty()){
    _hNPHLaBr = tfs->make<TH1D>("NPHDigisLaBr", "N PH LaBr Digis;Number of Pulse Height Digis;Entries", 20, -0.5, 30.5);
    _hPulseHeightLaBr = tfs->make<TH1D>("PulseHeightLaBr", "STM LaBr Pulse Height;Pulse Height;Entries", 1000, 0.0, 10000.0);
  }

  if (!_conf.HPGefragSummaryTag().empty()){
    _hNContainerFrags = tfs->make<TH1D>("NContainerFrags",
					"N STM Container Fragments;Number of Container Frags;Events",
					4,-0.5,4);
    _hNTotalInnerFrags = tfs->make<TH1D>("NTotalInnerFrags",
					 "N STM Inner Fragments;Number of Inner Frags;Events",
					 200,-0.5,2000.5);
    
    _hNGoodRawHPGeInnerFrags = tfs->make<TH1D>("NGoodRawHPGeInnerFrags",
					       "N Good Raw HPGE Inner Frags; Number of Inner Frags;Events",
					       200,-10.5, 250.5);
    _hNGoodZSHPGeInnerFrags = tfs->make<TH1D>("NGoodZSHPGeInnerFrags",
					      "N Good ZS HPGE Inner Frags; Number of Inner Frags;Events",
					      200,-10.5, 250.5);
    _hNGoodPHHPGeInnerFrags = tfs->make<TH1D>("NGoodPHHPGeInnerFrags",
					      "N Good PH HPGE Inner Frags; Number of Inner Frags;Events",
					      200,-10.5,250.5);
    _hNZeroRawHPGeInnerFrags = tfs->make<TH1D>("NZeroRawHPGeInnerFrags",
					       "N Zero Raw HPGE Inner Frags; Number of Inner Frags;Events",
					       200,-10.5,250.5);
    _hNZeroZSHPGeInnerFrags = tfs->make<TH1D>("NZeroZSHPGeInnerFrags",
					      "N ZS HPGE Inner Frags; Number of Inner Frags;Events",
					      200,-10.5,250.5);   
    _hNZeroPHHPGeInnerFrags = tfs->make<TH1D>("NZeroPHHPGeInnerFrags",
					      "N PH HPGE Inner Frags; Number of Inner Frags;Events",
					      200,-10.5,250.5);   
    _hNEmptyRawHPGeInnerFrags = tfs->make<TH1D>("NEmptyRawHPGeInnerFrags",
						"N Raw HPGE Inner Frags; Number of Inner Frags;Events ",
						200,-10.5,250.5);
    _hNEmptyZSHPGeInnerFrags = tfs->make<TH1D>("NEmptyZSHPGeInnerFrags",
					      "N ZS HPGE Inner Frags; Number of Inner Frags;Events",
					       200,-10.5,250.5);   
    _hNEmptyPHHPGeInnerFrags = tfs->make<TH1D>("NEmptyPHHPGeInnerFrags",
					      "N PH HPGE Inner Frags; Number of Inner Frags;Events",
					      200,-10.5,250.5);   
  }

  if (!_conf.LaBrfragSummaryTag().empty()){
    _hNGoodRawLaBrInnerFrags = tfs->make<TH1D>("NGoodRawLaBrInnerFrags",
					       "N Raw LaBr Inner Frags; Number of Inner Frags;Events",
					       200, -10.5, 250.5);
    _hNGoodZSLaBrInnerFrags = tfs->make<TH1D>("NGoodZSLaBrInnerFrags",
					      "N ZS LaBr Inner Frags; Number of Inner Frags;Events",
					      200, -10.5, 250.5);
    _hNGoodPHLaBrInnerFrags = tfs->make<TH1D>("NGoodPHLaBrInnerFrags",
					      "N PH LaBr Inner Frags; Number of Inner Frags;Events",
					      200, -10.5, 250.5);
    _hNZeroRawLaBrInnerFrags = tfs->make<TH1D>("NZeroRawLaBrInnerFrags",
                                               "N Zero Raw LaBr Inner Frags; Number of Inner Frags;Events",
                                               200, -10.5, 250.5);
    _hNZeroZSLaBrInnerFrags = tfs->make<TH1D>("NZeroZSLaBrInnerFrags",
                                              "N Zero ZS LaBr Inner Frags; Number of Inner Frags;Events",
                                              200, -10.5, 250.5);
    _hNZeroPHLaBrInnerFrags = tfs->make<TH1D>("NZeroPHLaBrInnerFrags",
                                              "N Zero PH LaBr Inner Frags; Number of Inner Frags;Events",
                                              200, -10.5, 250.5);
    _hNEmptyRawLaBrInnerFrags = tfs->make<TH1D>("NEmptyRawLaBrInnerFrags",
                                                "N Empty Raw LaBr Inner Frags; Number of Inner Frags;Events ",
                                                200, -10.5, 250.5);
    _hNEmptyZSLaBrInnerFrags = tfs->make<TH1D>("NEmptyZSLaBrInnerFrags",
                                              "N Empty ZS LaBr Inner Frags; Number of Inner Frags;Events",
                                               200, -10.5, 250.5);
    _hNEmptyPHLaBrInnerFrags = tfs->make<TH1D>("NEmptyPHLaBrInnerFrags",
                                              "N Empty PH LaBr Inner Frags; Number of Inner Frags;Events",
                                              200, -10.5, 250.5);
  }
}


/************************************/
  // Filling the histograms
void DqmStm::analyze(const art::Event& event) {
  _hVer->Fill(0.0);

  if(!_conf.HPGefragSummaryTag().empty() ){
    auto summaryHandle = event.getValidHandle<STMFragmentSummaryCollection>(_conf.HPGefragSummaryTag());
    for (const auto& summary : *summaryHandle){
      _hNContainerFrags->Fill(summary.nContainerFrags());
      _hNTotalInnerFrags->Fill(summary.nInnerFrags());
      _hNGoodRawHPGeInnerFrags ->Fill(summary.nGoodRawFrags());
      _hNGoodZSHPGeInnerFrags ->Fill(summary.nGoodZSFrags());
      _hNGoodPHHPGeInnerFrags ->Fill(summary.nGoodPHFrags());
      _hNZeroRawHPGeInnerFrags ->Fill(summary.nZeroRawFrags());
      _hNZeroZSHPGeInnerFrags ->Fill(summary.nZeroZSFrags());
      _hNZeroPHHPGeInnerFrags ->Fill(summary.nZeroPHFrags());
      _hNEmptyRawHPGeInnerFrags ->Fill(summary.nEmptyRawFrags());
      _hNEmptyZSHPGeInnerFrags ->Fill(summary.nEmptyZSFrags());
      _hNEmptyPHHPGeInnerFrags ->Fill(summary.nEmptyPHFrags());

    }
  }

  if(!_conf.LaBrfragSummaryTag().empty() ){
    auto summaryHandle = event.getValidHandle<STMFragmentSummaryCollection>(_conf.LaBrfragSummaryTag());
    for (const auto& summary : *summaryHandle){
      //_hNContainerFrags->Fill(summary.nContainerFrags());
      //_hNInnerFrags->Fill(summary.nInnerFrags());
      _hNGoodRawLaBrInnerFrags ->Fill(summary.nGoodRawFrags());
      _hNGoodZSLaBrInnerFrags ->Fill(summary.nGoodZSFrags());
      _hNGoodPHLaBrInnerFrags ->Fill(summary.nGoodPHFrags());
      _hNZeroRawLaBrInnerFrags ->Fill(summary.nZeroRawFrags());
      _hNZeroZSLaBrInnerFrags ->Fill(summary.nZeroZSFrags());
      _hNZeroPHLaBrInnerFrags ->Fill(summary.nZeroPHFrags());
      _hNEmptyRawLaBrInnerFrags ->Fill(summary.nEmptyRawFrags());
      _hNEmptyZSLaBrInnerFrags ->Fill(summary.nEmptyZSFrags());
      _hNEmptyPHLaBrInnerFrags ->Fill(summary.nEmptyPHFrags());
    }
  }

  // Each art event holds many STM events, one map entry each.  The count
  // histograms are filled once per STM event, as Offline's
  // ValSTMWaveformDigi does.
  if (!_conf.rawHPGeTag().empty()) {
    auto rawDigiHandle = event.getValidHandle<STMWaveformDigiCollectionMap>(_conf.rawHPGeTag());
    for (const auto& [header, rawdigis] : *rawDigiHandle) {
      _hNRAWHPGe->Fill(rawdigis.size());
      for (const auto& dg : rawdigis){
        for (const auto& adc : dg.adcs()) _hRawHPGeADC->Fill(adc);}
    }
  }

  if (!_conf.rawLaBrTag().empty()) {
    auto rawDigiHandle = event.getValidHandle<STMWaveformDigiCollectionMap>(_conf.rawLaBrTag());
    for (const auto& [header, rawdigis] : *rawDigiHandle) {
      _hNRAWLaBr->Fill(rawdigis.size());
      for (const auto& dg : rawdigis){
        for (const auto& adc : dg.adcs()) _hRawLaBrADC->Fill(adc);}
    }
  }

  if (!_conf.zsHPGeTag().empty()) {
    auto zsDigiHandle = event.getValidHandle<STMWaveformDigiCollectionMap>(_conf.zsHPGeTag());
    for (const auto& [header, zsdigis] : *zsDigiHandle) {
      _hNZSHPGe->Fill(zsdigis.size());
      for (const auto& dg : zsdigis){
        for (const auto& adc : dg.adcs()) _hZSHPGeADC->Fill(adc);}
    }
  }

  if (!_conf.zsLaBrTag().empty()) {
    auto zsDigiHandle = event.getValidHandle<STMWaveformDigiCollectionMap>(_conf.zsLaBrTag());
    for (const auto& [header, zsdigis] : *zsDigiHandle) {
      _hNZSLaBr->Fill(zsdigis.size());
      for (const auto& dg : zsdigis){
        for (const auto& adc : dg.adcs()) _hZSLaBrADC->Fill(adc);}
    }
  }

  if (!_conf.phHPGeTag().empty()) {
    auto phDigiHandle = event.getValidHandle<STMPHDigiCollectionMap>(_conf.phHPGeTag());
    for (const auto& [header, phDigis] : *phDigiHandle) {
      _hNPHHPGe->Fill(phDigis.size());
      for (const auto& phDigi: phDigis) {
        _hPulseHeightHPGe->Fill(phDigi.energy());
      }
    }
  }

  if (!_conf.phLaBrTag().empty()) {
    auto phDigiHandle = event.getValidHandle<STMPHDigiCollectionMap>(_conf.phLaBrTag());
    for (const auto& [header, phDigis] : *phDigiHandle) {
      _hNPHLaBr->Fill(phDigis.size());
      for (const auto& phDigi: phDigis) {
        _hPulseHeightLaBr->Fill(phDigi.energy());
      }
    }
  }


}
} //namespace mu2e
  
DEFINE_ART_MODULE(mu2e::DqmStm)
