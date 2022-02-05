#ifndef DQM_DqmMetrics_hh
#define DQM_DqmMetrics_hh

//
// extract the numerical metrics from a histogram file
//

#include "DQM/inc/DqmValue.hh"
#include "TFile.h"
#include "TH1D.h"
#include <string>
#include <iostream>

namespace mu2e {

  class DqmMetrics {
  public:

    DqmMetrics(TFile& file):_tfile(file) { }
    int process();
    int write(std::ostream& os=std::cout);

    
  private:

    int cal(TDirectory& dir);
    int str(TDirectory& dir);
    int trk(TDirectory& dir, const char* coll);
    int crv(TDirectory& dir);
    int addMean(TH1D const* hh, const char* group, 
                const char* subgroup, const char* name,
                int minStats=20, int precision=2);
    int addRMS(TH1D const* hh, const char* group, 
               const char* subgroup, const char* name,
               int minStats=20, int precision=2);
    int addBinFrac(TH1D const* hh, const char* group, 
                    const char* subgroup, const char* name,
                    int bin, int minStats=1, int precision=2);
    int addVar(const char* group, const char* subgroup, const char* name,
               float value, float sigma, int code, int precision=2);

    TFile& _tfile;
    DqmValueCollection _vcoll;

    static constexpr int cOK   = mu2e::DqmValue::codeValues::OK;
    static constexpr int cmiss = mu2e::DqmValue::codeValues::missing;
    static constexpr int cstat = mu2e::DqmValue::codeValues::lowStats;
    static constexpr int cerror = mu2e::DqmValue::codeValues::error;

  };
  
}

#endif
