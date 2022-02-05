
#include <iostream>
#include <fstream>
#include "DQM/inc/DqmTool.hh"
#include "DQM/inc/DqmTime.hh"
#include "Offline/DbService/inc/DbIdList.hh"
#include <boost/algorithm/string.hpp>
#include <boost/algorithm/string/classification.hpp>
#include <boost/algorithm/string/split.hpp>
#include <boost/tokenizer.hpp>
#include <string>
#include <map>

mu2e::DqmTool::DqmTool() : _verbose(0) {}


//***********************************************************

int mu2e::DqmTool::run(const std::string &arg) { 
  StringVec args = splitString(arg,' ');
  return run(args); 
}

//***********************************************************

int mu2e::DqmTool::run(const StringVec &args) {

  _args = args;

  int rc;
  rc = parseGeneral();
  if (rc != 0) return rc;

  init();


  if (_action == "commit-value") {
    rc = commitValue();
  } else if (_action == "print-sources") {
    rc = printSources();
  } else if (_action == "print-intervals") {
    rc = printIntervals();
  } else if (_action == "print-values") {
    rc = printValues();
  } else if (_action == "print-numbers") {
    rc = printNumbers();
  } else {
    std::cout << "Error - unknown action: " << _action << std::endl;
    return 1;
  }

  return rc;
}


//***********************************************************

int mu2e::DqmTool::init() {

  DbIdList idList; // read the connections info file
  DbId id = idList.getDbId("mu2e_dqm_prd");

  _reader.setDbId(id);
  _reader.setVerbose(_verbose);
  _reader.setTimeVerbose(_verbose);

  _sql.setDbId(id);
  _sql.setVerbose(_verbose);

  return 0;
}


//***********************************************************

