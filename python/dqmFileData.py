import ROOT

verbose = 1
compStatus = {'perfect':0,'tight':1,'loose':2,'fail':3,'cantCompare':11};

class pars:
    def __init__(self):
        # 0 no scaling, 1=scale 2 to 1, 2=scale to given numbers 
        self.mode = 0
        # 0 = samples are expected identical, 1 = they are stat. independent
        self.indep = 0
        self.scale1 = 1.0
        self.scale2 = 1.0
        self.under = True
        self.over = True
        # TODO set correctly based on indep mode
        self.loose = 0.99
        self.tight = 0.999

class hist:
    def __init__(self,thist,path):
        self.thist = thist
        self.path = path
        self.type = thist.Class().GetName()

class file:

    def listHist(self):
        if verbose>0 :
            print("Processing file",self.filen)
        self.hists = []
        dirs = []
        dirs.append(self.file)
        while len(dirs)>0 :
            dd = dirs[0]
            dirs = dirs[1:]
            if verbose>5 :
                print("Processing Dir",dd.GetName())
            for kk in dd.GetListOfKeys():
                oo = dd.Get(kk.GetName())
                otype = oo.Class().GetName()
                if otype=='TDirectory' or otype=='TDirectoryFile':
                    dirs.append(oo)
                    if verbose>5 :
                        print("Queueing Dir",oo.GetName())
                elif otype in self.dTypes:
                    path = dd.GetPath().split(':')[1][1:]+'/'+oo.GetName()
                    self.hists.append(hist(oo,path))
                    if verbose>5 :
                        print("Adding hist",path)

    def __init__(self,filen):
        self.filen = filen
        self.file = ROOT.TFile(filen,"READONLY")
        self.dTypes = ['TH1F','TH1D','TProfile','TEfficiency','TH2F','TH2D']
        self.listHist()


class compHist:

    def __init__(self,hist1,hist2,pars):
        self.pars = pars
        self.status = 0
        self.hist1 = hist1
        self.hist2 = hist2
        self.ks = 0.0
        self.fr = 0.0
        self.sum1 = 0.0
        self.sum2 = 0.0
        self.empty = True
        self.compare()
        self.logY = False

    def compColor(self,test):
        x = self.ks
        if test == 'fraction' :
            x = self.fr
        if self.status == compStatus['perfect']:
            return '#196F3D'
        elif x > self.pars.tight :
            return '#2ECC71'
        elif x > self.pars.loose :
            return '#F4D03F'
        else:
            return '#E74C3C'

    def compare(self):
        print("compare ",self.hist1.path)
        self.status = 0
        h1 = self.hist1.thist
        h2 = self.hist2.thist
        if h1.GetNbinsX() != h2.GetNbinsX():
            return
        diff = False
        llim = 1
        if self.pars.under :
            llim = 0
        hlim = h1.GetNbinsX()
        if self.pars.over :
            hlim =  h1.GetNbinsX() + 1
        for i in range(llim,hlim+1):
            self.sum1 = self.sum1 + h1.GetBinContent(i)
            self.sum2 = self.sum2 + h2.GetBinContent(i)
            if h1.GetBinContent(i) != h2.GetBinContent(i):
                diff = True

        # TODO scaling modes go here

        if self.sum1==0.0 and self.sum2==0.0:
            self.empty = True
            self.ks = 1.0
            self.fr = 1.0
            self.status = compStatus['perfect']
            return

        if self.sum1==0.0 or self.sum2==0.0:
            self.empty = True
            self.fr = 0.0
        else:
            maxDiff = 0.0
            s1 = 0.0
            s2 = 0.0
            for ii in range(llim,hlim+1):
                s1 = s1 + self.pars.scale1*h1.GetBinContent(ii)
                s2 = s2 + self.pars.scale2*h2.GetBinContent(ii)
                dd = abs(s1-s2)
                if dd>maxDiff :
                    maxDiff = dd
            self.fr = 1.0 - maxDiff/s1
            if self.fr<0.0 :
                self.fr = 0.0

        if self.sum1==0.0 or self.sum2==0.0:
            self.ks = math.exp( -max(self.sum1,self.sum2) )
        else:
            qual = ''
            if self.pars.under :
                qual = qual + 'U'
            if self.pars.over :
                qual = qual + 'O'
            self.ks = h1.KolmogorovTest(h2,qual);

        self.status = compStatus['fail']
        if self.pars.indep == 0 :
            if self.fr > self.pars.loose or self.ks>self.pars.loose :
                self.status = compStatus['loose']
            if self.fr > self.pars.tight or self.ks>self.pars.tight :
                self.status = compStatus['tight']
        else:
            if self.ks>self.pars.loose :
                self.status = compStatus['loose']
            if self.ks>self.pars.tight :
                self.status = compStatus['tight']
        if not diff :
            self.status = compStatus['perfect']

        print("compare ",self.ks,self.fr,self.status)



class compFiles:

    def compare(self):
        self.comps = []
        n = 0
        for h1 in self.file1.hists:
            for h2 in self.file2.hists:
                #print(h1.path,h2.path)
                if h1.path == h2.path :
                    self.comps.append( compHist(h1,h2,self.pars) )
                    n = n + 1
        #print("check order 0 ",self.comps[0].hist1.path)
        #print("check order n ",self.comps[-1].hist1.path)

    def __init__(self,file1n,file2n):
        # 0 no scaling, 1=scale 2 to 1, 2=scale to given numbers 
        self.pars = pars()

        self.file1n = file1n
        self.file2n = file2n
        self.file1 = file(file1n)
        self.file2 = file(file2n)
        self.compare()
