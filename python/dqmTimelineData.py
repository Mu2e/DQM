import pandas as pd
import os
import urllib.request

class sourceItem:
    def __init__(self,source):
        self.sid = int(source.split(",")[0])
        self.version = source.split(",")[-1]
        self.item = "/".join( source.split(",")[1:-1] )

class valueItem:
    def __init__(self,value):
        self.vid = int(value.split(",")[0])
        self.item = "/".join( value.split(",")[1:] )

class dataItem:
    def __init__(self,number,sigma,code,
                 srun,ssrun,erun,esrun,stime,etime,version):
        self.number = number
        self.sigma = sigma
        self.code = code
        self.srun = srun
        self.ssrun = ssrun
        self.erun = erun
        self.esrun = esrun
        self.stime = stime
        self.etime = etime
        self.version = version
    def print(self, level=0):
        print("{:7g} {:7g} {:3d} {:6d} {:6d} {:6d} {:6d} {:s} {:s}".format(self.number,self.sigma,self.code,self.srun,self.ssrun,self.erun,self.esrun,self.stime,self.etime))


class plotData:

    def __init__(self,source,value):
        self.source = source
        self.value = value
        # to be filled with dataItem's
        self.data = []
        self.goodRuns = False
        self.goodTime = False
        self.nVersion = 0

    def print(self, level=0):
        if level>0:
            print("source =",self.source)
            print("value  =",self.value)
            print("{} data items".format(len(self.data)))
            print("goodRuns =",self.goodRuns)
            print("goodTime =",self.goodTime)
            print("nVersion =",self.nVersion)
        if level>1:
            for dd in self.data:
                dd.print(level)

    def checkData(self):
        vs = []
        for dd in self.data:
            if dd.srun>0 :
                self.goodRuns = True
            if "infinity" not in dd.stime:
                self.goodTime = True
            if dd.version not in vs:
                vs.append(dd.version)
        self.nVersion = len(vs)

class timelineMenuData:

    def __init__(self,sources,values):
        self.sources = []
        for ss in sources:
            self.sources.append(sourceItem(ss))
        self.sourceMenu = []
        for ss in self.sources:
            self.sourceMenu.append(ss.item)

        self.values = []
        for vv in values:
            self.values.append(valueItem(vv))
        self.valueMenu = []
        for vv in self.values:
            self.valueMenu.append(vv.item)

    def print(self,level=0):
        if level>0:
            print("loaded timeline menus: {:d} sources, {:d} values:".
                  format(len(self.sources),len(self.values)))
        if level>1:
            print("\nsource items")
            for ss in self.sources:
                print(F'    {ss.sid:3d}  {ss.item:s}   {ss.version:d}')
            print("\nvalue items")
            for vv in self.values:
                print(f'    {vv.vid:3d}  {vv.item}')

    # for a given process/stream/aggregation/version
    # return items, which includes sid's for lookup
    def getSourceItems(self, source, version):
        items = []
        for ss in self.sources:
            #if ss.item == source and (ss.version==version or version<0):
            if ss.item == source and (ss.version==version):
                items.append(ss)
        return items

    # for a given group/subgroup/name
    # return items, which includes vid's for lookup
    def getValueVid(self, value):
        for vv in self.values:
            if vv.item == value:
                return vv.vid
        return -1


class timelineData:

    def getMenuData(self):
        return self.menuData

    def readUrl(self, url):
        lines = []
        nread = 0
        furl = self.url+url
        print(furl)
        file = urllib.request.urlopen(furl)
        for line in file:
            nread = nread + 1
            decoded_line = line.decode("utf-8")
            if nread >1:
                lines.append(decoded_line[:-1]) # strip trailing \n
        #print(len(lines),lines)
        return lines

    def loadMenus(self):
        url="&t=dqm.sources"
        sources = self.readUrl(url)
        url="&t=dqm.values"
        values = self.readUrl(url)
        self.menuData = timelineMenuData(sources,values)


    def loadDbUrl(self):
        self.database="mu2e_dqm_prd"
        self.url = "https://dbdata0vm.fnal.gov:9443/QE/mu2e/prod/app/SQ/query?dbname="+self.database
        connFile = "/cvmfs/mu2e.opensciencegrid.org/DataFiles/Database/connections.txt"
        if not os.path.exists(connFile):
            return

        with open(connFile,"r") as cfile:
            lines = cfile.readlines()

        for ii,ll in enumerate(lines):
            words = ll.split()
            if len(words)>=2 and words[1]==self.database:
                words = lines[ii+4].split()
                self.url = words[1]+"dbname="+self.database
                return

    def __init__(self):
        self.loadDbUrl()
        self.loadMenus()



    # for a given source, see what values exist
    # find the list of values which have a
    def valuesForSource(self,sid):
        vids = []
        url="&t=dqm.numbers&w=sid:eq:{:d}&c=vid".format(sid)
        text = self.readUrl(url)
        #print("debug value for source: ",text)
        for ss in text:
            vids.append(int(ss))
        return vids

    # return a set of points suitable for a timeline
    # source is like "valNightly/ceSimReco/day"
    # value is like "ops/stats/CPU"
    # version is an int source version or -1 for all versions
    # return a plotData object
    def makePlotData(self,source,version,value):
        xx = plotData(source,value)
        # list of source items consistent with request, 
        # may have several entries with different versions
        sourceItems = self.menuData.getSourceItems(source, version)
        # the database vid (an int) for this value
        vid = self.menuData.getValueVid(value)
        if vid<0 :
            return xx;
        #print("makePlotData n si=",len(sourceItems))
        for si in sourceItems:
            # fetch the intervals for this source
            #print("fetching intervals for sid=",si.sid)
            url="&t=dqm.intervals&w=sid:eq:{:d}&o=start_run,start_subrun,start_time".format(si.sid)
            intervals = self.readUrl(url)
            intervalsd = {}
            # reorg in a dictionary for easy lookup
            for ii in intervals:
                iis = ii.split(",")
                iid = int(iis[0]) # the database interval id, iid
                intervalsd[iid] = iis
            #print("makePlotData intervalsd ",intervalsd)
            # find numbers related to the source (sid) and value (vid)
            url="&t=dqm.numbers&w=sid:eq:{:d}&w=vid:eq:{:d}".format(si.sid,vid)
            numbers = self.readUrl(url)
            #print("makePlotData numbers ",len(numbers),numbers)
            for nn in numbers:
                # the first four ints are: nid,sid,iid and vid
                nns = nn.split(",")
                numiid = int(nns[2])
                #print("numiid, intervalsd = ",numiid,intervalsd)
                if numiid in intervalsd:
                    iis = intervalsd[numiid]
                    #print("adding number")
                    xx.data.append(dataItem( 
                        float(nns[4]),float(nns[5]),int(nns[6]),
                        int(iis[2]),int(iis[3]),
                        int(iis[4]),int(iis[5]),
                        iis[6],iis[7],si.version ))
            #print(intervals)
            #print(numbers)
            # get related intervals
        #    ssc = ss.replace(",","/").split("/")[]
        xx.checkData()
        return xx
#
#
#