int mu2e::DqmTool::commitValue() {

  int rc;
  _argMap["source"] = "";
  _argMap["runs"] = "";
  _argMap["start"] = "";
  _argMap["end"] = "";
  _argMap["value"] = "";

  rc = parseAction();
  if(rc) return rc;

  // **** interpret source (process/stream/aggregation/version)

  std::string ss = _argMap["source"];
  if(ss.empty()) {
    std::cout << "ERROR - commit-value requires --source" << std::endl;
    return 1;
  }

  DqmSource source;
  std::string runs;
  // take the ss string and parse it into proces/stream, etc, fields, 
  // whether it is a file name with a standard form, or csv string
  // runs will be filled if the aources was a file with a runs type sequencer
  rc = parseSource(source,runs,ss);
  if(rc!=0) return rc; // the method will print any errors

  // **** interpret time interval

  std::string rn = _argMap["runs"];
  std::string st = _argMap["start"];
  std::string en = _argMap["end"];

  // if we got a start run from the file name, and the
  // expclicit run range parameter does not overwrite it, then use it
  if (rn.empty() && !runs.empty()) rn = runs;

  // must have some time or run restriction
  if (rn.empty() && st.empty()) {
    std::cout << "ERROR - commit-source requires one of --runs, --start, or a file name with a run_subrun sequencer" << std::endl;
    return 1;
  }
  if (st.empty() && !en.empty()) {
    std::cout << "ERROR - commit-source --end is non-empty but --start is empty (opposite is allowed)" << std::endl;
    return 1;
  }
  // if there is a start time, but no end time, then set end to start
  if(!st.empty() && en.empty()) en = st;
  // if no times, set to irrelevent (there should still be a run range)
  if(st.empty() && en.empty()) {
    st = "-infinity";
    en = "-infinity";
  }
  // if no run info given, set start and stop to 0
  if(rn.empty()) rn="EMPTY";

  // container for time
  DqmTime time(rn,st,en);


  // **** interpret values
  std::string vv = _argMap["value"];

  if( vv.empty() ) {
    std::cout << "ERROR - commit-value requires --value" << std::endl;
    return 1;
  }

  if(_verbose>2) {
    std::cout <<"Running commit-source with parameters:" << std::endl;
    std::cout <<"source :" << ss << std::endl;
    std::cout <<"runs   :" << rn << std::endl;
    std::cout <<"start  :" << st << std::endl;
    std::cout <<"end    :" << en << std::endl;
    std::cout <<"value : "<< vv << std::endl;
  }


  // collect the list of values from a file, if needed
  StringVec values;
  int nComm=0;
  for(auto const& c : vv) {
    if(c==',') nComm++;
  }

  if (nComm>0) {
    values.emplace_back(vv);
  } else {
    std::ifstream myfile;
    myfile.open(vv);
    if(!myfile.is_open()) {
      std::cout << "ERROR - failed to open file "<< vv << std::endl;
      return 1;
    }
    std::string line;
    while ( std::getline(myfile,line) ) {
      if(!line.empty()) values.emplace_back(line);
    }
    if(_verbose>2) {
      std::cout << "Read "<<values.size() <<" values from "<< vv << std::endl;
    }
  }

  // parse value strings into DqmValue objects

  DqmValueCollection valueColl;
  for(auto const& vs : values) {
    DqmValue vv;
    // take a string like "cal,disk0,menaE,20.0,0.1,0"
    // validate and split it into fields
    rc = parseValue(vv,vs);
    if(rc) return 1;
    valueColl.emplace_back(vv);
  }

  // lookup or create, if necessary, the 4 table entries
  // this doesn't need to be a transaction since each step is atomic

  std::string  command,result;

  rc = _sql.connect();
  if(rc) return rc;

  command = "SET ROLE dqmWrite;";
  rc = _sql.execute(command, result);
  if(rc) return rc;

  // 1 ****** find or create the source ID 

  int sid = -1;

  command="select sid from dqm.sources where process='"+source.process()
    +"' and stream='"+source.stream()
    +"' and aggregation='"+source.aggregation()
    +"' and version="+std::to_string(source.version())+";";
  if(_verbose>4) {
    std::cout << "Find sid for source" << std::endl;
    std::cout << "command: " << command << std::endl;
  }
  rc = _sql.execute(command, result);
  if(rc) return rc;
  if(_verbose>4) {
    std::cout << "result: "<< result << std::endl;
  }

  if(!result.empty()) { // found it
    sid = std::stoi(result);
  } else { // didn't find it, so create it

    command = "INSERT INTO dqm.sources (process,stream,aggregation,version)  VALUES ('"
    +source.process()+"','"
    +source.stream()+"','"
    +source.aggregation()+"',"
    +std::to_string(source.version())+") RETURNING sid;";

    if(_verbose>4) {
      std::cout << "committing source:" << std::endl;
      std::cout << "command: "<<command << std::endl;
    }

    rc = _sql.execute(command, result);
    if(rc) return rc;
    
    sid = std::stoi(result);
  }

  if(_verbose>0) {
    std::cout << "sid is "<<sid <<std::endl;
  }

  // 2 ****** find or create the interval ID 


  int iid = -1;

  command="select iid from dqm.intervals where sid="
    +std::to_string(sid)
    +" and start_run="+std::to_string(time.iov().startRun())
    +" and start_subrun="+std::to_string(time.iov().startSubrun())
    +" and end_run="+std::to_string(time.iov().endRun())
    +" and end_subrun="+std::to_string(time.iov().endSubrun())
    +" and start_time='"+time.startTime()+"'"
    +" and end_time='"+time.endTime()+"';";
  if(_verbose>4) {
    std::cout << "Find iid for interval" << std::endl;
    std::cout << "command: " << command << std::endl;
  }
  rc = _sql.execute(command, result);
  if(rc) return rc;
  if(_verbose>4) {
    std::cout << "result: "<< result << std::endl;
  }

  if(!result.empty()) { // found it
    iid = std::stoi(result);
  } else { // didn't find it, so create it

    command = "INSERT INTO dqm.intervals (sid,start_run,start_subrun,end_run,end_subrun,start_time,end_time)  VALUES ("
      +std::to_string(sid)+","
      +std::to_string(time.iov().startRun())+","
      +std::to_string(time.iov().startSubrun())+","
      +std::to_string(time.iov().endRun())+","
      +std::to_string(time.iov().endSubrun())+",'"
      +time.startTime()+"','"
      +time.endTime()+"') RETURNING iid;";

    if(_verbose>4) {
      std::cout << "committing source:" << std::endl;
      std::cout << "command: "<<command << std::endl;
    }

    rc = _sql.execute(command, result);
    if(rc) return rc;
    
    iid = std::stoi(result);
  }

  if(_verbose>0) {
    std::cout << "iid is "<<iid <<std::endl;
  }

  // 3 ****** find or create the value ID 

  for(auto const& value: valueColl) {
    int vid = -1;

    command="select vid from dqm.values where groupx='"+value.group()
      +"' and subgroup='"+value.subgroup()
      +"' and namex='"+value.name()+"';";
    if(_verbose>4) {
      std::cout << "Find vid for value" << std::endl;
      std::cout << "command: " << command << std::endl;
    }

    rc = _sql.execute(command, result);
    if(rc) return rc;

    if(_verbose>4) {
      std::cout << "result: "<< result << std::endl;
    }

    if(!result.empty()) { // found it
      vid = std::stoi(result);
    } else { // didn't find it, so create it

    command = "INSERT INTO dqm.values (groupx,subgroup,namex)  VALUES ('"
    +value.group()+"','"
    +value.subgroup()+"','"
    +value.name()+"') RETURNING vid;";

    if(_verbose>4) {
      std::cout << "committing source:" << std::endl;
      std::cout << "command: "<<command << std::endl;
    }

    rc = _sql.execute(command, result);
    if(rc) return rc;
    
    vid = std::stoi(result);
  }

  if(_verbose>0) {
    std::cout << "vid is "<< vid <<std::endl;
  }

  // 4 ****** create the numbers entry


    int nid = -1;

    command = "INSERT INTO dqm.numbers (sid,iid,vid,valuex,sigma,code)  VALUES ("
      +std::to_string(sid)+","
      +std::to_string(iid)+","
      +std::to_string(vid)+",'"
      +value.valueStr()+"','"
      +value.sigmaStr()+"',"
      +std::to_string(value.code())+") RETURNING nid;";
  
    if(_verbose>4) {
      std::cout << "committing source:" << std::endl;
      std::cout << "command: "<<command << std::endl;
    }
    
    rc = _sql.execute(command, result);
    if(rc) return rc;
    
    nid = std::stoi(result);

    if(_verbose>0) {
      std::cout << "new nid is "<< nid <<std::endl;
    }
  }

  rc = _sql.disconnect();
  if(rc) return rc;

  return 0;
  
}


