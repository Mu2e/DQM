//
// analyzer module producing DQM histograms for Trk subsystem
//
//

#include "art/Framework/Core/EDAnalyzer.h"
#include "art/Framework/Core/ModuleMacros.h"
#include "art/Framework/Principal/Event.h"
#include "art_root_io/TFileService.h"

#include "Offline/RecoDataProducts/inc/KalSeed.hh"

#include "TH1D.h"

#include <string>
#include <vector>

namespace mu2e {

  class DqmTrk : public art::EDAnalyzer {

  public:
    struct Config {
      using Name = fhicl::Name;
      using Comment = fhicl::Comment;
      fhicl::Atom<art::InputTag> seedTag{
        Name("seedTag"), Comment("KalSeed Collection"), art::InputTag()};
    };
    typedef art::EDAnalyzer::Table<Config> Parameters;

    explicit DqmTrk(const Parameters &conf);
    virtual ~DqmTrk() {}

    virtual void beginJob();
    virtual void endJob(){};
    virtual void analyze(const art::Event &e);

  private:
    Config _conf;

    TH1D *_hVer;

    TH1D* _hN;
    TH1D* _hNStraw;
    TH1D* _hNSeg;
    TH1D* _hStatus;
    TH1D* _hflt0;
    TH1D* _ht0;
    TH1D* _hchi2;
    TH1D* _hhasCal;
    TH1D* _hfitCon;
    TH1D* _hfitConC;
    TH1D* _hfitConT;
    TH1D* _hp;
    TH1D* _hpC;
    TH1D* _hpT;
    TH1D* _hpce;
    TH1D* _hpcec;
    TH1D* _hpcep;
    TH1D* _hpe;
    TH1D* _hD0;
    TH1D* _hPhi0;
    TH1D* _hOmega;
    TH1D* _hZ0;
    TH1D* _hTan;
    TH1D* _hCuts;
    TH1D* _hCCdisk;
    TH1D* _hCCEoverP;
    TH1D* _hCCDt0;
    TH1D* _hCCDt;
    TH1D* _hCCDOCA;
    TH1D* _hCChlen;
    TH1D* _hCCtlen;
    TH1D* _hHDrift;
    TH1D* _hHDOCA;
    TH1D* _hHEDep;
    TH1D* _hHPanel;
    TH1D* _hSRadLen;
    TH1D* _hSRadLenSum;
  };

  /********************************************************/

  DqmTrk::DqmTrk(const Parameters &conf) : art::EDAnalyzer(conf), _conf(conf()) {

    mayConsume<KalSeedCollection>(_conf.seedTag());
  }

  /********************************************************/

