cmake_minimum_required (VERSION 3.19 FATAL_ERROR)

find_package(cetmodules)

project(dqm VERSION 0.1.0)

include(CetCMakeEnv)
cet_cmake_env()
SET(CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE)

cet_set_compiler_flags(DIAGS VIGILANT
 WERROR
 NO_UNDEFINED
 EXTRA_FLAGS -pedantic
 -Wno-unused-parameter -Wno-type-limits -Wno-ignored-qualifiers -Wno-unused-but-set-parameter -Wno-extra -Wno-non-virtual-dtor -Wno-implicit-fallthrough -Wno-deprecated-copy
)

file(CREATE_LINK ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/DQM SYMBOLIC)


find_package(Offline REQUIRED EXPORT)
find_package(art_root_io REQUIRED EXPORT)

include(ArtDictionary)
include(BuildPlugins)


add_subdirectory(src)

install(DIRECTORY data DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/dqm)

install_source(SUBDIRS src)
install_headers(NO_RELATIVE_SUBDIR SUBDIRS inc SUBDIRNAME DQM)
install_fhicl(SUBDIRS fcl SUBDIRNAME DQM/fcl)

cet_cmake_config()
