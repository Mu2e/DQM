
#include "DQM/inc/DqmMetrics.hh"
#include "TH1D.h"
#include <iomanip>
#include <iostream>

int mu2e::DqmMetrics::cal(TDirectory& dir) {
  TH1D* hh;

  hh = (TH1D*)dir.Get("Ver");
  addMean(hh, "cal", "gen", "version", 20, 0);

  hh = (TH1D*)dir.Get("NDigis");
  addMean(hh, "cal", "digi", "meanN", 20, 2);
  addBinFrac(hh, "cal", "digi", "fZeroN", 1, 20, 2);

  hh = (TH1D*)dir.GetObjectUnchecked("EMax");
  addMean(hh, "cal", "digi", "meanEMax", 20, 2);

  hh = (TH1D*)dir.GetObjectUnchecked("NClus");
  addMean(hh, "cal", "clus", "meanN", 20, 2);

  hh = (TH1D*)dir.GetObjectUnchecked("size");
  addMean(hh, "cal", "clus", "size", 20, 2);

  hh = (TH1D*)dir.GetObjectUnchecked("E0");
  addMean(hh, "cal", "clus", "meanE0", 20, 2);

  hh = (TH1D*)dir.GetObjectUnchecked("E1");
  addMean(hh, "cal", "clus", "meanE1", 20, 2);

  return 0;
}