  void DqmTrk::beginJob() {

    art::ServiceHandle<art::TFileService> tfs;

    _hVer = tfs->make<TH1D>("Ver", "Version Number", 101, -0.5, 100.0);

    _hN = tfs->make<TH1D>( "NSeed", "N KalSeed", 11, -0.5, 10.0);
    _hNStraw = tfs->make<TH1D>( "NHit", "N Hits", 101, -0.5, 100.0);
    _hNSeg = tfs->make<TH1D>( "NSeg", "N KalSegment", 21, -0.5, 20.0);
    _hStatus = tfs->make<TH1D>( "Status", "Status", 32, -0.5, 31.5);
    _hflt0 = tfs->make<TH1D>( "flt0", "flt0", 100, -1200.0, 1200.0);
    _ht0 = tfs->make<TH1D>( "t0", "t0", 100, 400.0, 1800.0);
    _hchi2 = tfs->make<TH1D>( "Chi2N", "Chi2/DOF", 100, 0.0, 20.0);
    _hhasCal = tfs->make<TH1D>( "hasCal", "CalCluster attached", 2, -0.5, 1.5);
    _hfitCon = tfs->make<TH1D>( "FitConn", "Fit CL", 100, 0.0, 1.0);
    _hfitConC = tfs->make<TH1D>( "FitConnC", "Fit CL CPR", 100, 0.0, 1.0);
    _hfitConT = tfs->make<TH1D>( "FitConnT", "Fit CL TPR", 100, 0.0, 1.0);
    _hp = tfs->make<TH1D>( "p", "p", 100, 0., 110.);
    _hpC = tfs->make<TH1D>( "pC", "p CPR", 100, 0., 110.);
    _hpT = tfs->make<TH1D>( "pT", "p TPR", 100, 0., 110.);
    _hpce = tfs->make<TH1D>( "pce", "p CE", 100, 95.0, 110.);
    _hpcec = tfs->make<TH1D>( "pcec", "p CE cuts", 100, 95.0, 110.);
    _hpcep = tfs->make<TH1D>( "pcep", "p CE+", 100, 82.0, 97.);
    _hpe = tfs->make<TH1D>( "pe", "p error", 100, 0.0, 1.0);
    _hD0 = tfs->make<TH1D>( "d0", "d0", 100, -100., 100.);
    _hPhi0 = tfs->make<TH1D>( "phi0", "phi0", 100, -M_PI, M_PI);
    _hOmega = tfs->make<TH1D>( "omega", "omega", 100, -0.02, 0.02);
    _hZ0 = tfs->make<TH1D>( "Z0", "Z0", 100, -1000.0, 1000.0);
    _hTan = tfs->make<TH1D>( "tanDip", "tanDip", 100, -1.8, 1.8);
    _hCuts = tfs->make<TH1D>( "Cuts", "Cut series", 8, 0.5, 8.5);
    _hCCdisk = tfs->make<TH1D>( "CCdisk","Calo Disk",2,-0.5,1.5);
    _hCCEoverP = tfs->make<TH1D>( "CCEoverP","Calo E Over Track P",100,0.0,1.5);
    _hCCDt0 = tfs->make<TH1D>( "CCDt0","Calo t0 - Track t0",100,-1.0,25.0);
    _hCCDt = tfs->make<TH1D>( "CCDt","Calo time residual",100,-5.0,5.0);
    _hCCDOCA = tfs->make<TH1D>("CCDOCA","Calo DOCA to Track",100,-100.0,100.0);
    _hCChlen = tfs->make<TH1D>("CChlen","Calo POCA Depth",100,-100.0,500.0);
    _hCCtlen = tfs->make<TH1D>("CCtlen","Calo POCA Track Length",100,1000.0,5000.0);
    _hHDrift = tfs->make<TH1D>("HDrift","Hit Drift Radius;drift radius (mm)",100,0.0,3.0);
    _hHDOCA = tfs->make<TH1D>("HDOCA","Hit Wire DOCA;DOCA (mm)",100,-3.0,3.0);
    _hHEDep = tfs->make<TH1D>("HEDep","Hit Energy Deposition;EDep (KeV)",100,0,5.0);
    _hHPanel = tfs->make<TH1D>( "HPanel", "Hit Unique Panel",216, -0.5, 215.5);
    _hSRadLen = tfs->make<TH1D>("SRadLen","Fractional Straw Radiation Length",100,0,1.0e-3);
    _hSRadLenSum = tfs->make<TH1D>("SRadLenSum","Sum Fractional Straw Radiation Length",100,0,0.04);
    int ibin=1;
    _hCuts->GetXaxis()->SetBinLabel(ibin++,"All seeds"); // bin 1, first visible
    _hCuts->GetXaxis()->SetBinLabel(ibin++,"KalmanOK"); // 3
    _hCuts->GetXaxis()->SetBinLabel(ibin++,"Fit Quality");
    _hCuts->GetXaxis()->SetBinLabel(ibin++,"Livegate");   // 5
    _hCuts->GetXaxis()->SetBinLabel(ibin++,"Reco pitch");
    _hCuts->GetXaxis()->SetBinLabel(ibin++,"Cosmic Rejection"); 
    _hCuts->GetXaxis()->SetBinLabel(ibin++,"Momentum window");  // 8
    _hCuts->SetMinimum(0.0);

  }

  /********************************************************/

