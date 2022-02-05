//
// analyzer module producing DQM histograms for Cal subsystem
//
//

#include "art/Framework/Core/EDAnalyzer.h"
#include "art/Framework/Core/ModuleMacros.h"
#include "art/Framework/Principal/Event.h"
#include "art_root_io/TFileService.h"

#include "Offline/RecoDataProducts/inc/CaloDigi.hh"
#include "Offline/RecoDataProducts/inc/CaloHit.hh"
#include "Offline/RecoDataProducts/inc/CaloCluster.hh"

#include "TH1D.h"

#include <string>
#include <vector>



namespace mu2e {

  
  class DqmCal : public art::EDAnalyzer {
    
  public:

    struct Config 
    {
      using Name    = fhicl::Name;
      using Comment = fhicl::Comment;
      fhicl::Atom<art::InputTag> digiTag{Name("digiTag"),
          Comment("CaloDigi Collection"), art::InputTag()};
      fhicl::Atom<art::InputTag> clusterTag{Name("clusterTag"),
          Comment("CaloCluster Collection"), art::InputTag()};
    };
    typedef art::EDAnalyzer::Table<Config> Parameters;
  
       
    explicit DqmCal(const Parameters& conf);
    virtual ~DqmCal() { }
  
    virtual void beginJob();
    virtual void endJob() {};
    virtual void analyze(const art::Event& e);
  
  
  private:

    Config _conf;

    TH1D* _hVer;

    TH1D* _hdN;
    TH1D* _hdN2;
    TH1D* _hdI;
    TH1D* _hdt;
    TH1D* _hdt2;
    TH1D* _hdm;
    TH1D* _hdE;

    TH1D* _hcN;
    TH1D* _hct;
    TH1D* _hcs;
    TH1D* _hce0;
    TH1D* _hce1;
    TH1D* _hcR;
  
  };

  /********************************************************/

  DqmCal::DqmCal(const Parameters& conf) :
    art::EDAnalyzer(conf),
    _conf(conf())
  {
    mayConsume<CaloDigiCollection>(_conf.digiTag());
    mayConsume<CaloClusterCollection>(_conf.clusterTag());
  }

  /********************************************************/

  void DqmCal::beginJob(){

    art::ServiceHandle<art::TFileService> tfs;

    _hVer = tfs->make<TH1D>( "Ver", "Version Number", 101, -0.5, 100.0);

    if(!_conf.digiTag().empty()) {
      _hdN = tfs->make<TH1D>( "NDigis", "N Digis", 101, -0.5, 100.5);
      _hdN2= tfs->make<TH1D>( "NDigis2", "N Digis", 100, -0.5, 4999.5);
      _hdI = tfs->make<TH1D>( "SiPMID", "SiPM ID",100, 0.0, 3000.0);
      _hdt = tfs->make<TH1D>( "dt", "time", 100, 0.0, 2000.0);
      _hdt2= tfs->make<TH1D>( "dt2", "time", 100, 0.0, 100.0e3);
      _hdm = tfs->make<TH1D>( "Nwave", "N points in waveform",81, -0.5, 80.5);
      _hdE = tfs->make<TH1D>( "EMax", "E max in waveform",100, 0.0, 1500.0);
    }
    
    if(!_conf.clusterTag().empty()) {
      _hcN = tfs->make<TH1D>( "NClus", "N Clusters", 31, -0.05, 30.0);
      _hct = tfs->make<TH1D>( "ct", "time", 100, 0.0, 2000.0);
      _hcs = tfs->make<TH1D>( "size", "size", 51, -0.5, 50.5);
      _hce0 = tfs->make<TH1D>( "E0", "Energy disk0",50, 0.0, 200.0);
      _hce1 = tfs->make<TH1D>( "E1", "Energy disk1",50, 0.0, 200.0);
      _hcR = tfs->make<TH1D>( "R", "Radius",50, 340.0, 650.0);
    }
  }

  /********************************************************/

  void DqmCal::analyze(const art::Event& event) {

    _hVer->Fill(0.0);

    if(!_conf.digiTag().empty()) {
      auto digiH = event.getValidHandle<CaloDigiCollection>(_conf.digiTag());
      const auto& digis = *digiH;

      _hdN->Fill(digis.size());
      _hdN2->Fill(digis.size());
      for(auto dg : digis) {
        _hdI->Fill(dg.SiPMID());
        _hdt->Fill(dg.t0());
        _hdt2->Fill(dg.t0());
        _hdm->Fill(double(dg.waveform().size()));
        double emax = 0.0;
        for (auto e: dg.waveform()) { if(e>emax) emax = e; }
        _hdE->Fill(emax);
      }
    }

    if(!_conf.clusterTag().empty()) {
      auto clusterH = 
        event.getValidHandle<CaloClusterCollection>(_conf.clusterTag());
      const auto& clusters = *clusterH;

      _hcN->Fill(clusters.size()); 
      for(auto sp : clusters) {
        _hct->Fill(sp.time());
        _hcs->Fill(sp.size());
        if(sp.diskID()==0) {
          _hce0->Fill(sp.energyDep());
        } else {
          _hce1->Fill(sp.energyDep());
        }
        _hcR->Fill(sp.cog3Vector().perp());
      }
    }
  }

}

DEFINE_ART_MODULE(mu2e::DqmCal);
