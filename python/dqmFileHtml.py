import dash
from dash import dcc
from dash import html
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dash.dependencies import Input, Output, State
import dqmFileData
import copy



class fileHtml:

    def definePresets(self):
        self.presets = {}

        plotlist = []
        plotlist.append({'path':'Validation/StepPointMCs_cosmicFilter_CRV/NStep','logY':False})
        plotlist.append({'path':'Validation/StepPointMCs_cosmicFilter_CRV/eTot2','logY':True})
        plotlist.append({'path':'Validation/StepPointMCs_cosmicFilter_CRV/ZCRV','logY':False})
        plotlist.append({'path':'Validation/CrvRecoPulses_CrvRecoPulses_noName/PE','logY':False})
        plotlist.append({'path':'Validation/CrvCoincidenceClusters_CrvCoincidenceClusterFinder_noName/PE','logY':False})
        self.presets["crv"] = plotlist.copy()

    def __init__(self):
        self.dqmData = dqmFileData.compFiles('s1.root','s2.root')
        self.nplots = len(self.dqmData.comps)
        self.preset = 'full'
        self.definePresets()

    def buildPageHeader(self):
        return html.Center(html.H1('DQM File Comparison Viewer'))

    #
    # build the box of selections at the top of the page
    # this is two vertical boxes
    # first the files seelction
    # second the style selection
    #
    def buildFileSelections(self):

        return html.H3('file selection',style={'padding-right':'3%'})


    #
    # build the box at the top of the page with the presets and style
    #
    def buildStyle(self):
        objs = []

        # create a little padding a the left
        objs.append( html.H4('',style={'padding-right':'3%'}) )

        presetOpts = []
        presetOpts.append( {'label' : 'full', 'value' : 'full' } )
        for key in self.presets:
            presetOpts.append( {'label' : key, 'value' : key } )
        print("debug preset ",self.preset)
        pre = dcc.Dropdown(id="presetDD",options=presetOpts,
                           clearable=False,
                           value=self.preset,
                           style={'width' : '150px',
                                  'font-size':'20px' })
        prel = html.Label('Presets',style={'padding-left':'20px',
                                           'margin-bottom':'0px','font-size':'25px'})

        objs.append(pre)
        objs.append(prel)

        return html.Div(children=objs, 
                        style={'display': 'flex', 'flex-direction':'row',
                               'align-items':'bottom'})


    #
    # combine the file selection box and the 
    # and the style/presets box into one, 
    # and add the reload page button
    #
    def buildPageSelections(self):
        leftPad = html.H4('',style={'padding-right':'3%'})
        objs = []
        #these are both html div objects
        objs.append( self.buildFileSelections() )
        objs.append( self.buildStyle() )
        leftbox = html.Div(children=objs)
        centerPad = html.H4('',style={'padding-right':'50%'})
        # the button to reload the page
        rb = html.Button('Reload plots', id='reloadButton',
                         style={'background-color':'#AEB6Bf',
                                'border-radius':'10px',
                               'font-size': '22px'})

        return html.Div(children=[leftPad, leftbox,centerPad,rb], 
                        style={'display': 'flex', 'flex-direction': 'row',
                               'background-color':'#EAEDED',
                               'border-radius':'20px','align-items':'center'})

        return [hfs,hps]

    def buildTextHeadings(self):
        childs = []
        childs.append( html.H3('',style={'width':'10%'}) )
        childs.append( html.H3('ks',style={'width':'5%'}) )
        childs.append( html.H3('frac',style={'width':'15%'}) )
        childs.append( html.H3('path',style={'width':'47%'}) )
        childs.append( html.H3('title',style={'width':'20%'}) )
        childs.append( html.H3('',style={'width':'13%'}) )
        return html.H3(children=childs,
                       style={'display': 'flex', 'flex-direction': 'row'})

    def buildFig(self, index, state=0):
        #print("buildFig",index,state)
        sindex = "{:03d}".format(index)

        comp = self.dqmData.comps[index]

        # ROOT objects
        th1 = comp.hist1.thist
        th2 = comp.hist2.thist

        title = comp.hist1.path
        xtitle = th1.GetTitle()

        kcolor = comp.compColor('ks')
        ktext = "KS={:7.5f}".format(comp.ks)
        fcolor = comp.compColor('fraction')
        ftext = "FR={:7.5f}".format(comp.fr)

        x = []
        y1 = []
        y2 = []
        y2e = []
        for ii in range(th1.GetNbinsX()):
            x.append(th1.GetBinCenter(ii+1))
            y1.append(th1.GetBinContent(ii+1))
            y2.append(th2.GetBinContent(ii+1))
            y2e.append(th2.GetBinError(ii+1))
            
        df = pd.DataFrame({'x':pd.Series(x),
                           'y1':pd.Series(y1), 
                           'y2':pd.Series(y2), 
                           'y2e':pd.Series(y2e)})
        #returns plotly.graph_objects.Figure
        #fig = px.histogram(df, x="x", y='y1',
        fig = px.bar(df, x="x", y='y1',
                     title=title,
                     labels={'x':xtitle,'y1':''}, 
                     #log_y=True, # represent bars with log scale
                     # color of histogram bars
                     color_discrete_sequence=['#BFC9CA'] 
               )
        fig.update_layout(bargap=0,plot_bgcolor='#F8F9F9',barmode='overlay')


        knote = {'xref':'paper','xanchor':'left','x':0.0,
                 'yref':'paper','yanchor':'bottom','y':1.0,
                 'text':ktext,'font':{'color':kcolor,'size':20},
                 'showarrow':False}
        fig.add_annotation(knote)
        fnote = {'xref':'paper','xanchor':'left','x':0.3,
                 'yref':'paper','yanchor':'bottom','y':1.0,
                 'text':ftext,'font':{'color':fcolor,'size':20},
                 'showarrow':False}
        fig.add_annotation(fnote)


        #fig2 = go.scatter(df, x='x', y='y2') 
        fig2 = go.Scatter(x=x, y=y2, 
                          error_y={'array':y2e,'color':'#C0392B','thickness':1,'width':0}, 
                          mode='markers',
                          marker={'color':'#C0392B','symbol':0,'size':5},
                          showlegend=False) 
        #fig2 = go.Bar(x=x, y=y2,opacity=0.1,marker_color='black')
        #fig2 = go.Bar(x=x, y=y2,opacity=0.1,marker_color='black',marker_symbol='circle')
                      #marker={'color':'black','size':2} ) 
                      #marker={'color':'black','size':2} ) 
                      #marker={'color':'black','symbol':0,'size':2} ) 
                      #symbol='markers', error_y=error_name)
        fig.add_trace(fig2)

        return fig

    #
    # build a row of a plot on left and log plot on right
    #
    def buildRowHists(self,index,state=0):

        #print("buildRow",index,state)
        sindex = "{:03d}".format(index)

        if state==0:
                return []

        fig = self.buildFig(index,state)
        gr = dcc.Graph(
            id="plot"+sindex,
            figure=fig
        )
        h1 = html.Div(children=gr,style={'width':'50%'})

        figl = copy.deepcopy(fig)
        figl.update_yaxes(type="log")

        grl = dcc.Graph(
            id="plotl"+sindex,
            figure=figl
        )
        h1l = html.Div(children=grl,style={'width':'50%'})
        
        childs = [h1,h1l]

        return childs


