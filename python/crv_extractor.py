#
# DQM CRV extractor
# read CRV root files and create dqm database-entry text files
# see https://mu2ewiki.fnal.gov/wiki/DQM
#
# DJT  USouthCarolina   2024
#
# crv_extractor.py <RootFile>
#
# <RootFile> - containing CRV metadata tree and DQM hists
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
#
# current DQM filename format is
# data_tier.owner.DESC-DQM.CAMPAIGN-VSTRING-AGGREGATION.seq.root
# extract process(Campaign),version, aggregation from field 4 of DQM-root_file
#
def parse_dqm_file(root_filename):
    filename=os.path.basename(root_filename).split(".")
    field4=filename[3].split("-",1)
    process=field4[0]
    part2=field4[1].rsplit("-",1)
    version=part2[0]
    aggregation=part2[1]
    return process,version,aggregation
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
#----------------------------------------------------------------------------
def create_DQM_df():
# multiplier is number of metrics from "hist"

    df1 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["mpvPEsTemperatureCorrected"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df2 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["calibConstantsTemperatureCorrected"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df3 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["meanTemperatures"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df4 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["febTemperaturesAvg"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df5 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["noiseRate"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df6 = pd.DataFrame ({
    "group": ["CRV"]*2,
    "hist": ["calibConstants"]*2,
    "metric":["LeftEdge","RightEdge"],
    "value":[-999.,-999.],
    "uncertainty":[-999.,-999.],
    "dqm_int":[0,0]
    })

    df7 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["pedestals"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df8 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["xtalkProbability"]*3,
    "metric":["LeftEdge","RightEdge","Centroid"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })

    df9 = pd.DataFrame ({
    "group": ["CRV"]*3,
    "hist": ["time"]*3,
    "metric":["LeftEdge","RightEdge","Peak"],
    "value":[-999.,-999.,-999.],
    "uncertainty":[-999.,-999.,-999.],
    "dqm_int":[0,0,0]
    })
#
# df_list controls which metrics are extracted
#
    df_list = [df1, df2, df3, df4, df5, df6, df7, df8, df9]
    df=pd.concat(df_list,ignore_index=True)
    return df
#----------------------------------------------------------------------------
def extract_metrics(root_file,df):

    file = ROOT.TFile.Open(root_file)
    tree = file.Get("metaData")

    for row in df.itertuples():
        hist = file.Get(row.hist)
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

    file = ROOT.TFile.Open(root_file)
    tree = file.Get("metaData")
    for entry in tree:
        runNumber = entry.runNumber
        subrunNumber = entry.subrunNumber
        firstSpillTime = entry.firstSpillTime
        lastSpillTime = entry.lastSpillTime
        configuration = entry.configuration
        version = entry.version
    file.Close()

# get source information for dqm-db
    process,version,aggregation=parse_dqm_file(root_file)
    meta_data=samweb_dict(root_file)
    stream=parse_parent_file(meta_data['Parents'])

# check times (fix time=0 for runs <=1043 with file parent 'Create Date')
    if (firstSpillTime == 0):
        parent_meta_data=samweb_dict(meta_data['Parents'])
        start_time=parent_meta_data['Create Date']
        end_time=parent_meta_data['Create Date']
    else:
        start_time=datetime.fromtimestamp(firstSpillTime).isoformat()
        end_time=datetime.fromtimestamp(lastSpillTime).isoformat()

# output metada and dqmTool commands
    name_fields[5]="sh"
    sh_file = ".".join(name_fields)
    f = open(sh_file, 'w')

    print("dqmTool commit-value"," \\",sep='',file=f)
    print("--source \"",process,"\",\"",stream,"\",\"",aggregation,"\",\"",version,"\""," \\",sep='',file=f)
    print("--runs  \"",runNumber,":",subrunNumber,"\""," \\",sep='',file=f)
    print("--start \"",start_time,"\""," \\",sep='',file=f)
    print("--end   \"",end_time,"\""," \\",sep='',file=f)
    print("--value ",txt_file,sep='',file=f)

    f.close()
    return sh_file,txt_file
#------------------------------------------------------------------------
# executed block starts here
if __name__ == "__main__":
    parser=argparse.ArgumentParser(description='Extract CRV metrics from root file for DQM')
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