//***********************************************************

int mu2e::DqmTool::printSources() {

  int rc = 0;
  _argMap["heading"] = "";
  rc = parseAction();
  if(rc!=0) return rc;

  std::string table("dqm.sources");
  std::string select("*");
  StringVec where;
  std::string order;
  _result.clear();
  rc = _reader.query(_result,select,table,where,order);
  if(rc) return rc;


  if(!_argMap["heading"].empty()) {
    _result = "sid, process, stream, aggregation, version\n"+_result;
  }

  return 0;
}

//***********************************************************

int mu2e::DqmTool::printIntervals() {

  int rc = 0;
  _argMap["heading"] = "";
  rc = parseAction();
  if(rc!=0) return rc;

  std::string table("dqm.intervals");
  std::string select("*");
  StringVec where;
  std::string order;
  _result.clear();
  rc = _reader.query(_result,select,table,where,order);
  if(rc) return rc;


  if(!_argMap["heading"].empty()) {
    _result = "iid, sid, start_run, start_subrun, end_run, end_subrun, start_time, end_time\n"+_result;
  }

  return 0;
}

//***********************************************************

int mu2e::DqmTool::printValues() {

  int rc = 0;
  _argMap["heading"] = "";
  rc = parseAction();
  if(rc!=0) return rc;

  std::string table("dqm.values");
  std::string select("*");
  StringVec where;
  std::string order;
  _result.clear();
  rc = _reader.query(_result,select,table,where,order);
  if(rc) return rc;

  if(!_argMap["heading"].empty()) {
    _result = "vid, group, subgroup, name\n"+_result;
  }

  return 0;
}

//***********************************************************

