
#include "DQM/inc/DqmMetrics.hh"
#include <iostream>
#include <iomanip>
#include "TH1D.h"


int mu2e::DqmMetrics::crv(TDirectory& dir) {

  TH1D* hh;

  hh = (TH1D*) dir.Get("Ver");
  addMean(hh,"crv","gen","version",20,0);

  hh = (TH1D*) dir.Get("NDigis2");
  addMean(hh,"crv","digi","meanN",20,2);

  hh = (TH1D*) dir.Get("ADC");
  addMean(hh,"crv","digi","meanADC",20,2);
  addRMS(hh,"crv","digi","rmsADC",20,2);

  hh = (TH1D*) dir.Get("NPulses2");
  addMean(hh,"crv","pulse","meanN",20,2);

  hh = (TH1D*) dir.Get("PEr");
  addMean(hh,"crv","pulse","meanPE",20,2);

  hh = (TH1D*) dir.Get("chi2");
  addMean(hh,"crv","pulse","meanChi2",20,2);
  addRMS(hh,"crv","pulse","rmsChi2",20,2);

  hh = (TH1D*) dir.Get("NClus");
  addMean(hh,"crv","clus","meanN",20,2);

  hh = (TH1D*) dir.Get("PEc");
  addMean(hh,"crv","clus","meanPE",20,2);
  addRMS(hh,"crv","clus","rmsPE",20,2);

  hh = (TH1D*) dir.Get("NPc");
  addMean(hh,"crv","clus","nPulse",20,2);

  return 0;

}
