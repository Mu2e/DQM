
#include "DQM/inc/DqmTool.hh"
#include <iostream>
#include <string>
#include <vector>

int main(int argc, char** argv) {
  std::vector<std::string> words;
  for (size_t i = 1; i < size_t(argc); ++i) {
    words.emplace_back(argv[i]);
  }

  mu2e::DqmTool tool;
  int rc = tool.run(words);
  std::cout << tool.getResult();
  return rc;
}
