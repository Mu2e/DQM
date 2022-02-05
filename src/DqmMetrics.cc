#include "DQM/inc/DqmMetrics.hh"
#include "TH1D.h"
#include "TDirectory.h"
#include <sstream>
#include <iomanip>


//***********************************************************

int mu2e::DqmMetrics::process() {

  _tfile.ReadAll();
  for(auto const& obj : *(_tfile.GetList()) ) {
    TString sdir = obj->GetName();
    if(sdir.EqualTo("dqmCal")) {
      _tfile.cd(sdir);
      cal(*gDirectory);
    } else if(sdir.EqualTo("dqmStr")) {
      _tfile.cd(sdir);
      str(*gDirectory);
    } else if(sdir.Contains("dqmTrk")) {
      _tfile.cd(sdir);
      trk(*gDirectory,sdir(6,6).Data());
    } else if(sdir.EqualTo("dqmCrv")) {
      _tfile.cd(sdir);
      crv(*gDirectory);
    }
  }

  return 0;
}

//***********************************************************

int mu2e::DqmMetrics::write(std::ostream& os) {
  for(auto const& vv: _vcoll) {
    os << vv.csv() << "\n";
  }
  return 0;
}


//***********************************************************

int mu2e::DqmMetrics::addMean(TH1D const* hh,
                              const char* group, const char* subgroup,
                              const char* name,
                              int minStats, int precision) {

  if(hh==nullptr) {
    _vcoll.emplace_back(group,subgroup,name,"0.0","0.0",cmiss);
  } else if(hh->GetEntries()<minStats) {
    _vcoll.emplace_back(group,subgroup,name,"0.0","0.0",cstat);
  } else {
    std::ostringstream vv;
    vv << std::fixed << std::setprecision(precision) << hh->GetMean();
    std::ostringstream ss;
    ss << std::fixed << std::setprecision(precision) << hh->GetMeanError();
    _vcoll.emplace_back(group,subgroup,name,vv.str(),ss.str(),cOK);
  }
  return 0;
}


//***********************************************************

int mu2e::DqmMetrics::addRMS(TH1D const* hh,
                             const char* group, const char* subgroup,
                             const char* name,
                             int minStats, int precision) {

  if(hh==nullptr) {
    _vcoll.emplace_back(group,subgroup,name,"0.0","0.0",cmiss);
  } else if(hh->GetEntries()<minStats) {
    _vcoll.emplace_back(group,subgroup,name,"0.0","0.0",cstat);
  } else {
    std::ostringstream vv;
    vv << std::fixed << std::setprecision(precision) << hh->GetRMS();
    std::ostringstream ss;
    ss << std::fixed << std::setprecision(precision) << hh->GetRMSError();
    _vcoll.emplace_back(group,subgroup,name,vv.str(),ss.str(),cOK);
  }
  return 0;
}


//***********************************************************

int mu2e::DqmMetrics::addBinFrac(TH1D const* hh, const char* group, 
                                 const char* subgroup, const char* name,
                                 int bin,int minStats, int precision) {
  if(hh==nullptr) {
    _vcoll.emplace_back(group,subgroup,name,"0.0","0.0",cmiss);
  } else if(hh->GetEntries()<minStats) {
    _vcoll.emplace_back(group,subgroup,name,"0.0","0.0",cstat);
  } else {
    float x = hh->GetBinContent(bin)/hh->GetEntries();
    float s = sqrt(x*(1-x)/hh->GetEntries());
    std::ostringstream vv;
    vv << std::fixed << std::setprecision(precision) << x;
    std::ostringstream ss;
    ss << std::fixed << std::setprecision(precision) << s;
    _vcoll.emplace_back(group,subgroup,name,vv.str(),ss.str(),cOK);
  }

  return 0;
}

//***********************************************************

int mu2e::DqmMetrics::addVar(const char* group, const char* subgroup, 
                             const char* name,
                             float value, float sigma, int code, 
                             int precision) {

  std::ostringstream vv;
  vv << std::fixed << std::setprecision(precision) << value;
  std::ostringstream ss;
  ss << std::fixed << std::setprecision(precision) << sigma;
  _vcoll.emplace_back(group,subgroup,name,vv.str(),ss.str(),code);
  
  return 0;
}