int mu2e::DqmTool::printNumbers() {

  int rc = 0;
  _argMap["heading"] = "";
  _argMap["source"] = "";
  _argMap["value"] = "";
  _argMap["expand"] = "";
  rc = parseAction();
  if(rc!=0) return rc;

  int sid = -1;
  if(!_argMap["source"].empty()) {
    std::string& ss = _argMap["source"];
    if( ss.find_first_not_of("0123456789") == std::string::npos ) {
      sid = std::stoi(ss); // was an integer
    } else { // is file name or csv
      DqmSource source;
      std::string runs;
      rc = parseSource(source,runs,ss);
      if(rc) return rc;
      sid = lookupSid(source);
      if( sid<0 ) {
        std::cout << "ERROR - source could not be interpreted" << std::endl;
        return 1;
      }
    }
  }

  int vid = -1;
  if(!_argMap["value"].empty()) {
    std::string& vv = _argMap["value"];
    if( vv.find_first_not_of("0123456789") == std::string::npos ) {
      vid = std::stoi(vv); // was an integer
    } else { // is csv
      DqmValue value;
      // parse value expects the value's number with the value description
      rc = parseValue(value,vv+",0,0,0");
      if(rc) return rc;
      vid = lookupVid(value);
      if( vid<0 ) {
        std::cout << "ERROR - value could not be interpreted" << std::endl;
        return 1;
      }
    }
  }


  std::string table = "dqm.numbers";
  std::string select;
  StringVec where;
  if(sid>=0) where.emplace_back("sid:eq:"+std::to_string(sid));
  if(vid>=0) where.emplace_back("vid:eq:"+std::to_string(vid));
  std::string order("sid,nid,iid");

  std::string result;
  rc = _reader.query(result,select,table,where,order);
  if(rc) return rc;

  if(_argMap["expand"].empty()) {
    if(_argMap["heading"].empty()) {
      _result = result;
    } else {
      _result = "nid, sid, iid, vid, value, sigma, code\n"+result;
    } 
    return 0;
  }

  // if we came here, then we have to --expand the printout
  // to include the text of source, value and interval
  printSources();
  std::string sources = _result;
  auto ssv = splitString(sources,'\n');
  ssv.pop_back(); // last entry is blank
  std::map<int,std::string> smap;
  for(auto const& ss : ssv) {
    if(std::isdigit(ss[0])) { // if heading was set, ther ewill be a text line
      auto ii = ss.find(',');
      int ind = std::stoi(ss.substr(0,ii));
      smap[ind] = ss;
    }
  }

  printValues();
  std::string values = _result;
  auto vsv = splitString(values,'\n');
  vsv.pop_back(); // last entry is blank
  std::map<size_t,std::string> vmap;
  for(auto const& ss : vsv) {
    if(std::isdigit(ss[0])) {
      auto ii = ss.find(',');
      int ind = std::stoi(ss.substr(0,ii));
      vmap[ind] = ss;
    }
  }


  printIntervals();
  std::string intervals = _result;
  auto isv = splitString(intervals,'\n');
  isv.pop_back(); // last entry is blank
  std::map<size_t,std::string> imap;
  for(auto const& ss : isv) {
    if(std::isdigit(ss[0])) {
      auto ii = ss.find(',');
      int ind = std::stoi(ss.substr(0,ii));
      imap[ind] = ss;
    }
  }

  _result.clear();

  auto rsv = splitString(result,'\n');
  rsv.pop_back(); // last entry is blank
  for(auto const& rs:rsv) {
    auto rss =  splitString(rs,',');
    std::cout << rss[0]<< "," << rss[4]<<","<< rss[5]<<","<< rss[6];
    int ind;
    ind = std::stoi(rss[1]);
    std::cout << "  " << smap[ind];
    ind = std::stoi(rss[3]);
    std::cout << "  " << vmap[ind];
    ind = std::stoi(rss[2]);
    std::cout << "  " << imap[ind]<<"\n";
  }


  return 0;
}



//***********************************************************

