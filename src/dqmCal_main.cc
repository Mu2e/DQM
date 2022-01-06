
// read a DQM histogram file and write out DQM metrics

#include <string>
#include <vector>
#include <iostream>
#include <iomanip>
#include "DQM/inc/DqmValue.hh"
#include "TFile.h"
#include "TH1D.h"



int main(int argc, char**argv) {

  std::vector<std::string> words;
  for(size_t i=1; i<size_t(argc);++i) {
    words.emplace_back(argv[i]);
  }

  TFile file(words[0].c_str(),"READONLY");

  // quit if the file does not contain cal results
  if(file.GetDirectory("dqmCal") == nullptr) return 0;



  TH1D* hh;
  constexpr int cOK   = mu2e::DqmValue::codeValues::OK;
  constexpr int cmiss = mu2e::DqmValue::codeValues::missing;
  constexpr int cstat = mu2e::DqmValue::codeValues::lowStats;

  hh = (TH1D*) file.GetObjectUnchecked("dqmCal/Ver");
  if(hh==nullptr) {
    std::cout << "cal,gen,version,0.0,0.0," << cmiss << std::endl;
  } else if(hh->GetEntries()<=0) {
    std::cout << "cal,gen,version,0.0,0.0," << cstat << std::endl;
  } else {
    std::cout << "cal,gen,version,"<< int(hh->GetMean())
              << ",0.0,0" << std::endl;
  }

  hh = (TH1D*) file.GetObjectUnchecked("dqmCal/NDigis");

  if(hh==nullptr) {
    std::cout << "cal,digi,meanN,0.0,0.0," << cmiss << std::endl;
    std::cout << "cal,digi,fracZero,0.0,0.0," << cmiss << std::endl;
  } else if(hh->GetEntries()<20) {
    std::cout << "cal,digi,meanN,0.0,0.0," << cstat << std::endl;
    std::cout << "cal,digi,fracZero,0.0,0.0," << cstat << std::endl;
  } else {
    std::cout << "cal,digi,meanN," 
              << std::fixed 
              << std::setprecision(2) << hh->GetMean() << ","
              << std::setprecision(2) << hh->GetMeanError() << ","
              << cOK << std::endl;

    float x = hh->GetBinContent(1)/hh->GetEntries();
    float s = (hh->GetEntries()>0? sqrt(x*(1-x)/hh->GetEntries()):0.0);
    std::cout << "cal,digi,fracZero," 
              << std::fixed 
              << std::setprecision(3) << x << ","
              << std::setprecision(3) << s << ","
              << cOK << std::endl;
  }

  hh = (TH1D*) file.GetObjectUnchecked("dqmCal/EMax");
  if(hh==nullptr) {
    std::cout << "cal,digi,meanEMax,0.0,0.0," << cmiss << std::endl;
  } else if(hh->GetEntries()<=20) {
    std::cout << "cal,digi,meanEMax,0.0,0.0," << cstat << std::endl;
  } else {
    std::cout << "cal,digi,meanEMax,"
              << std::fixed 
              << std::setprecision(2) << hh->GetMean() << ","
              << std::setprecision(2) << hh->GetMeanError() << ","
              << cOK << std::endl;
  }


  hh = (TH1D*) file.GetObjectUnchecked("dqmCal/E0");
  if(hh==nullptr) {
    std::cout << "cal,cluster,meanE0,0.0,0.0," << cmiss << std::endl;
  } else if(hh->GetEntries()<=20) {
    std::cout << "cal,cluster,meanE0,0.0,0.0," << cstat << std::endl;
  } else {
    std::cout << "cal,cluster,meanE0,"
              << std::fixed 
              << std::setprecision(2) << hh->GetMean() << ","
              << std::setprecision(2) << hh->GetMeanError() << ","
              << cOK << std::endl;
  }


  hh = (TH1D*) file.GetObjectUnchecked("dqmCal/E1");
  if(hh==nullptr) {
    std::cout << "cal,cluster,meanE1,0.0,0.0," << cmiss << std::endl;
  } else if(hh->GetEntries()<=20) {
    std::cout << "cal,cluster,meanE1,0.0,0.0," << cstat << std::endl;
  } else {
    std::cout << "cal,cluster,meanE1,"
              << std::fixed 
              << std::setprecision(2) << hh->GetMean() << ","
              << std::setprecision(2) << hh->GetMeanError() << ","
              << cOK << std::endl;
  }


  return 0;
}

