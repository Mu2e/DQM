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

#include "TH1F.h"

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

    Config conf_;

    TH1D* hVer_;

    TH1D* hdN_;
    TH1D* hdN2_;
    TH1D* hdI_;
    TH1D* hdt_;
    TH1D* hdt2_;
    TH1D* hdm_;
    TH1D* hdE_;

    TH1D* hcN_;
    TH1D* hct_;
    TH1D* hcs_;
    TH1D* hce0_;
    TH1D* hce1_;
    TH1D* hcR_;
  
  };

  /********************************************************/

  DqmCal::DqmCal(const Parameters& conf) :
    art::EDAnalyzer(conf),
    conf_(conf())
  {
    mayConsume<CaloDigiCollection>(conf_.digiTag());
    mayConsume<CaloClusterCollection>(conf_.clusterTag());
  }

  /********************************************************/

  void DqmCal::beginJob(){

    art::ServiceHandle<art::TFileService> tfs;

    hVer_ = tfs->make<TH1D>( "Ver", "Version Number", 101, -0.5, 100.0);

    if(!conf_.digiTag().empty()) {
      hdN_ = tfs->make<TH1D>( "NDigis", "N Digis", 101, -0.5, 100.5);
      hdN2_= tfs->make<TH1D>( "NDigis2", "N Digis", 100, -0.5, 4999.5);
      hdI_ = tfs->make<TH1D>( "SiPMID", "SiPM ID",100, 0.0, 3000.0);
      hdt_ = tfs->make<TH1D>( "dt", "time", 100, 0.0, 2000.0);
      hdt2_ = tfs->make<TH1D>( "dt2", "time", 100, 0.0, 100.0e3);
      hdm_ = tfs->make<TH1D>( "Nwave", "N points in waveform",81, -0.5, 80.5);
      hdE_ = tfs->make<TH1D>( "EMax", "E max in waveform",100, 0.0, 1500.0);
    }
    
    if(!conf_.clusterTag().empty()) {
      hcN_ = tfs->make<TH1D>( "NClus", "N Clusters", 31, -0.05, 30.0);
      hct_ = tfs->make<TH1D>( "ct", "time", 100, 0.0, 2000.0);
      hcs_ = tfs->make<TH1D>( "size", "size", 51, -0.5, 50.5);
      hce0_ = tfs->make<TH1D>( "E0", "Energy disk0",50, 0.0, 200.0);
      hce1_ = tfs->make<TH1D>( "E1", "Energy disk1",50, 0.0, 200.0);
      hcR_ = tfs->make<TH1D>( "R", "Radius",50, 340.0, 650.0);
    }
  }

  /********************************************************/

  void DqmCal::analyze(const art::Event& event) {

    hVer_->Fill(0.0);

    if(!conf_.digiTag().empty()) {
      auto digiH = event.getValidHandle<CaloDigiCollection>(conf_.digiTag());
      const auto& digis = *digiH;

      hdN_->Fill(digis.size());
      hdN2_->Fill(digis.size());
      for(auto dg : digis) {
        hdI_->Fill(dg.SiPMID());
        hdt_->Fill(dg.t0());
        hdt2_->Fill(dg.t0());
        hdm_->Fill(double(dg.waveform().size()));
        double emax = 0.0;
        for (auto e: dg.waveform()) { if(e>emax) emax = e; }
        hdE_->Fill(emax);
      }
    }

    if(!conf_.clusterTag().empty()) {
      auto clusterH = 
        event.getValidHandle<CaloClusterCollection>(conf_.clusterTag());
      const auto& clusters = *clusterH;

      hcN_->Fill(clusters.size()); 
      for(auto sp : clusters) {
        hct_->Fill(sp.time());
        hcs_->Fill(sp.size());
        if(sp.diskID()==0) {
          hce0_->Fill(sp.energyDep());
        } else {
          hce1_->Fill(sp.energyDep());
        }
        hcR_->Fill(sp.cog3Vector().perp());
      }
    }
  }

}

DEFINE_ART_MODULE(mu2e::DqmCal);
