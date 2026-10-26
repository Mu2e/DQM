#ifndef DQM_DqmCrvConfiguration_hh
#define DQM_DqmCrvConfiguration_hh
//
// CRVDQMRun1 configuration of the DqmCrv* modules. The CRV clients book the
// readout of one configuration at construction ("run1a" or "extracted"), so
// the module takes it from FHiCL and checks it against the geometry at run
// start.
//

#include "Offline/CRVDQM/inc/CRVDQMRun1.hh"

#include "cetlib_except/exception.h"

#include <string>

namespace mu2e {

// The CRVDQMRun1 configuration with layout name `name`.
inline int crvDqmConfiguration(const std::string& name) {
  for (int c = 0; c < CRVDQMRun1::kNConfigurations; ++c) {
    if (name == CRVDQMRun1::configurationName(c)) {
      return c;
    }
  }
  throw cet::exception("DqmCrv") << "configuration \"" << name
                                 << "\" is not a CRVDQMRun1 configuration (run1a, extracted).\n";
}

// A geometry other than the booked configuration would fill nothing
// (CRV*DQM::SetConfiguration refuses it), so stop the job instead.
inline void checkCrvDqmConfiguration(int booked, int geometry) {
  if (geometry != booked) {
    throw cet::exception("DqmCrv")
        << "the CRV DQM clients were booked for configuration \""
        << CRVDQMRun1::configurationName(booked) << "\" (fcl `configuration`) but the geometry is \""
        << CRVDQMRun1::configurationName(geometry) << "\".\n";
  }
}

}  // namespace mu2e

#endif