int mu2e::DqmTool::lookupSid(DqmSource& source) {

  int sid = -1;
  int rc = 0;

  std::string table = "dqm.sources";
  std::string select = "sid";
  StringVec where;
  std::string order;
  std::string csv;
  where.emplace_back("process:eq:"+source.process());
  where.emplace_back("stream:eq:"+source.stream());
  where.emplace_back("aggregation:eq:"+source.aggregation());
  where.emplace_back("version:eq:"+std::to_string(source.version()));
  rc = _reader.query(csv,select,table,where,order);
  if(rc) return rc;

  std::cout << "debug sid csv "<<csv<<std::endl;
  if( !csv.empty() ) {
    sid = std::stoi(csv);
  }

  return sid;
}


//***********************************************************

int mu2e::DqmTool::lookupVid(DqmValue& value) {

  int vid = -1;
  int rc = 0;

  std::string table = "dqm.values";
  std::string select = "vid";
  StringVec where;
  std::string order;
  std::string csv;
  where.emplace_back("groupx:eq:"+value.group());
  where.emplace_back("subgroup:eq:"+value.subgroup());
  where.emplace_back("namex:eq:"+value.name());
  rc = _reader.query(csv,select,table,where,order);
  if(rc) return rc;

  std::cout << "debug vid csv "<<csv<<std::endl;
  if( !csv.empty() ) {
    vid = std::stoi(csv);
  }

  return vid;
}



//***********************************************************
// parse string into a DqmSource
// runs returns the sequencer field as a run range

int mu2e::DqmTool::parseSource(DqmSource& source, std::string& runs, 
                               const std::string &ss) {

  //ss (source string) may be a file:
  //ntd.mu2e.DQM_stream.process_aggregation_version.run_subrun.root
  //or a text listing
  //process,stream,aggregation,version

  StringVec vs = splitString(ss);
  
  std::string process,stream,aggregation,version;
  if(vs.size()==6) { // assume a file name

    StringVec dd = splitString(vs[2],'_');
    if(dd.size()!=2) {
      std::cout << "ERROR - interpreting source as a file name, \n"
                << "      did not find 2 fields in the description field: " 
                << vs[2] <<std::endl;
      return 1;
    }
    stream = dd[1];

    StringVec cc = splitString(vs[3],'_');
    if(cc.size()!=3) {
      std::cout << "ERROR - interpreting source as a file name, \n"
                << "      did not find 3 fields in the config field: " 
                << vs[3] <<std::endl;
      return 1;
    }
    process = cc[0];
    aggregation = cc[1];
    version = cc[2];

    // assuming a sequencer with an underscore, change to 
    // a colon so it is in run range format
    runs = vs[4].replace(vs[4].find("_"),1,":");

  } else if(vs.size()==4) {

    process = vs[0];
    stream = vs[1];
    aggregation = vs[2];
    version = vs[3];
    runs = "";

  } else {
    std::cout << "ERROR - source did not have 6 fields (for a file name)" << std::endl;
    std::cout << "           or 4 fields (for a parameter listing)" << std::endl;
    return 1;
  }

  // default values
  if(aggregation.empty()) aggregation = "file";
  if(version.empty()) version = "0";

  if(_verbose>5) {
    std::cout << "Parsed source string: "<< ss << std::endl;
    std::cout << "process: " << process << std::endl;
    std::cout << "stream: " << stream<< std::endl;
    std::cout << "aggregation: " << aggregation << std::endl;
    std::cout << "version: " << version << std::endl;
    std::cout << "runs: " << runs << std::endl;
  }

  source = DqmSource(-1,process,stream,aggregation,std::stoi(version));

  return 0;
}

//***********************************************************
// parse string into a DqmValue

