cet_make_library(
  SOURCE
  DqmMetrics.cc
  DqmMetrics_cal.cc
  DqmMetrics_crv.cc
  DqmMetrics_str.cc
  DqmMetrics_trk.cc
  DqmTool.cc

  LIBRARIES PUBLIC
  Offline::DbService
  Offline::DbTables

  LIBRARY_NAME dqm
)

cet_make_exec(NAME dqmTool
    SOURCE dqmTool_main.cc
    LIBRARIES
      Offline::DbService
      dqm::dqm
)

cet_make_exec(NAME dqmMetrics
    SOURCE dqmMetrics_main.cc
    LIBRARIES
      Offline::DbService
      dqm::dqm
)

cet_build_plugin(DqmCal art::module
    REG_SOURCE DqmCal_module.cc
    LIBRARIES REG
      Offline::DbService
      art_root_io::TFileService_service
      ROOT::Postscript
)

cet_build_plugin(DqmCrv art::module
    REG_SOURCE DqmCrv_module.cc
    LIBRARIES REG
      Offline::DbService
      art_root_io::TFileService_service
      ROOT::Postscript
)

cet_build_plugin(DqmStr art::module
    REG_SOURCE DqmStr_module.cc
    LIBRARIES REG
      Offline::DbService
      Offline::RecoDataProducts
      art_root_io::TFileService_service
      ROOT::Postscript
)

cet_build_plugin(DqmTrk art::module
    REG_SOURCE DqmTrk_module.cc
    LIBRARIES REG
    Offline::DbService
    Offline::RecoDataProducts
      art_root_io::TFileService_service
)

