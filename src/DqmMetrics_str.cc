
#include "DQM/inc/DqmMetrics.hh"
#include "TH1D.h"
#include <iomanip>
#include <iostream>

int mu2e::DqmMetrics::str(TDirectory& dir) {
  TH1D* hh;

  hh = (TH1D*)dir.Get("Ver");
  addMean(hh, "str", "gen", "version", 20, 0);

  hh = (TH1D*)dir.Get("NDigi2");
  addMean(hh, "str", "digi", "meanN", 20, 2);

  hh = (TH1D*)dir.Get("TOT");
  addMean(hh, "str", "digi", "meanTOT", 20, 2);
  addRMS(hh, "str", "digi", "rmsTOT", 20, 2);

  hh = (TH1D*)dir.Get("PMP");
  addMean(hh, "str", "digi", "meanPMP", 20, 2);

  hh = (TH1D*)dir.Get("ADC");
  addMean(hh, "str", "digi", "meanADC", 20, 2);

  return 0;
}