int mu2e::DqmTool::parseValue(DqmValue& rvalue, const std::string& vv) {

  //vv should be a comma-separated list of 
  // group,subgroup,name,value,sigma,code

  StringVec vs = splitString(vv);
  
  std::string group,subgroup,name,value,sigma;
  int code;

  if(vs.size()!=6) {
    std::cout << "ERROR - not 6 items in value statement: "
              << vv <<std::endl;
    return 1;
  }


  if(vs[0].empty()) {
    std::cout << "ERROR - required 'group' field is empty in value statement : " 
              << vv << std::endl;
    return 1;
  }
  if(vs[2].empty()) {
    std::cout << "ERROR - required 'name' field is empty in value statement : " 
              << vv << std::endl;
    return 1;
  }
  if(vs[3].empty()) vs[3] = "0.0";
  if(vs[4].empty()) vs[4] = "-1";
  if(vs[5].empty()) vs[5] = "0";

  group = vs[0];
  subgroup = vs[1];
  name = vs[2];
  value = vs[3];
  sigma = vs[4];
  code = std::stoi(vs[5]);


  if(_verbose>5) {
    std::cout << "Parsed value string: "<< vv << std::endl;
    std::cout << "group: " << group << std::endl;
    std::cout << "subgroup: " << subgroup << std::endl;
    std::cout << "name: " << name << std::endl;
    std::cout << "value: " << value << std::endl;
    std::cout << "sigma: " << sigma << std::endl;
    std::cout << "code: " << code << std::endl;
  }

  rvalue = DqmValue(group,subgroup,name,value,sigma,code);

  return 0;
}



//***********************************************************
// split into words, respecting quoted strings

mu2e::DqmTool::StringVec 
mu2e::DqmTool::splitString(const std::string &command, char del) {

  using namespace boost;

  if(del=='X') { // try to discover the delimitor
    int nd = 0;
    for(char c : command) if(c=='.') nd++;
    int nc = 0;
    for(char c : command) if(c==',') nc++;
    del = ',';
    if(nd>nc) del = '.';
  }

  StringVec sv;

  escaped_list_separator<char> els('\\', del, '"');
  tokenizer<escaped_list_separator<char>> tok(command, els);
  for (tokenizer<escaped_list_separator<char>>::iterator beg = tok.begin();
       beg != tok.end(); ++beg) {
    std::string ss(*beg);
    boost::trim(ss);
    sv.emplace_back(ss);
  }

  return sv;
}

//***********************************************************

int mu2e::DqmTool::parseGeneral() {

  if (_args.size() == 0) {
    usage();
    return 1;
  }
  if (_args[0] == "-h" || _args[0] == "--help") {
    usage();
    return 1;
  }

  // this is the action word, like "commit-source"
  _action = _args[0];

  size_t ipt = 1; // starting after the action word

  while (ipt < _args.size()) {

    if (_args[ipt] == "-h" || _args[ipt] == "--help") {
      // help for this action word
      usage(true);
      return 1;

    } else if (_args[ipt] == "--verbose") {

      if (ipt == _args.size() - 1) {
        std::cout << "ERROR no verbose value" << std::endl;
        return 1;
      }
      if (!std::isdigit(_args[ipt + 1][0])) {
        std::cout << "ERROR verbose value is not a number " << std::endl;
        return 1;
      }
      _verbose = std::stoi(_args[ipt + 1]);
      ipt = ipt + 2;

    } else {

      // whatever is not parsed here is left for the action to interpret
      _actionArgs.emplace_back(_args[ipt]);
      ipt++;
    }

  } // loop over args

  if (_verbose > 5) {
    std::cout << "Parsed general arguments:" << std::endl;
    std::cout << "    verbose = " << _verbose << std::endl;
  }

  return 0;
}

//***********************************************************
// the routine chosen by the action has loaded _argMap
// with a list of allowed arguments with defaults, now see how they
// match to actionArgs, the actual command line arguments

int mu2e::DqmTool::parseAction() {

  size_t ipt = 0;
  while (ipt < _actionArgs.size()) {
    if(_actionArgs[ipt].substr(0,2) != "--" ) {
      std::cout << "ERROR - action arguments did not start with a qualifier"  << std::endl;
      return 1;
    }
    std::string aa = _actionArgs[ipt].substr(2,std::string::npos);
    auto it = _argMap.find(aa);
    if (it == _argMap.end()) {
      std::cout << "ERROR - unknown argument " << _actionArgs[ipt] << std::endl;
      return 1;
    }
    if (ipt == _actionArgs.size() - 1 || _actionArgs[ipt + 1][0] == '-') {
      it->second = "FOUND"; // arg with no value is simply found present
      ipt++;
    } else {
      it->second = _actionArgs[ipt + 1];
      ipt = ipt + 2;
    }
  }

  if (_verbose > 5) {
    std::cout << "Parsed action for " << _action << std::endl;
    for (auto const &aa : _argMap) {
      std::cout << "    " << aa.first << " = " << aa.second << std::endl;
    }
  }

  return 0;
}


