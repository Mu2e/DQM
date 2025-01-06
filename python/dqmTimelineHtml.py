import dash
from dash import dcc
from dash import html
import plotly.express as px
import pandas as pd
from dash.dependencies import Input, Output, State
import dqmTimelineData

class timelineConfig:
    def __init__(self,source='none', version=-1, value='none', 
                 showErrors=True, useTime=True):
        self.source = source
        self.sid = -1
        self.version = version
        self.value = value
        self.showErrors = showErrors
        self.useTime = useTime

class timelineHtml:

    def definePresets(self):
        self.presets = {}
        plotlist = []

        plotlist.append(timelineConfig())
        self.presets["1 plot"] = plotlist.copy()
        plotlist.clear()

        for ii in range(5):
            plotlist.append(timelineConfig())
        self.presets["5 plot"] = plotlist.copy()
        plotlist.clear()

        plotlist.append(timelineConfig(
            "valNightly/ceSimReco/day",-1,"ops/stats/CPU"))
        plotlist.append(timelineConfig(
            "valNightly/ceSimReco/day",-1,"ops/stats/MEM"))
        plotlist.append(timelineConfig(
            "valNightly/reco/day",-1,"ops/stats/CPU"))
        plotlist.append(timelineConfig(
            "valNightly/reco/day",-1,"ops/stats/MEM"))
        self.presets["valNightly"] = plotlist.copy()

        plotlist.clear()

        plotlist.append(timelineConfig(
            "test/strmA/file",-1,"det0/subgroup0/var0"))
        plotlist.append(timelineConfig(
            "test/strmA/file",-1,"det0/subgroup0/var1"))
        plotlist.append(timelineConfig(
            "test/strmB/file",-1,"det1/subgroup0/var2"))
        plotlist.append(timelineConfig(
            "test/strmB/file",-1,"det1/subgroup1/var3"))
        self.presets["test"] = plotlist.copy()


    def setPlotList(self,preset):
        self.plotlist = self.presets[preset].copy()
        ii = len(self.presets[preset])
        #while ii < self.maxPlots:
        #    self.plotlist.append(timelineConfig("none",-1,"none"))
        #    ii = ii +1


    def __init__(self):
        self.maxPlots = 30
        self.rangeSlider = True
        self.definePresets()
        self.preset = "1 plot"
        self.setPlotList(self.preset)
        self.dqmData = dqmTimelineData.timelineData()

    def buildHeader(self):
        return html.Center(html.H1('DQM Timeline Viewer'))
        #return html.Center(html.H1('DQM Timeline Viewer',style={
        #                       'background-color':'#EAEDED',
        #                       'border-radius':'20px','align-items':'center'}))

    def buildStyle(self):
        objs = []

        # create a little padding a the left
        objs.append( html.H4('',style={'padding-right':'3%'}) )

        presetOpts = []
        for key in self.presets:
            presetOpts.append( {'label' : key, 'value' : key } )
        #presetOpts.append( {'label' : '5 plots', 'value' : '5 plots' } )
        #presetOpts.append( {'label' : '10 plots', 'value' : '10 plots' } )
        #presetOpts.append( {'label' : 'valNightly', 'value' : 'valNightly' } )
        #presetOpts.append( {'label' : 'test', 'value' : 'test' } )
        #print("defining presetDD")
        pre = dcc.Dropdown(id="presetDD",options=presetOpts,
                           clearable=False,
                           value=self.preset,style={'width' : '120px'})
        prel = html.Label('Presets',style={'padding-left':'1%'})

        #nbx = dcc.Input(value='valNightly', type='text',style={'width' : '10%',
        #                                               'height' : '15pt'})
        #nlb = html.Label('Presets',style={'padding-left':'1%'})
        #objs.append(nbx)
        #objs.append(nlb)

        objs.append(pre)
        objs.append(prel)

        ri = dcc.Checklist( 
            id = 'rangeSlider',
            options=[
                {'label': 'RangeSliders', 'value': 'rangeSlider'}
            ],
            labelStyle={'display': 'inline-block'},
            style={'float': 'right','display': 'inline-block',
                   'padding-left':'3%'}, 
            value = ['rangeSlider']
        )

        objs.append(ri)

        objs.append( html.H4('',style={'padding-right':'50%'}) )

        rb = html.Button('Reload plots', id='reloadButton',
                         style={'background-color':'#AEB6Bf',
                                'border-radius':'10px'})
        objs.append(rb)

        objs.append( html.H4('',style={'padding-right':'3%'}) )

        return html.Div(children=objs, 
                        style={'display': 'flex', 'flex-direction': 'row',
                               'background-color':'#EAEDED',
                               'border-radius':'20px','align-items':'center'})




    #
    # make the timeline dropdown menu for the source
    #
    def buildTimelineDDSource(self,index=0):

        sindex = "{:02d}".format(index)
        config = self.plotlist[index]


        sou = ['none']
        for ss in self.dqmData.getMenuData().sources:
            if not ss.item in sou:
                sou.append(ss.item)

        sources = []
        for ss in sou:
            sources.append( {'label' : ss, 'value' : ss } )

        return sources


    #
    # make the timeline dropdown menu for the source version
    #
    def buildTimelineDDVersion(self,index=0):
        sindex = "{:02d}".format(index)
        config = self.plotlist[index]

        ver = [-1]
        for ss in self.dqmData.getMenuData().sources:
            #print("vers: ",config.source,ss.item)
            if config.source == 'none' or config.source == ss.item:
                #print("adding ver ",ss.version)
                if not ss.version in ver:
                    ver.append(ss.version)
        #print(ver)
        ver.sort(key = str)
        versions = []
        for v in ver:
            versions.append({'label':str(v),'value':v})
        #print("versionOG ",versions)

        return versions

    #
    # make the timeline dropdown menu for the value value
    #
    def buildTimelineDDValue(self,index=0):
        sindex = "{:02d}".format(index)
        config = self.plotlist[index]

        # the source may have several versions, need to consider them all

        sids = []
        for ss in self.dqmData.getMenuData().sources:
            if config.source=='none' or config.source == ss.item:
                if config.version==-1 or ss.version==config.version:
                    sids.append( ss.sid )

        # if the source is not 'none" and a sources id (sid)
        # has been determined, then only include the values 
        # that the source can provide
        matchingVids = []
        for sid in sids:
            matchingVids = matchingVids + self.dqmData.valuesForSource(sid)
        values=[{'label' : 'none', 'value' : 'none' }]
        for vv in self.dqmData.getMenuData().values:
            # source was none, then include all, 
            # else include only appropriate values
            if vv.vid in matchingVids:
                values.append( {'label' : vv.item, 'value' : vv.item } )

        return values


    #
    # make the timeline figure
    #
    def buildTimelineFigure(self,index=0):

        print("buildTimelineFigure ",index)

        sindex = "{:02d}".format(index)
        config = self.plotlist[index]


        # pandas dataframe
        data = []
        errors = []
        times = []
        runs = []
        markers = []
        if config.source != 'none' and config.value != 'none':
            tld = self.dqmData.makePlotData(config.source,
                                            config.version,config.value)
            #print("got tld data ",len(tld.data))
            for di in tld.data:
                data.append(di.number)
                errors.append(di.sigma)
                times.append(di.stime)
                runs.append(di.srun)
                markers.append(di.version)
                
        #print("times ",times)
        #print("times pd ", pd.to_datetime(times) )
        df = pd.DataFrame({'times':pd.to_datetime(times), 
                           'runs':pd.Series(runs), 
                           'data':pd.Series(data), 
                           'errors':pd.Series(errors),
                           'markers':pd.Series(markers)})
            
        #print("df ",df)
        # px is plotly express line graph
        error_name = None
        if config.showErrors:
            error_name = 'errors'

        x_name = 'runs'
        xaxis_title='run'
        if config.useTime:
            x_name = 'times'
            xaxis_title='time'

        #fig = px.line(df, x='times', y='data', 
        #                  symbol='markers', error_y=error_name)
        fig = px.scatter(df, x=x_name, y='data', 
                          symbol='markers', error_y=error_name)

        rangeselectorDict = {}
        if config.useTime:
            rangeselectorDict = dict(
                buttons=list([
                    dict(count=7, label="7d", step="day", stepmode="backward"),
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(step="all")
                ])
            )

        fig.update_xaxes(
            rangeslider_visible=self.rangeSlider,
            rangeselector = rangeselectorDict
        )
        fig.update_xaxes(showline=True, linewidth=2, linecolor='black', 
                         gridcolor='#D6DBDF')
        fig.update_yaxes(showline=True, linewidth=2, linecolor='black', 
                         gridcolor='#D6DBDF')

        fig.update_layout(
            xaxis_title=xaxis_title,
            yaxis_title=config.value,
            title=config.source,
            #title="Plot Title",
            #xaxis_title="X Axis Title",
            #yaxis_title="Y Axis Title",
            #legend_title="Legend Title",
            font=dict(
                family="Courier New, monospace",
                size=16,
                #color="RebeccaPurple"
            ),
            plot_bgcolor='#F8F9F9'
            #plot_bgcolor='#FFFFFF'
        )
        return fig


    def buildTimeline(self,index=0):
        # this will be a left box for menus, with vertical items
        # and a box on the right with the plot

        sindex = "{:02d}".format(index)
        config = self.plotlist[index]

        # source dropdown menu
        sources = self.buildTimelineDDSource(index)

        #print("source DD ","source"+sindex)
        sourcedd = dcc.Dropdown(
            id="source"+sindex,
            clearable=False,
            options=sources,
            value=config.source
        )


        # version dropdown menu
        versions = self.buildTimelineDDVersion(index)
        #print("version= ",versions,config.version)
        versiondd = dcc.Dropdown(
            id="version"+sindex,
            clearable=False,
            options=versions,
            value=config.version
        )


        # value dropdown menu
        values = self.buildTimelineDDValue(index)

        valuedd = dcc.Dropdown(
            id="value"+sindex,
            clearable=False,
            options=values,
            value=config.value
        )


        # optional checkboxes
        checklistValues = []
        if config.showErrors :
            checklistValues.append('showErrors')
        if config.useTime :
            checklistValues.append('useTime')
        plotcl = dcc.Checklist( 
            id = 'plotcl'+sindex,
            options=[
                {'label': 'showErrors', 'value': 'showErrors'},
                {'label': 'useTime', 'value': 'useTime'}
            ],
            style={'float': 'left','padding-left':'3%','padding-top':'20px'}, 
            labelStyle={'display': 'block'},
            #style={'float': 'left','display': 'inline-block',
            #       'padding-left':'3%'}, 
            value = checklistValues
        )

        fig = self.buildTimelineFigure(index)


        # the Dash core components object
        gr = dcc.Graph(
            id="timeline"+sindex,
            figure=fig
        )


        # one row with a left box for the drop menus, and the plot in right box
        hd = html.Div( [
            html.Div(
                [ html.Br(), html.Br(), html.Br(), 
                  "Source", sourcedd, 
                  "Version", versiondd, 
                  "Value", valuedd , plotcl
                 ],
                style={'width' : '15%'}
            ),
            html.Div( gr ,style={'float':'left','width' : '85%'})
            ], style={'display': 'flex', 'flex-direction': 'row'}
         )

        return hd



    def buildPlots(self):
        childs = []
        for ii in range(len(self.plotlist)):
            childs.append( self.buildTimeline(ii) )
        return childs

    def buildPage(self):
        childs = []
        childs.append( self.buildHeader() )
        childs.append( self.buildStyle() )
        plotsc = self.buildPlots()
        childs.append( html.Div(children=plotsc,id='plotsDiv') )
        return html.Div(children=childs)


    def callbacks(self, app):
        @app.callback(
        Output('plotsDiv','children'),
            Input('reloadButton', 'n_clicks'),
            State('presetDD','value'),
            State('rangeSlider','value') )
        def update_plotsDiv(reload,preset,ranges):
            print("plotsDiv callback ",reload,preset)
            self.preset = preset
            self.setPlotList(preset)
            self.rangeSlider = 'rangeSlider' in ranges
            return self.buildPlots()

        for ip0 in range(self.maxPlots):

            sip = "{:02d}".format(ip0)


            @app.callback(
                Output('value'+sip,'options'),
                Output('version'+sip,'options'),
                Output('value'+sip,'value'),
                Output('version'+sip,'value'),
                Input('source'+sip, 'value'),
                State('version'+sip,'value'),
                State('value'+sip,'value'),
                State('timeline'+sip,'id') )
            def update_value(source,version,value,name):
                ip = int(name[-2:])
                print('value callback ',ip,source,version,value)
                if ip >= len(self.plotlist):
                    raise dash.exceptions.PreventUpdate
                self.plotlist[ip].source = source

                valval = self.buildTimelineDDValue(ip)
                print('debugcallb ',ip,value,valval)
                found = False
                #print("value preloop")
                for vv in valval:
                    print("value in loop ",ip,vv['value'],value)
                    if vv['value'] == value:
                        print("value found true",ip)
                        found = True
                print("value mid ",ip,found)
                if not found:
                    value = 'none'
                self.plotlist[ip].value = value
                print("value mid",ip,value)

                verval = self.buildTimelineDDVersion(ip)
                found = False
                for vv in verval:
                    if vv['value'] == version:
                        found = True
                if not found:
                    version = -1
                self.plotlist[ip].version = version

                print("value callback result ",ip,valval,verval,value,version)
                return valval,verval,value,version


            @app.callback(
                Output('timeline'+sip,'figure'),
                Input('source'+sip, 'value'),
                Input('version'+sip, 'value'),
                Input('value'+sip, 'value'),
                Input('plotcl'+sip,'value'),
                State('timeline'+sip,'id') )
            def update_figure(source,version,value,plotcl,name):
                ip = int(name[-2:])
                #print("figure callback ",ip,name)
                # dash not define dctx = dash.callback_context
                if ip >= len(self.plotlist):
                    raise dash.exceptions.PreventUpdate
                print('figure callback ',ip,source,value)
                self.plotlist[ip].source = source
                self.plotlist[ip].version = version
                self.plotlist[ip].value = value
                self.plotlist[ip].showErrors = 'showErrors' in plotcl
                self.plotlist[ip].useTime = 'useTime' in plotcl
                return self.buildTimelineFigure(ip)




#    if n_clicks is None:
#        raise PreventUpdate
#    else:
#        return "Elephants are the only animal that can't jump"


    #        #return source, variable, make_tlfigure(dframes,source,variable)
    #        #return make_tlfigure(dframes,source,variable)

    #def callbacks(self, app):
    #    @app.callback(
    #    #Output('sourcelabel'+si,'children'),
    #    #Output('variablelabel'+si,'children'),
    #    Output('header', 'title'),
    #    #Input('source'+si, 'value'),
    #    Input('ReloadButton', 'value') )
    #    def update_graph0(reload):
    #        print("callb ",reload)
    #        return 'new title'
    #        #return source, variable, make_tlfigure(dframes,source,variable)
    #        #return make_tlfigure(dframes,source,variable)
