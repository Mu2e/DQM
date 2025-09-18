#include "DQM/inc/DqmTool.hh"
#include "Offline/GeneralUtilities/inc/ParseCLI.hh"
#include <algorithm>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

typedef std::vector<std::string> StrVec;


// *********************************************************
int main(int argc, char** argv) {

  mu2e::ParseCLI pcli("read and write to the DQM database");
  pcli.addSubcommand("", "");
  pcli.addSwitch("", "verbose", "v", "verbose", false, "increase verbosity", "",
                 true);
  pcli.addSubcommand("print-sources", "list all sources of metrics");
  pcli.addSwitch("print-sources", "heading", "d", "heading", false,
                 "also print a header", "");
  pcli.addSubcommand("print-intervals",
                     "list all time and run range intervals of metrics");
  pcli.addSwitch("print-intervals", "heading", "d", "heading", false,
                 "also print a header", "");
  pcli.addSubcommand("print-values", "list all the names of the metrics");
  pcli.addSwitch("print-values", "heading", "d", "heading", false,
                 "also print a header", "");

  pcli.addSubcommand("print-numbers", "print all metrics numbers");
  pcli.addSwitch("print-numbers", "heading", "d", "heading", false,
                 "also print a header", "");
  pcli.addSwitch(
      "print-numbers", "source", "s", "source", true,
      "source for value either\n       name of the DQM histogram "
      "source file\n       or csv like "
      "\"pass1,ele,file,0\" = process,stream,aggregation,version\n    "
      "   or an SID");
  pcli.addSwitch(
      "print-numbers", "value", "v", "value", true,
      "name of the metric, either\n       csv like \"cal,disk0,meanE\" = "
      "group,subgroup,name\n       or VID");
  pcli.addSwitch("print-numbers", "expand", "e", "expand", false,
                 "expand the id values into text");

  pcli.addSubcommand("print-limits", "print all metrics limits");
  pcli.addSwitch("print-limits", "heading", "d", "heading", false,
                 "also print a header", "");
  pcli.addSwitch(
      "print-limits", "source", "s", "source", true,
      "source for metric either\n       name of the DQM histogram "
      "source file\n       or csv like "
      "\"pass1,ele,file,0\" = process,stream,aggregation,version\n    "
      "   or an SID");
  pcli.addSwitch(
      "print-limits", "value", "v", "value", true,
      "name of the metric, either\n       csv like \"cal,disk0,meanE\" = "
      "group,subgroup,name\n       or VID");
  pcli.addSwitch("print-limits", "expand", "e", "expand", false,
                 "expand the id values into text");

  pcli.addSubcommand("commit-value", "commit metric value");
  pcli.addSwitch("commit-value", "source", "s", "source", true,
                 "source for metric either\n       name of the DQM histogram "
                 "source file\n       or csv like \"pass1,ele,file,0\" = "
                 "process,stream,aggregation,version");
  pcli.addSwitch(
      "commit-value", "runs", "r", "runs", true,
      "runs for an interval\n       like \"1100:0-1101:999999\" (optional)");
  pcli.addSwitch(
      "commit-value", "start", "t", "start", true,
      "start of an interval\n       like \"2022-01-01T14:00:00\" (optional)");
  pcli.addSwitch(
      "commit-value", "end", "e", "end", true,
      "end of an interval\n       like \"2022-01-01T14:00:00\" (optional)");
  pcli.addSwitch("commit-value", "value", "v", "value", true,
                 "either a csv string like\n       "
                 "\"cal,disk0,meanE,20.0,0.1,0\"  = "
                 "group,subgroup,name,val,sigma,code\n       or a filespec of "
                 "a text file containing csv strings");

  pcli.addSubcommand("commit-limit", "commit metric limit");
  pcli.addSwitch("commit-limit", "source", "s", "source", true,
                 "source for metric either\n       name of the DQM histogram "
                 "source file\n       or csv like \"pass1,ele,file,0\" = "
                 "process,stream,aggregation,version");
  pcli.addSwitch(
      "commit-limit", "runs", "r", "runs", true,
      "runs for an interval\n       like \"1100:0-1101:999999\" (optional)");
  pcli.addSwitch(
      "commit-limit", "start", "t", "start", true,
      "start of an interval\n       like \"2022-01-01T14:00:00\" (optional)");
  pcli.addSwitch(
      "commit-limit", "end", "e", "end", true,
      "end of an interval\n       like \"2022-01-01T14:00:00\" (optional)");
  pcli.addSwitch(
      "commit-limit", "value", "v", "value", true,
      "name of the metric, either\n       csv like \"cal,disk0,meanE\" = "
      "group,subgroup,name\n       or VID");

  int rc = pcli.setArgs(argc, argv);
  if (rc != 0) return rc;

  mu2e::DqmTool tool;
  tool.setVerbose(pcli.getCount("", "verbose"));
  tool.init();

  if (pcli.subcommand() == "print-sources") {
    rc = tool.printSources(pcli.getBool("print-sources", "heading"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "print-intervals") {
    rc = tool.printIntervals(pcli.getBool("print-intervals", "heading"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "print-values") {
    rc = tool.printValues(pcli.getBool("print-values", "heading"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "print-numbers") {
    rc = tool.printNumbers("numbers", pcli.getBool("print-numbers", "heading"),
                           pcli.getString("print-numbers", "source"),
                           pcli.getString("print-numbers", "value"),
                           pcli.getBool("print-numbers", "expand"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "print-limits") {
    rc = tool.printNumbers("limits", pcli.getBool("print-numbers", "heading"),
                           pcli.getString("print-numbers", "source"),
                           pcli.getString("print-numbers", "value"),
                           pcli.getBool("print-numbers", "expand"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "commit-value") {
    rc = tool.commitValue(pcli.getString("commit-value", "source"),
                          pcli.getString("commit-value", "runs"),
                          pcli.getString("commit-value", "start"),
                          pcli.getString("commit-value", "end"),
                          pcli.getString("commit-value", "value"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "commit-limit") {
    rc = tool.commitLimit(pcli.getString("commit-limit", "source"),
                          pcli.getString("commit-limit", "runs"),
                          pcli.getString("commit-limit", "start"),
                          pcli.getString("commit-limit", "end"),
                          pcli.getString("commit-limit", "value"));
    if (rc != 0) return rc;
  } else {
    std::cout << "Error - unknown command: " << pcli.subcommand() << std::endl;
  }

  std::cout << tool.getResult();
  return 0;
}