#fig = px.histogram(df, x="total_bill",
#                   title='Histogram of bills',
#                   labels={'total_bill':'total bill'}, # can specify one label per df column
#                   opacity=0.8,
#                   log_y=True, # represent bars with log scale
#                   color_discrete_sequence=['indianred'] # color of histogram bars
#                   )


    def buildRow(self, index):

        #print("buildRow",index)
        sindex = "{:03d}".format(index)

        comp = self.dqmData.comps[index]
        kcolor = comp.compColor('ks')
        ktext = "{:7.5f}".format(comp.ks)
        fcolor = comp.compColor('fraction')
        ftext = "{:7.5f}".format(comp.fr)

        ptext = comp.hist1.path
        ttext = comp.hist1.thist.GetTitle()

        #hks = html.Label(ktext)
        #hfr = html.Label(ftext)
        #hks = html.Label(ktext,style={'padding-left':'1%','font_color':kcolor})
        #hfr = html.Label(ftext,style={'padding-left':'1%','font_color':fcolor})
        hks = html.Label(ktext,style={'padding-left':'2%','color':kcolor})
        hfr = html.Label(ftext,style={'padding-left':'2%','color':fcolor})
        hpa = html.Label(ptext,style={'padding-left':'2%','width':'45%'})
        hti = html.Label(ttext,style={'padding-left':'2%','witdh':'10%'})
        #print("buildRow",ktext,ftext,kcolor,fcolor)

        sb = html.Button( 'show', id='show'+sindex,
                         style={'background-color':'#AEB6Bf',
                                'border-radius':'10px','width':'5%'})

        hr = html.Div( children=[sb,hks,hfr,hpa,hti], 
                       style={'display': 'flex', 'flex-direction': 'row'})

        figChilds = self.buildRowHists(index)
        hp = html.Div( children=figChilds, id='fig'+sindex,
                       style={'display': 'flex', 'flex-direction': 'row'})

        hx = html.Div( children=[hr,hp] )

        return hx


    def buildPlots(self):
        rows = []
        if self.preset == 'full':
            rows.append( self.buildTextHeadings() )
            for index in range(self.nplots):
                sindex = "{:03d}".format(index)
                rows.append( self.buildRow(index) )
        else:
            print('debug in alt ')
            nx=2
            width = "{:4.1f}%".format(100.0/nx)
            ix=0
            vchilds = []
            hchilds = []
            plotlist = self.presets[self.preset]
            print('debug nplot ',len(plotlist))
            for ip,comp in enumerate(self.dqmData.comps):
                found = False
                for pp in plotlist:
                    if pp['path'] == comp.hist1.path:
                        found = True
                        break
                if found:
                    print('debug i crv ',comp.hist1.path)
                    fig = self.buildFig(ip,1)
                    if pp['logY']:
                        fig.update_yaxes(type="log")
                    gr = dcc.Graph(figure=fig)
                    hh = html.Div(children=gr,style={'width':width})
                    ix = ix +1
                    hchilds.append(hh)
                    if ix == nx:
                        print("debug childs row",ip,ix,len(hchilds))
                        rows.append(html.Div(children=hchilds.copy(),
                            style={'display': 'flex', 'flex-direction': 'row'}))
                        ix = 0
                        hchilds.clear()
            # if there is a partialy-filled row
            if(len(hchilds)>0) :
                print("debug childs row",ip,ix,len(hchilds))
                rows.append( html.Div(children=hchilds.copy(),
                   style={'display': 'flex', 'flex-direction': 'row'}) )
        return rows

    def buildPage(self):
        #return self.buildPlots()
        childs = []
        childs.append( self.buildPageHeader() )
        childs.append( self.buildPageSelections() )
        # a list of html div's to be displayed vertically
        plotChilds = self.buildPlots()
        hp = html.Div( id='plotsDiv', children=plotChilds )
        childs.append( hp )
        
        hd = html.Div( children=childs ) 
        
        return hd

    def callbacks(self, app):

        @app.callback(
            Output('plotsDiv','children'),
            Input('reloadButton', 'n_clicks'),
            State('presetDD','value'),
            prevent_initial_call=True)
        def update_plots(nclicks,preset):
            print('callback update plots',preset)
            self.preset = preset
            return self.buildPlots()

        for ip0 in range(self.nplots):

            sip = "{:03d}".format(ip0)

            @app.callback(
                Output('fig'+sip,'children'),
                Output('show'+sip,'children'),
                Input('show'+sip, 'n_clicks'),
                State('fig'+sip,'id'),
                prevent_initial_call=True)
            def update_row(nclicks,name):
                ip = int(name[-3:])
                if ip%20 == 0:
                    print('show callback ',ip,nclicks)
                if nclicks==None:
                    nclicks = 0

                #if nclicks == 0:
                #    raise dash.exceptions.PreventUpdate

                if nclicks%2 == 0:
                    state = 0
                    buttonText = 'show'
                else:
                    state = 1
                    buttonText = 'hide'

                return self.buildRowHists(ip,state), [buttonText]

