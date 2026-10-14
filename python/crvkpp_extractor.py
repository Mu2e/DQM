#!/usr/bin/env python
#
# DQM CRV extractor
# read CRV root files and create dqm database-entry text files
# see https://mu2ewiki.fnal.gov/wiki/DQM
#
# DJT  USouthCarolina   2025
#
# crvkpp_extractor.py <RootFile>
#
# <RootFile> - containing CRV_kpp DQM hists
#
# output - .txt file containg extract_metrics
#          .sh file containing dqmTools command
#-------------------------------------------------------------
import sys
import subprocess
import os
import ROOT
from datetime import datetime
import argparse
import pandas as pd
import math

# datetime check for time field format
#
def has_fractional(iso_str):
    try:
        # Use replace('Z', '+00:00') if on a version older than Python 3.11
        dt = datetime.fromisoformat(iso_str)
        return dt.microsecond > 0
    except ValueError:
        return False

#
# current DQM filename format is
# data_tier.owner.DESC-DQM.CAMPAIGN-VSTRING-AGGREGATION.seq.root
# extract process(Campaign),version, aggregation from field 4 of DQM-root_file
#
def parse_dqm_file(root_filename):
    filename=os.path.basename(root_filename).split(".")
    file_dict={}
    field5=filename[4].split("_",1)
    file_dict['run']=field5[0]
    file_dict['subrun']=field5[1]
    field4=filename[3].split("-",1)
    file_dict['process']=field4[0]
    part2=field4[1].rsplit("-",1)
    file_dict['version']=part2[0]
    file_dict['aggregation']=part2[1]
    return file_dict
#----------------------------------------------------------------------------
# current production filename format is
# data_tier.owner.description.configuration.sequencer.file_format
# extract stream information from field 4
#
def parse_parent_file(root_filename):
    filename=os.path.basename(root_filename).split(".")
    field4=filename[3]
    return field4
#----------------------------------------------------------------------------
# create python dictionary from samweb metadata
#  keys are : ['File Name', 'File Id', 'Create Date', 'User', 'File Size', 'Checksum', 'adler32',
#             'Content Status', 'File Type', 'File Format', 'Data Tier', 'Application', 'Dataset.Tag',
#             'dh.configuration', 'dh.dataset', 'dh.description', 'dh.owner', 'dh.sequencer', 'dh.sha256', 'Parents'
#
def samweb_dict(root_filename):
    filename=os.path.basename(root_filename)
    result = subprocess.run(["samweb", "get-metadata",filename], capture_output=True, text=True)
    stdout_array=result.stdout.split("\n")
    file_dict={}
    for i in range(len(stdout_array)-1):
        key, value = stdout_array[i].split(":",1)
        file_dict[key.strip()] = value.strip()
    return file_dict

#
# create python dictionary from metacat metadata
#  keys are : ['checksums', 'adler32', 'enstore', 'created_timestamp', 'creator', 'fid', 'name', 'namespace',
#              'size', 'updated_timestamp', 'metadata', 'dh.dataset', 'dh.status', 'dh.type', 'fn.configuration',
#              'fn.description', 'fn.format', 'fn.owner', 'fn.sequencer', 'fn.tier', 'parents', 'mu2e']
#
def metacat_dict(root_filename):
    filename="mu2e:"+os.path.basename(root_filename)
    result = subprocess.run(["metacat", "file","show","-m","-l",filename], capture_output=True, text=True)
    stdout_array=result.stdout.split("\n")
    file_dict={}
    for i in range(len(stdout_array)-1):
        key, value = stdout_array[i].split(":",1)
        if (key.strip() == "parents"):
            key2, value2 = stdout_array[i+1].split(":",1)
            file_dict[key.strip()] = value2.split("(",1)[0].strip()
        else:
            file_dict[key.strip()] = value.strip()
    return file_dict
#

