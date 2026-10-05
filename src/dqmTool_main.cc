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
  pcli.addSubcommand("print-files",
                     "list the files the metrics were derived from");
  pcli.addSwitch("print-files", "heading", "d", "heading", false,
                 "also print a header", "");

  pcli.addSubcommand("print-alarms", "list alarm episodes");
  pcli.addSwitch("print-alarms", "heading", "d", "heading", false,
                 "also print a header", "");
  pcli.addSwitch("print-alarms", "note", "n", "note", false,
                 "also print the note column.  It holds algo-internal\n"
                 "       json, whose commas and newlines make the csv\n"
                 "       awkward to parse, so it is off by default",
                 "");
  pcli.addSwitch("print-alarms", "live", "l", "live", false,
                 "only alarms still worth looking at, i.e. those not\n"
                 "       retired or deleted",
                 "");

  pcli.addSubcommand("print-causes",
                     "list the evidence for the alarm episodes");
  pcli.addSwitch("print-causes", "heading", "d", "heading", false,
                 "also print a header", "");
  pcli.addSwitch("print-causes", "numbers", "n", "numbers", false,
                 "also print the measurement each cause refers to", "");
  pcli.addSwitch("print-causes", "aid", "i", "aid", true,
                 "only causes of this one alarm episode");

  pcli.addSubcommand("print-numbers", "print all metrics numbers");
  pcli.addSwitch("print-numbers", "heading", "d", "heading", false,
                 "also print a header", "");
  pcli.addSwitch(
      "print-numbers", "source", "s", "source", true,
      "source for value either\n       csv like "
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
      "source for metric either\n       csv like "
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
                 "source for metric, csv like \"pass1,ele,file,0\" = "
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
  pcli.addSwitch("commit-value", "file", "f", "file", true,
                 "name of the file these metrics were derived from,\n"
                 "       recorded against this source and interval so an\n"
                 "       anomalous metric can be traced back to it (optional)");

  pcli.addSubcommand("commit-limit", "commit metric limit");
  pcli.addSwitch("commit-limit", "source", "s", "source", true,
                 "source for metric, csv like \"pass1,ele,file,0\" = "
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

  pcli.addSubcommand("commit-alarm", "commit an alarm finding");
  pcli.addSwitch("commit-alarm", "algo", "a", "algo", true,
                 "name of the algorithm, e.g. \"limits\"");
  pcli.addSwitch("commit-alarm", "config", "c", "config", true,
                 "label for the algorithm's configuration,\n"
                 "       e.g. \"crv-tight-0\"");
  pcli.addSwitch("commit-alarm", "subject", "j", "subject", true,
                 "what the algorithm found, from its own short\n"
                 "       vocabulary, e.g. \"gain_shifted\"");
  pcli.addSwitch("commit-alarm", "sid", "s", "sid", true,
                 "the source examined");
  pcli.addSwitch("commit-alarm", "cause", "u", "cause", true,
                 "evidence for the finding, either a csv string like\n"
                 "       \"200,11,2\" = iid,vid,level\n"
                 "       or \"200,2\" = iid,level for a global test\n"
                 "       or a filespec of a text file of csv strings");
  pcli.addSwitch("commit-alarm", "note", "n", "note", true,
                 "algo-internal json, not queryable (optional)");

  pcli.addSubcommand("alarm-status", "set an alarm episode's status");
  pcli.addSwitch("alarm-status", "aid", "i", "aid", true,
                 "the alarm episode to update");
  pcli.addSwitch("alarm-status", "status", "s", "status", true,
                 mu2e::DqmAlarm::statusList() +
                     "\n       retired and deleted also close the episode");

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
  } else if (pcli.subcommand() == "print-files") {
    rc = tool.printFiles(pcli.getBool("print-files", "heading"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "print-alarms") {
    rc = tool.printAlarms(pcli.getBool("print-alarms", "heading"),
                          pcli.getBool("print-alarms", "note"),
                          pcli.getBool("print-alarms", "live"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "print-causes") {
    rc = tool.printCauses(pcli.getBool("print-causes", "heading"),
                          pcli.getBool("print-causes", "numbers"),
                          pcli.getString("print-causes", "aid"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "print-numbers") {
    rc = tool.printNumbers("numbers", pcli.getBool("print-numbers", "heading"),
                           pcli.getString("print-numbers", "source"),
                           pcli.getString("print-numbers", "value"),
                           pcli.getBool("print-numbers", "expand"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "print-limits") {
    rc = tool.printNumbers("limits", pcli.getBool("print-limits", "heading"),
                           pcli.getString("print-limits", "source"),
                           pcli.getString("print-limits", "value"),
                           pcli.getBool("print-limits", "expand"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "commit-value") {
    rc = tool.commitValue(pcli.getString("commit-value", "source"),
                          pcli.getString("commit-value", "runs"),
                          pcli.getString("commit-value", "start"),
                          pcli.getString("commit-value", "end"),
                          pcli.getString("commit-value", "value"),
                          pcli.getString("commit-value", "file"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "commit-limit") {
    rc = tool.commitLimit(pcli.getString("commit-limit", "source"),
                          pcli.getString("commit-limit", "runs"),
                          pcli.getString("commit-limit", "start"),
                          pcli.getString("commit-limit", "end"),
                          pcli.getString("commit-limit", "value"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "commit-alarm") {
    rc = tool.commitAlarm(pcli.getString("commit-alarm", "algo"),
                          pcli.getString("commit-alarm", "config"),
                          pcli.getString("commit-alarm", "subject"),
                          pcli.getString("commit-alarm", "sid"),
                          pcli.getString("commit-alarm", "cause"),
                          pcli.getString("commit-alarm", "note"));
    if (rc != 0) return rc;
  } else if (pcli.subcommand() == "alarm-status") {
    rc = tool.alarmStatus(pcli.getString("alarm-status", "aid"),
                          pcli.getString("alarm-status", "status"));
    if (rc != 0) return rc;
  } else {
    std::cout << "Error - unknown command: " << pcli.subcommand() << std::endl;
  }

  std::cout << tool.getResult();
  return 0;
}
