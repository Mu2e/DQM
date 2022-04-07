
#include "DQM/inc/DqmMetrics.hh"
#include "TH1D.h"
#include <iomanip>
#include <iostream>

int mu2e::DqmMetrics::trk(TDirectory& dir, const char* coll) {
  TH1D* hh;

  hh = (TH1D*)dir.Get("Ver");
  addMean(hh, "trk", coll, "version", 20, 0);

  hh = (TH1D*)dir.Get("NSeed");
  addMean(hh, "trk", coll, "Nseed", 20, 4);

  hh = (TH1D*)dir.Get("NHit");
  addMean(hh, "trk", coll, "NHit", 20, 2);

  hh = (TH1D*)dir.Get("Chi2N");
  addMean(hh, "trk", coll, "Chi2N", 20, 2);

  hh = (TH1D*)dir.Get("hasCal");
  addMean(hh, "trk", coll, "hasCal", 20, 2);

  return 0;
}
