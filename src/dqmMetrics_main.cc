
// read a DQM histogram file and write out DQM metrics

#include "DQM/inc/DqmMetrics.hh"
#include "TFile.h"
#include <string>
#include <vector>
#include <fstream>

int main(int argc, char**argv) {

  std::vector<std::string> words;
  for(size_t i=1; i<size_t(argc);++i) {
    words.emplace_back(argv[i]);
  }

  TFile file(words[0].c_str(),"READONLY");

  mu2e::DqmMetrics metrics(file);
  metrics.process();

  std::ofstream mfile("dqmMetrics.txt");
  metrics.write(mfile);
  mfile.close();

  return 0;
}