#----------------------------------------------------------------------------
def create_DQM_df():
# multiplier is number of metrics from "hist"

    df1 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["crvPEsMPV_CRVsector0"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df2 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["crvPEsMPV_CRVsector1"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df3 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["crvPEsMPV_CRVsector2"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df4 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["crvPedestals_CRVsector0"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df5 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["crvPedestals_CRVsector1"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df6 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["crvPedestals_CRVsector2"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df7 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["crvCalibConstants_CRVsector0"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df8 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["crvCalibConstants_CRVsector1"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df9 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["crvCalibConstants_CRVsector2"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df10 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["crvDigisPerChannelAndEvent_CRVsector0"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df11 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["crvDigisPerChannelAndEvent_CRVsector1"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df12 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["crvDigisPerChannelAndEvent_CRVsector2"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df13 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["crvCoincidencesClusters"]*3,
    "metric":["CCR1","CCR2","CCR3"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })
#
# df_list controls which metrics are extracted
#
    df_list = [df1, df2, df3, df4, df5, df6, df7, df8, df9, df10, df11, df12, df13]
    df=pd.concat(df_list,ignore_index=True)
    return df
#----------------------------------------------------------------------------
def extract_metrics(root_file,df):

    file = ROOT.TFile.Open(root_file)
    # historgrams are now in subdirectory CrvDQMcollector
    for row in df.itertuples():
        hist = file.Get("CrvDQMcollector/"+row.hist)
        if (row.metric == "LeftEdge"):
            df.loc[row.Index, 'value'] = hist.GetBinCenter(hist.FindFirstBinAbove())
            df.loc[row.Index, 'uncertainty'] = hist.GetBinWidth(hist.FindFirstBinAbove())

        if (row.metric == "RightEdge"):
            df.loc[row.Index, 'value'] = hist.GetBinCenter(hist.FindLastBinAbove())
            df.loc[row.Index, 'uncertainty'] = hist.GetBinWidth(hist.FindLastBinAbove())

        if (row.metric == "Centroid"):
            df.loc[row.Index, 'value'] = hist.GetMean()
            df.loc[row.Index, 'uncertainty'] = hist.GetMeanError()

        # if fit does not exist (led runs) then set to zero
        if (row.metric == "Peak"):
            try:
                df.loc[row.Index, 'value'] = hist.GetListOfFunctions().At(0).GetParameter(1)
                df.loc[row.Index, 'uncertainty'] = hist.GetListOfFunctions().At(0).GetParameter(2)
            except:
                df.loc[row.Index, 'value'] = 0.0
                df.loc[row.Index, 'uncertainty'] = 0.0

        if (row.metric == "CCR1"):
            ccr_1=hist.GetBinContent(hist.FindBin(1))
            ccr_tot=hist.GetEntries()
            if (ccr_tot > 0):
                df.loc[row.Index, 'value'] = ccr_1/ccr_tot
                df.loc[row.Index, 'uncertainty'] = math.sqrt(ccr_1)/ccr_tot
            else:
                df.loc[row.Index, 'value'] = -1.0
                df.loc[row.Index, 'uncertainty'] = -1.0
        if (row.metric == "CCR2"):
            ccr_2=hist.GetBinContent(hist.FindBin(2))
            ccr_tot=hist.GetEntries()
            if (ccr_tot > 0):
                df.loc[row.Index, 'value'] = ccr_2/ccr_tot
                df.loc[row.Index, 'uncertainty'] = math.sqrt(ccr_2)/ccr_tot
            else:
                df.loc[row.Index, 'value'] = -1.0
                df.loc[row.Index, 'uncertainty'] = -1.0
        if (row.metric == "CCR3"):
            ccr_3=hist.GetBinContent(hist.FindBin(3))
            ccr_tot=hist.GetEntries()
            if (ccr_tot > 0):
                df.loc[row.Index, 'value'] = ccr_3/ccr_tot
                df.loc[row.Index, 'uncertainty'] = math.sqrt(ccr_3)/ccr_tot
            else:
                df.loc[row.Index, 'value'] = -1.0
                df.loc[row.Index, 'uncertainty'] = -1.0
    file.Close()
    return df
#----------------------------------------------------------------------------
def output_dqm(root_file,df):
# root file name supplies "process, stream, aggregation, version"
# create .sh  and .txt file for dqmTool
#
# output metrics
    name_fields = os.path.basename(root_file).split(".")
    name_fields[0]="dqm"
    name_fields[5]="txt"
    txt_file = ".".join(name_fields)

    f = open(txt_file, 'w')
    for row in df.itertuples():
        slist = [row.group,row.hist,str(row.metric), "{:.5f}".format(row.value), "{:.5f}".format(row.uncertainty), str(row.dqm_int)+"\n"]
        f.write(",".join(slist))
    f.close()

# get source information for dqm-db
    file_info=parse_dqm_file(root_file)
    meta_data=metacat_dict(root_file)
    if "parents" in meta_data:
        stream=parse_parent_file(meta_data['parents'])
        parent_meta_data=metacat_dict(meta_data['parents'])
    else:
        print("missing meta_data: parents")
#    print(parent_meta_data)
    if "created_timestamp" in meta_data:
        if has_fractional(parent_meta_data['created_timestamp']):
            start_time=parent_meta_data['created_timestamp']
            print(start_time)
            start_time_obj=datetime.strptime(start_time,"%Y-%m-%d %H:%M:%S.%f%z")
            start_time_rounded = start_time_obj.replace(microsecond=0)
            start_time2=start_time_rounded.isoformat()
            print("created_timestamp= ",start_time2)
            updated_time=parent_meta_data['updated_timestamp']
            updated_time2=datetime.fromtimestamp(int(float(updated_time))).isoformat()
            print("updated_timestamp=",updated_time2)
        else:
            start_time2=parent_meta_data['created_timestamp']
            print(root_file)
    else:
        print("missing meta_data: created_timestamp")

# output metada and dqmTool commands
# leave out end time for now - updated time same as start time and wrong format
#
    name_fields[5]="sh"
    sh_file = ".".join(name_fields)
    f = open(sh_file, 'w')

# patch subrun number
    subrun_temp=file_info['subrun']
    if ("-") in file_info['subrun']:
        sub_patch = file_info['subrun'].split("-",1)
        subrun_temp=sub_patch[0]+sub_patch[1]
    if ("_") in file_info['subrun']:
        sub_patch = file_info['subrun'].split("_",1)
        subrun_temp=sub_patch[0]+sub_patch[1]

    print("dqmTool commit-value"," \\",sep='',file=f)
    print("--source \"",file_info['process'],"\",\"",stream,"\",\"",file_info['aggregation'],"\",\"",file_info['version'],"\""," \\",sep='',file=f)
    print("--runs  \"",file_info['run'],":",subrun_temp,"\""," \\",sep='',file=f)
#    print("--runs  \"",file_info['run'],":",file_info['subrun'],"\""," \\",sep='',file=f)
    print("--start \"",start_time2,"\""," \\",sep='',file=f)
#    print("--end   \"",end_time,"\""," \\",sep='',file=f)
    print("--value ",txt_file,sep='',file=f)

    f.close()
    return sh_file,txt_file
#------------------------------------------------------------------------
# executed block starts here
if __name__ == "__main__":
    parser=argparse.ArgumentParser(description='Extract CRV_kpp metrics from root file for DQM')
    parser.add_argument('RootFile',metavar='<RootFile>',help='Root file containing metatdata tree')
    parser.add_argument('--insert','-i',action='store_true',help='Insert values into DQM-db')
    args=parser.parse_args()
    DQM_df = create_DQM_df()
    extract_metrics(args.RootFile,DQM_df)
#    print(DQM_df)
    sh_file,txt_file=output_dqm(args.RootFile,DQM_df)
    if args.insert:
        result = subprocess.run("source ./"+sh_file, shell=True, capture_output=True, text=True)
        print(result)
    else:
        print(sh_file,txt_file)
        print("Insert metrics to DQM-db is OFF")