//***********************************************************
// start from the command string
void mu2e::DqmTool::usage(bool inAction) {

  if(_action=="" || _action=="help") {
    std::cout << 
      " \n"
      " dqmTool ACTION [OPTIONS]\n"
      " \n"
      " Perform basic DQM database maintenance functions.  The action \n"
      " determines what to do, and OPTIONS refine it.  \n"
      " Use dqmTool ACTION --help for lists of options for that action.\n"
      " \n"
      " Global options:\n"
      "   --verbose <level>, an integer 0-10\n"
      " \n"
      " <ACTION>\n"
      "    print-sources : print all sources (such as files)\n"
      "    print-intervals : print all run/time intervals of sources\n"
      "    print-values : print all value names \n"
      "    print-numbers : print al materic numbers\n"
      "    commit-value : insert a (or set) metric number\n"
      " \n"
      <<std::endl;
  } else if(_action=="print-sources") {
    std::cout << 
      " \n"
      " dqmTool print-sources [OPTIONS]\n"
      "   Print the recorded sources of metrics\n"
      " \n"
      " [OPTIONS]\n"
      "    --heading : print columns headings too\n"
      " \n"
      << std::endl;
  } else if(_action=="print-intervals") {
    std::cout << 
      " \n"
      " dqmTool print-intervals [OPTIONS]\n"
      "   Print the recorded intervals for sources of metrics\n"
      " \n"
      " [OPTIONS]\n"
      "    --heading : print columns headings too\n"
      " \n"
      << std::endl;
  } else if(_action=="print-values") {
    std::cout << 
      " \n"
      " dqmTool print-values [OPTIONS]\n"
      "   Print the recorded names of the metrics\n"
      " \n"
      " [OPTIONS]\n"
      "    --heading : print columns headings too\n"
      " \n"
      << std::endl;
  } else if(_action=="print-numbers") {
    std::cout << 
      " \n"
      " dqmTool print-numbers [OPTIONS]\n"
      "   Print the recorded metrics\n"
      " \n"
      " [OPTIONS]\n"
      "    --heading : print columns headings too\n"
      "    --source : only print numbers with this source\n"
      "         may be sid, csv or file name\n"
      "    --value  : only print numbers with this value (name)\n"
      "         may be vid or csv \n"
      "    --expand : expand the id values into strings\n"
      "  \n"
      "  Examples:\n"
      "    dqmTool print-numbers --heading\n"
      "    dqmTool print-numbers --source 13 --value 2\n"
      "    dqmTool print-numbers --source ntd.mu2e.DQM_strmA.test_file_000.0_0.root\n"
      "    dqmTool print-numbers --source \"test,strmB,file,0\"  \\\n"
      "                   --value \"2,det0,subgroup0,var0\"\n"
      "  \n"
      " \n"
      << std::endl;
  } else if(_action=="commit-value") {
    std::cout << 
      " \n"
      " dqmTool commit-value [OPTIONS]\n"
      " \n"
      " \n"
      " [OPTIONS]\n"
      "    --source STRING : name of the DQM histogram source file\n"
      "         or a csv string like \"pass1,ele,file,0\" \n"
      "    --runs STRING : run period like \"1100:0-1101:999999\" (optional) \n"
      "    --start STRING : start of DQM interval, like \"2022-01-01T14:00:00\" (optional) \n"
      "    --end STRING : end of DQM interval, like \"2022-01-01T14:00:00\" (optional) \n"
      "    --value STRING : either a csv string like \"cal,disk0,meanE,20.0,0.1,0\" \n"
      "           or a filespec of a text file containing csv strings \n"
      " \n"
      " \n"
      << std::endl;
  } else if(_action=="unique-value") {
    std::cout << 
      " \n"
      " dqmTool unique-value [OPTIONS]\n"
      " \n"
      " .\n"
      " \n"
      " [OPTIONS]\n"
      "    --name NAME : name of the table\n"
      "    --user USERNAME : only print tables committed by this user \n"
      "    --cid CID : only print contents for this cid \n"
      " \n"
      << std::endl;
  }

}
