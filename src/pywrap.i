//
// swig interface file to wrap c++ code for python
//

%module DQM

%include "std_vector.i"
%include "std_string.i"
%include "stdint.i"

%apply const std::string& {std::string* foo};
%template(vec_str) std::vector<std::string>;

%{
#include "DQM/inc/DqmTool.hh"
%}

%include "DQM/inc/DqmTool.hh"