  void DqmTrk::analyze(const art::Event &event) {

    _hVer->Fill(0.0);

    if (!_conf.seedTag().empty()) {
      auto seedH = event.getValidHandle<KalSeedCollection>(_conf.seedTag());
      const auto &seeds = *seedH;

      _hN->Fill(seeds.size());
      for (auto const &ks : seeds) {
        _hCuts->Fill(1.0);
        //************

        _hNStraw->Fill(ks.hits().size());
        _hNSeg->Fill(ks.segments().size());
        const TrkFitFlag& tff = ks.status();
        bool isCPR = tff.hasAllProperties(TrkFitFlag::CPRHelix);
        bool isTPR = tff.hasAllProperties(TrkFitFlag::TPRHelix);

        for(auto sn: tff.bitNames()) { 
          if(tff.hasAnyProperty(TrkFitFlag(sn.first))) 
            _hStatus->Fill(std::log2(sn.second)); 
        }

        _hflt0->Fill(ks.flt0());
        double t0 = ks.t0().t0();
        _ht0->Fill(t0);
        _hchi2->Fill(ks.chisquared()/std::max(1.0,double(ks.hits().size()-5)));
        int q = ks.hasCaloCluster();
        _hhasCal->Fill(q);
        _hfitCon->Fill(ks.fitConsistency());
        if(isCPR) _hfitConC->Fill(ks.fitConsistency());
        if(isTPR) _hfitConT->Fill(ks.fitConsistency());
        if( ks.segments().size()>0 ) {
          // first segment - in default config, this is front of tracker
          std::size_t i = 0;
          // middle segment - in default config, this is center of tracker
          //std::size_t i = ks.segments().size()/2;
          auto const& ss = ks.segments()[i]; //KalSegment
          auto const& h = ss.helix(); // HelixVal
          double p = ss.mom();
          _hp->Fill(ss.mom());
          if(isCPR) _hpC->Fill(ss.mom());
          if(isTPR) _hpT->Fill(ss.mom());
          _hpce->Fill(ss.mom());
          _hpcep->Fill(ss.mom());
          _hpe->Fill(ss.momerr());
          _hD0->Fill(h.d0());
          _hPhi0->Fill(h.phi0());
          double om = h.omega();
          _hOmega->Fill(h.omega());
          _hZ0->Fill(h.z0());
          double td = h.tanDip();
          _hTan->Fill(td);


          // fill the cut series
          double d0 = h.d0();
          bool d0cut = (d0<105 && d0>-80 && (d0+2/om)>450 && (d0+2/om)<680);

          if(tff.hasAllProperties(TrkFitFlag("KalmanOK"))) {
            _hCuts->Fill(2.0);
            if(ks.fitConsistency()>0.002) {
              _hCuts->Fill(3.0);
              if(t0>700.0 && t0<1695.0) {
                _hCuts->Fill(4.0);
                if(td>0.577&&td<1.0) {
                  _hCuts->Fill(5.0);
                  if(d0cut) {
                    _hCuts->Fill(6.0);
                    if(p>103.75 && p< 105.0) {
                      _hCuts->Fill(7.0);
                      _hpcec->Fill(ss.mom());
                    }
                  }
                }
              }
            }
          } // first of cuts, Kalman OK


        } // if seed has segments
        // associated cluster info
        if(ks.hasCaloCluster()){
          auto const& chs = ks.caloHit();
          _hCCdisk->Fill(chs.caloCluster()->diskID());
          // get momentum from the last segment
          auto const& ss = ks.segments().back(); //KalSegment
          double p = ss.mom();
          _hCCEoverP->Fill(ks.caloCluster()->energyDep()/p);
          _hCCDt0->Fill(chs.t0().t0()-t0);
          _hCCDt->Fill(chs.caloCluster()->time()-chs.t0().t0());
          _hCCDOCA->Fill(chs.clusterAxisDOCA());
          _hCChlen->Fill(chs.hitLen());
          _hCCtlen->Fill(chs.trkLen());
        }

        // Assocated TrkStrawHit info
        for(auto const& tshs : ks.hits()){
          if(tshs.flag().hasAllProperties(StrawHitFlag::active)){
            _hHDrift->Fill(tshs.driftRadius());
            _hHDOCA->Fill(tshs.wireDOCA());
            _hHEDep->Fill(1000*tshs.energyDep());
            _hHPanel->Fill(tshs.strawId().uniquePanel());
          }
        }
        // Assocated Material info
        float radlensum(0.0);
        for(auto const& ts : ks.straws()){
          if(ts.active()){
            _hSRadLen->Fill(ts.radLen());
            radlensum += ts.radLen();
          }
        }
        _hSRadLenSum->Fill(radlensum);

      } // end loop over seeds

    } // tag not empty
  } // end analyze

}

DEFINE_ART_MODULE(mu2e::DqmTrk);
