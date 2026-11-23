
// read a DQM histogram file and write out DQM metrics

#include "DQM/inc/DqmMetrics.hh"
#include "TFile.h"
#include <fstream>
#include <iostream>
#include <string>

namespace {
// the metrics go here, in the working directory, for a later
// dqmTool commit-value --value dqmMetrics.txt
const char* const outName = "dqmMetrics.txt";

// On any failure, say what went wrong and exit non-zero.  An empty file
// with status 0 used to let a chained commit-value record the interval
// with no numbers, so the failure looked like "no data".  Any file
// already in the working directory is left alone: it may be a previous
// run's good output, and this tool does not own what it did not write.
int fail(const std::string& why) {
  std::cerr << "ERROR - dqmMetrics: " << why << std::endl;
  return 1;
}
}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    std::cerr << "usage: dqmMetrics <DQM histogram file>\n"
              << "  reads the histograms and writes their metrics to "
              << outName << std::endl;
    return fail("no histogram file given");
  }
  std::string input(argv[1]);

  TFile file(input.c_str(), "READONLY");
  if (file.IsZombie() || !file.IsOpen()) {
    return fail("could not read " + input + " as a ROOT file");
  }

  mu2e::DqmMetrics metrics(file);
  metrics.process();

  std::ofstream mfile(outName);
  if (!mfile) return fail(std::string("could not open ") + outName);
  metrics.write(mfile);
  mfile.close();
  if (!mfile) return fail(std::string("could not write ") + outName);

  return 0;
}
