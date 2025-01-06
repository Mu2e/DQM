# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import dash
#from dash import dcc
#from dash import html
#import plotly.express as px
#import pandas as pd
from dash.dependencies import Input, Output

import dqmTimelineHtml

app = dash.Dash(__name__)

# set true so that we can define callbacks for items
# which might not be in all layouts
app.config.suppress_callback_exceptions = True

builder = dqmTimelineHtml.timelineHtml()

app.layout = builder.buildPage()
builder.callbacks(app)


#
# main
#
if __name__ == '__main__':
    app.run_server(debug=True)
