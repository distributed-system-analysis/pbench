# Copyright 2018 The MLPerf Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================

import os
import re
import csv
import sys
import json
import argparse

# Third-party modules
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.express       as pex
import plotly.graph_objects as pgo
import dateutil.parser
import pandas
import numpy

from dash.dependencies import Input, Output, State, ALL
from datetime import datetime, timedelta
from collections import defaultdict

# Global Variables -- User Modifiable
#   g_power_window*   : how much time before (BEGIN) and after (END) loadgen timestamps to show data in graph
g_power_window_before_add_td = timedelta(seconds=0)
g_power_window_before_sub_td = timedelta(seconds=30)
g_power_window_after_add_td  = timedelta(seconds=30)
g_power_window_after_sub_td  = timedelta(seconds=0)

# Global Variables -- Do not modify
g_power_add_td               = timedelta(seconds=0)
g_power_sub_td               = timedelta(seconds=0)
g_loadgen_data               = defaultdict(dict)
g_graph_data                 = defaultdict(dict)
g_figures                    = defaultdict(dict)
g_verbose                    = False

app = dash.Dash(__name__)

# Check command-line parameters and call respective functions
def main():

    m_args = f_parseParameters()

    if( m_args.loadgen_in != "" ):
        f_parse_Loadgen( m_args.loadgen_in, m_args.loadgen_out, m_args.workload )

    if( m_args.specpower_in != "" ):
        f_parse_SPECPowerlog( m_args.specpower_in, m_args.powerlog_out )

    if( m_args.stats is not None and m_args.loadgen_out != "" and m_args.powerlog_out != "" ):
        f_stats( m_args.loadgen_out, m_args.powerlog_out, m_args.stats, m_args.csv )
        
    if( m_args.graph is not None and m_args.loadgen_out != "" and m_args.powerlog_out != "" ):
        f_graph( m_args.loadgen_out, m_args.powerlog_out, m_args.graph )

        
def f_stats( p_loadgen_csv, p_power_csv, p_filter , p_stats_csv ):
    m_loadgen_data = pandas.DataFrame()
    m_power_data   = pandas.DataFrame()
   
    if( p_stats_csv ):
        m_stats_frame  = pandas.DataFrame( columns=['Run',
                                                    'Workload',
                                                    'Scenario',
                                                    'Mode',
                                                    'Begin Time',
                                                    'End Time',
                                                    'Runtime',
                                                    'Samples',
                                                    'Data',
                                                    'Minimum',
                                                    'Maximum',
                                                    'Average',
                                                    'Std.Dev'] )

    # Open loadgen data
    try:
        if( g_verbose ) : print( f"stats: opening {p_loadgen_csv} for reading" )
        m_loadgen_data = pandas.read_csv( p_loadgen_csv )
    except:
        print( f"stats: error opening file: {p_loadgen_csv}" )
        exit(1)

    # Open power data
    try:
        if( g_verbose ) : print( f"stats: opening {p_power_csv} for reading" )
        m_power_data = pandas.read_csv( p_power_csv )
    except:
        print( f"stats: error opening file: {p_power_csv}",  )
        exit(1)
        
    # Combine Date/Time and drop Time
    m_power_data['Date'] = m_power_data['Date'] + " " + m_power_data['Time']
    m_power_data.rename( columns = {'Date' : 'Datetime'}, inplace = True )
    m_power_data['Datetime'] = pandas.to_datetime( m_power_data['Datetime'] )
    m_power_data = m_power_data.drop( columns=['Time'] )
    m_power_data.set_index( 'Datetime' )

    m_dataset_count = 0
    
    if( g_verbose ) : print( "stats: loading and parsing data, please wait" )

    for index, m_loadgen_entry in m_loadgen_data.iterrows():
        m_power_ts_begin = dateutil.parser.parse( m_loadgen_entry['System Begin Date'] + " " + m_loadgen_entry['System Begin Time'] )
        m_power_ts_end   = dateutil.parser.parse( m_loadgen_entry['System End Date']   + " " + m_loadgen_entry['System End Time']   )

        m_mask_stats = (m_power_data['Datetime'] >= (m_power_ts_begin + g_power_add_td - g_power_sub_td )) & \
                       (m_power_data['Datetime'] <= (m_power_ts_end   + g_power_add_td - g_power_sub_td ))

        m_dataframe = m_power_data.loc[m_mask_stats].copy()
        
        if( m_dataframe.empty ):
            continue
        else:
            m_dataset_count += 1

        if( p_stats_csv ) :
            m_stats_list = []
        
            for m_header in list(m_dataframe) :
                if( p_filter and not re.findall(r"("+'|'.join(p_filter)+r")", m_header) ):
                    continue
                    
                m_data = m_dataframe[m_header]
                
                if( m_data.dtypes not in [numpy.int64, numpy.float64] ):
                    continue
                    
                m_stats_list.append( { 'Run'        : m_dataset_count,
                                       'Workload'   : m_loadgen_entry['Workload'],
                                       'Scenario'   : m_loadgen_entry['Scenario'],
                                       'Mode'       : m_loadgen_entry['Mode'],
                                       'Begin Time' : f"{m_power_ts_begin}",
                                       'End Time'   : f"{m_power_ts_end}",
                                       'Runtime'    : f"{m_power_ts_end - m_power_ts_begin}",
                                       'Metric'     : m_loadgen_entry['Metric'],
                                       'Score'      : m_loadgen_entry['Score'],
                                       'Samples'    : m_dataframe.shape[0],
                                       'Data'       : m_header,
                                       'Minimum'    : f"{m_data.min():.3f}",
                                       'Maximum'    : f"{m_data.max():.3f}",
                                       'Average'    : f"{m_data.mean():.3f}",
                                       'Std.Dev'    : f"{m_data.std():.3f}" } )
                if( re.search( "watts?|power", m_header, re.I ) ):
                    m_stats_list[-1].update( {'Energy' : f"{ float(m_stats_list[-1]['Average']) * (dateutil.parser.parse(m_stats_list[-1]['End Time']) - dateutil.parser.parse(m_stats_list[-1]['Begin Time'])).total_seconds():.3f}"} )

            m_stats_frame = m_stats_frame.append( pandas.DataFrame( m_stats_list ) )

        else:
            print( f"Run:        {m_dataset_count}\n" +
                   f"Workload:   {m_loadgen_entry['Workload']}\n" +
                   f"Scenario:   {m_loadgen_entry['Scenario']}\n" +
                   f"Mode:       {m_loadgen_entry['Mode']}\n" +
                   f"Begin Time: {m_loadgen_entry['System Begin Date']} {m_loadgen_entry['System Begin Time']}\n" +
                   f"End Time:   {m_loadgen_entry['System End Date']} {m_loadgen_entry['System End Time']}\n" +
                   f"Runtime:    {(m_power_ts_end - m_power_ts_begin)}\n" +
                   f"Metric:     {m_loadgen_entry['Metric']}\n" +
                   f"Score:      {m_loadgen_entry['Score']}\n" +
                   f"Samples:    {m_dataframe.shape[0]}\n" )
                   
            for m_header in list(m_dataframe) :
                if( p_filter and not re.findall(r"("+'|'.join(p_filter)+r")", m_header) ):
                    continue
                
                m_data = m_dataframe[m_header]
                
                if( m_data.dtypes not in [numpy.int64, numpy.float64] ):
                    #if( g_verbose ) : print( f"stats: {m_header} dtype is {m_data.dtypes}" )
                    continue
                
                print( f"Data:       {m_header}\n" + 
                       f"Minimum:    {m_data.min():.3f}\n" +
                       f"Maximum:    {m_data.max():.3f}\n" +
                       f"Average:    {m_data.mean():.3f}\n" +
                       f"Std.Dev:    {m_data.std():.3f}\n" )
                       
                if( re.search( "\bwatts?\b|\bpower\b", m_header, re.I ) ):
                    print( f"Energy:     {(m_data.mean() * (m_power_ts_end - m_power_ts_begin).total_seconds()):.3f}\n" )

    if( g_verbose ) : print( f"stats: {m_dataset_count} entries parsed" )

    if( not m_dataset_count ):
        print( "*** ERROR: no data collated!" )
        print( "           check loadgen and data timestamps for timing mismatches and/or use --deskew [seconds] to realign" )
        exit(1)

    if( p_stats_csv ):
        try:
            if( g_verbose ) : print( f"stats: saving stats to {p_stats_csv}\n" )
            m_stats_frame.to_csv( p_stats_csv, index=False )
        except:
            print( f"stats: error while creating csv output file: {p_stats_csv}" )
            exit(1)

    

#### Graph data over time
####  Parses the loadgen data for BEGIN and END times
####  Parses the power data (or any CSV data with a header) and tries to plot over time
def f_graph( p_loadgen_csv, p_power_csv, p_filter ):
    m_loadgen_data = pandas.DataFrame()
    m_graph_data   = pandas.DataFrame()

    # Open loadgen data
    try:
        if( g_verbose ) : print( f"graph: opening {p_loadgen_csv} for reading" )
        m_loadgen_data = pandas.read_csv( p_loadgen_csv )
    except:
        print( f"graph: error opening file: {p_loadgen_csv}" )
        exit(1)

    # Open power/raw data
    try:
        if( g_verbose ) : print( f"graph: opening {p_power_csv} for reading" )
        m_graph_data = pandas.read_csv( p_power_csv )
    except:
        print( f"graph: error opening file: {p_power_csv}",  )
        exit(1)

    # Combine Date/Time and drop Time
    m_graph_data['Date'] = m_graph_data['Date'] + " " + m_graph_data['Time']
    m_graph_data.rename( columns = {'Date' : 'Datetime'}, inplace = True )
    m_graph_data['Datetime'] = pandas.to_datetime( m_graph_data['Datetime'] )
    m_graph_data = m_graph_data.drop( columns=['Time'] )
    m_graph_data.set_index( 'Datetime' )

    m_dataset_count = 0
    
    if( g_verbose ) : print( "graph: Loading and parsing data, please wait" )

    for index, m_loadgen_entry in m_loadgen_data.iterrows():
        m_power_ts_begin = dateutil.parser.parse( m_loadgen_entry['System Begin Date'] + " " + m_loadgen_entry['System Begin Time'] )
        m_power_ts_end   = dateutil.parser.parse( m_loadgen_entry['System End Date']   + " " + m_loadgen_entry['System End Time'] )

        m_mask_stats = (m_graph_data['Datetime'] >= (m_power_ts_begin + g_power_add_td - g_power_sub_td )) & \
                       (m_graph_data['Datetime'] <= (m_power_ts_end   + g_power_add_td - g_power_sub_td ))
        m_mask_graph = (m_graph_data['Datetime'] >= (m_power_ts_begin + g_power_add_td - g_power_sub_td + g_power_window_before_add_td - g_power_window_before_sub_td )) & \
                       (m_graph_data['Datetime'] <= (m_power_ts_end   + g_power_add_td - g_power_sub_td + g_power_window_after_add_td  - g_power_window_after_sub_td  ))

        m_dataframe = m_graph_data.loc[m_mask_graph].copy()
        if( m_dataframe.empty or m_graph_data.loc[m_mask_stats].empty ):
            continue

        for m_header in m_graph_data.columns[1:] :

            if( not re.findall(r"("+'|'.join(p_filter)+r")", m_header) ):
                continue
        
            if( not g_figures[m_header] ):
                g_figures[m_header] = pgo.Figure()
                g_figures[m_header].update_layout( title={'text'   : f'{m_header} vs. Time',
                                                          'x'      : 0.5,
                                                          'y'      : 0.95,
                                                          'xanchor': 'center',
                                                          'yanchor': 'top' },
                                                    xaxis_title="Time (offset between powerlog & loadgen timestamps)",
                                                    xaxis_tickformat='%H:%M:%S.%L',
                                                    yaxis_title=f"{m_header}" )

            # Zero the timescale to difference between loadgen and data timestamps
            # Zero'ing causes datetime to be a timedelta, add an "arbitrary" date to convert back into datetime
            m_dataframe.loc[:,'Datetime'] -= m_dataframe['Datetime'].iloc[0]
            m_dataframe.loc[:,'Datetime'] += datetime( 2011, 1, 13 )

            g_figures[m_header].add_trace( pgo.Scatter( x=m_dataframe['Datetime'],
                                                        y=m_dataframe[m_header],
                                                        mode="lines+markers",
                                                        line=dict(color=pex.colors.qualitative.Plotly[m_dataset_count%len(pex.colors.qualitative.Plotly)]),
                                                        marker=dict(color=pex.colors.qualitative.Plotly[m_dataset_count%len(pex.colors.qualitative.Plotly)]),
                                                        name=f"run {m_dataset_count}, {m_loadgen_entry['Workload']}, {m_loadgen_entry['Scenario']}, {m_loadgen_entry['Mode']}",
                                                        visible=True ) )

            # Draw the loadgen runtime below the graph
            g_figures[m_header].add_vrect( x0=m_graph_data.loc[m_mask_stats]['Datetime'].iloc[0]  - m_graph_data.loc[m_mask_graph]['Datetime'].iloc[0] + datetime( 2011, 1, 13 ),
                                           x1=m_graph_data.loc[m_mask_stats]['Datetime'].iloc[-1] - m_graph_data.loc[m_mask_graph]['Datetime'].iloc[0] + datetime( 2011, 1, 13 ),
#                                           y1=m_graph_data.loc[m_mask_stats][m_header].max(),
                                           fillcolor=pex.colors.qualitative.Plotly[m_dataset_count%len(pex.colors.qualitative.Plotly)],
                                           opacity=0.20,
                                           layer="below",
                                           line_width=0,
#                                           annotation_text=f"loadgen range for run {m_dataset_count}", #, {m_loadgen_entry['Workload']}, {m_loadgen_entry['Scenario']}, {m_loadgen_entry['Mode']}",
#                                           annotation_position="bottom left",
                                           visible=True )

        g_graph_data[m_dataset_count] = m_graph_data.loc[m_mask_stats]
        g_loadgen_data[m_dataset_count] = m_loadgen_entry

        m_dataset_count += 1

    if( g_verbose ) : print( "graph: data parsing complete.  building components" )

    # Build list of graphs, dropdown options
    m_dcc_graphs = []
    m_dcc_dropdown = []
    m_counter = 0
    for m_key in g_figures :
        m_dcc_graphs.append( dcc.Graph( id={ 'type' : 'graph-obj',
                                             'data' : f'{m_key}',
                                             'index': m_counter },
                                        figure=g_figures[m_key],
                                        style ={'height':'70vh',
                                                'display':'none'} ) )
        m_dcc_dropdown.append( {'label':f'{m_key}', 'value':m_counter } )
        m_counter += 1
        
    if( not m_counter ):
        print( "*** ERROR: No data collated!" )
        print( "           Check loadgen and data timestamp for timing mismatches and/or use --deskew [seconds] to realign" )
        exit(1)
        
    app.layout = html.Div([
                      html.Div( id="div-filter-options", children=[
                           html.Div( ["Filter Dataset by Keywords (i.e. 'resnet ssd-large'): ", dcc.Input(id='input-box-filter-by-keywords', type='text') ] ),
                           html.Div( ["Filter Dataset by Run IDs (i.e. '1, 2, 3-9'): ",         dcc.Input(id='input-box-filter-by-run-id',   type='text') ] ),
                           html.Div( ["Graph selection: ", dcc.Dropdown(id='dropdown-graph-select',
                                                                        options=m_dcc_dropdown,
                                                                        value=m_dcc_dropdown[0]['value'],
                                                                        clearable=False,
                                                                        searchable=False) ] )
                           ]),
                      html.Div( id="div-graphs-area", children=m_dcc_graphs ),
                      html.Div( id="div-stats-area", children=[
                           html.P( html.B( id="div-loadgen-stats-title", children=["- Hide Loadgen Statistics & Info"], n_clicks=0, style={'cursor':'pointer'} ) ), 
                           html.Div( id="div-stats-area-loadgen",  style={'display':'block'}, children=[
                                html.Table( id="table-loadgen-stats", children=[] ),
                                html.Div( id="div-loadgen-stats-trigger", children=['0'], style={'display':'none' } ),
                                ]),
                           html.Hr(),
                           html.Div( id="div-stats-area-selected", children=[
                                html.P( id="div-selected-stats-infobox", children=[
                                   html.B( children=["Selected Data Statistics & Info"] ), " (use either box or lasso select for statistical information of selection)"] ),
                                html.Table( id="table-selected-stats", children=[] ),
                                html.Div( id="div-selected-stats-trigger", children=['0'], style={'display':'none' } ),
                                ])
                           ])
                     ])

#### Callbacks
####  Dropdown Menu Hanlding
    @app.callback([Output( {'type': 'graph-obj', 'data': ALL, 'index': ALL }, 'style' ),
                   Output( 'input-box-filter-by-keywords', 'value' ),
                   Output( 'input-box-filter-by-run-id',   'value' )],
                  [Input( 'dropdown-graph-select', 'value' )],
                  [State( {'type': 'graph-obj', 'data': ALL, 'index': ALL }, 'style' )])
    def f_dash_updateGraph( p_dropdown_value, s_graph_obj_styles ):
    
        for m_style in s_graph_obj_styles:
            m_style['display'] = 'none'
        s_graph_obj_styles[p_dropdown_value]['display'] = 'block'

        return [ s_graph_obj_styles, "", "" ]

#### Filtering by keywords/run ID
####   Also triggers loadgen stats function to be called
    @app.callback([Output( {'type': 'graph-obj', 'data': ALL, 'index': ALL }, 'figure' ),
                   Output( 'div-loadgen-stats-trigger', 'children' ),
                   Output( 'div-selected-stats-trigger', 'children' )],
                  [Input(  'input-box-filter-by-keywords', 'value'),
                   Input(  'input-box-filter-by-run-id',   'value'),
                   Input( { 'type':'graph-obj', 'data': ALL, 'index': ALL }, 'restyleData' )],
                  [State( {'type': 'graph-obj', 'data': ALL, 'index': ALL }, 'figure'),
                   State( 'div-loadgen-stats-trigger', 'children' ),
                   State( 'div-selected-stats-trigger', 'children' ),
                   State( 'dropdown-graph-select', 'value' )] )
    def f_dash_filterDatasets( p_filter_keywords, p_filter_run_id, p_restyleData, s_graph_obj_figures, s_loadgen_trigger, s_selected_trigger, s_graph_select ):

        m_ctx = dash.callback_context
        ( m_trigger_obj, m_trigger_src ) = m_ctx.triggered[0]['prop_id'].rsplit('.', 1)

        if( m_trigger_src == 'restyleData' ):
            for m_iter in range(0,len(p_restyleData[s_graph_select][1])) :
                (m_state, m_run) = (p_restyleData[s_graph_select][0], p_restyleData[s_graph_select][1])

                if( m_state['visible'][m_iter] == 'legendonly' ) :
                    s_graph_obj_figures[s_graph_select]['data'][m_run[m_iter]]['visible'] = 'legendonly'
                    s_graph_obj_figures[s_graph_select]['layout']['shapes'][m_run[m_iter]]['visible'] = False
                elif( m_state['visible'][m_iter] == True ) :
                    s_graph_obj_figures[s_graph_select]['data'][m_run[m_iter]]['visible'] = True
                    s_graph_obj_figures[s_graph_select]['layout']['shapes'][m_run[m_iter]]['visible'] = True
                else:
                    print( f"*** ERROR: restyleData = {p_restyleData}" )

            return [ s_graph_obj_figures, s_loadgen_trigger, s_selected_trigger ]

        m_filter_keywords = ""
        m_filter_run_id   = ""

        if( (p_filter_keywords != None) and (p_filter_keywords.strip() != "") ):
            m_filter_keywords = '|'.join( p_filter_keywords.split() )

        if( (p_filter_run_id != None) and (p_filter_run_id.strip() != "") ):
            for m_run_id in re.split( "[,\s]", p_filter_run_id):
                if( re.search( "^\d+-\d+$", m_run_id ) ):
                    if( m_filter_run_id != "" ):
                        m_filter_run_id += '|'
                    (m_lo, m_hi) = re.search( "^(\d+)-(\d+)$", m_run_id ).groups()
                    m_filter_run_id += '|'.join( str(m_int) for m_int in range( int(m_lo),int(m_hi)+1 ) )
                elif( re.search( "^\d+$", m_run_id) ):
                    if( m_filter_run_id != "" ):
                        m_filter_run_id += '|'
                    m_filter_run_id += f"{m_run_id}"

        m_filter_run_id = re.sub( "(\d+)", r"\\s*\1\\s*", m_filter_run_id )

        m_figure = s_graph_obj_figures[s_graph_select]
        for (m_dataset, m_shapes) in zip(m_figure['data'], m_figure['layout']['shapes']):
            if( (re.search( m_filter_run_id, m_dataset['name'], re.I )) and (re.search( m_filter_keywords, m_dataset['name'], re.I )) ):
                m_dataset['visible'] = True
                m_shapes['visible']  = True
            else:
                m_dataset['visible'] = "legendonly"
                m_shapes['visible']  = False

        return [ s_graph_obj_figures, not s_loadgen_trigger, not s_selected_trigger ]

        
#### Toggle visibility of loadgen stats table        
    @app.callback([Output( 'div-stats-area-loadgen', 'style' ),
                   Output( 'div-loadgen-stats-title', 'children' )], 
                   [Input( 'div-loadgen-stats-title', 'n_clicks' )] )
    def f_dash_toggleLoadgenStats( p_n_clicks ):
    
        if( p_n_clicks % 2 ):
            return [{ 'display' : 'none'  }, "+ Loadgen Statistics & Info"]
        else:
            return [{ 'display' : 'block' }, "- Loadgen Statistics & Info"]
    
    
#### Generate selection stats table
    @app.callback([Output( 'table-selected-stats', 'children'),
                   Output( 'div-selected-stats-infobox', 'style' )],
                  [Input( { 'type':'graph-obj', 'data': ALL, 'index': ALL }, 'selectedData' ),
                   Input( { 'type':'graph-obj', 'data': ALL, 'index': ALL }, 'restyleData' ),
                   Input( 'div-selected-stats-trigger', 'children' ),
                   Input( 'dropdown-graph-select', 'value' )],
                  [State( { 'type':'graph-obj', 'data': ALL, 'index': ALL }, 'figure' ),
                   State( 'dropdown-graph-select', 'value' )] )
    def f_dash_generateSelectedStats( p_selectedData, p_restyleData, p_dummy_trigger, p_dummy_dropdown, s_graph_obj_figures, s_dropdown_graph_select ):
    
        m_ctx = dash.callback_context
        ( m_trigger_obj, m_trigger_src ) = m_ctx.triggered[0]['prop_id'].rsplit('.', 1)

        if( not m_ctx.triggered or m_trigger_obj in ['div-selected-stats-trigger', 'dropdown-graph-select'] or m_trigger_src == 'restyleData' ):
            return [ [], {'display':'block'} ]

        m_figure = s_graph_obj_figures[s_dropdown_graph_select]

        m_table_run_id     = [ html.Th( "Run"      ) ]
        m_table_workload   = [ html.Th( "Workload" ) ]
        m_table_scenario   = [ html.Th( "Scenario" ) ]
        m_table_run_mode   = [ html.Th( "Mode"     ) ]
        m_table_samples    = [ html.Th( "Samples"  ) ]
        m_table_timedelta  = [ html.Th( "Timedelta") ]
        m_table_min        = [ html.Th( "Minimum"  ) ]
        m_table_max        = [ html.Th( "Maximum"  ) ]
        m_table_average    = [ html.Th( "Average"  ) ]
        m_table_dev        = [ html.Th( "Std.Dev"  ) ]

        if( re.search( "\bwatts?\b|\bpower\b", m_figure['layout']['yaxis']['title']['text'], re.I ) ):
        #if( m_figure['layout']['yaxis']['title']['text'] == 'Watts' ):
            m_table_energy = [ html.Th( "Energy"   ) ]
        
        m_dataframes       = defaultdict(dict)
        
        if( p_selectedData and p_selectedData[s_dropdown_graph_select] is not None ):
            for m_point in p_selectedData[s_dropdown_graph_select]['points'] :
            
                if( s_graph_obj_figures[s_dropdown_graph_select]['data'][m_point['curveNumber']]['visible'] != True ):
                    continue
                    
                if( m_point['curveNumber'] not in m_dataframes ):
                    m_dataframes[m_point['curveNumber']]['name'] = s_graph_obj_figures[s_dropdown_graph_select]['data'][m_point['curveNumber']]['name']
                    m_dataframes[m_point['curveNumber']]['data'] = s_graph_obj_figures[s_dropdown_graph_select]['layout']['yaxis']['title']['text']
                    m_dataframes[m_point['curveNumber']]['dataframe'] = pandas.DataFrame( {'x':[m_point['x']], 'y':[m_point['y']] } )
                else:    
                    m_dataframes[m_point['curveNumber']]['dataframe'] = m_dataframes[m_point['curveNumber']]['dataframe'].append( {'x':m_point['x'], 'y':m_point['y'] }, ignore_index=True )

            if( not m_dataframes ):
                return [ [], {'display':'block'} ]
                
            for m_key in m_dataframes:
                m_frame = m_dataframes[m_key]['dataframe']
                (m_run_id, m_workload, m_scenario, m_run_mode) = m_dataframes[m_key]['name'].split(", ")
                
                m_table_run_id.append( html.Td( f"{m_run_id}" ) )
                m_table_workload.append( html.Td( f"{m_workload}" ) )
                m_table_scenario.append( html.Td( f"{m_scenario}" ) )
                m_table_run_mode.append( html.Td( f"{m_run_mode}" ) )
                m_table_samples.append( html.Td( f"{m_frame.shape[0]}" ) )
                m_duration = dateutil.parser.parse(m_frame['x'].max()) - dateutil.parser.parse(m_frame['x'].min())
                m_table_timedelta.append( html.Td( f"{(datetime(2011, 1, 13) + m_duration).strftime('%H:%M:%S.%f')[:-3]}" ) )

                if( numpy.issubdtype(m_frame['y'].dtype, numpy.number ) ):
                    m_table_average.append( html.Td( f"{m_frame['y'].mean():.3f}" ) )
                    m_table_min.append( html.Td( f"{m_frame['y'].min():.3f}" ) )
                    m_table_max.append( html.Td( f"{m_frame['y'].max():.3f}" ) )
                    m_table_dev.append( html.Td( f"{m_frame['y'].std():.3f}" ) )
                else:  
                    m_table_average.append( html.Td( "n/a" ) )
                    m_table_min.append( html.Td( "n/a" ) )
                    m_table_max.append( html.Td( "n/a" ) )
                    m_table_dev.append( html.Td( "n/a" ) )
                
                if( re.search( "watts?|power", m_dataframes[m_key]['data'], re.I ) ):
                    m_table_energy.append( html.Td( f"{(m_frame['y'].mean() * (m_duration.seconds + m_duration.microseconds / 1000000)):.3f}" ) )
                
                   
            m_ret = [ html.Tr( m_table_run_id   ),
                      html.Tr( m_table_workload ),
                      html.Tr( m_table_scenario ),
                      html.Tr( m_table_run_mode ),
                      html.Tr( m_table_samples  ),
                      html.Tr( m_table_timedelta),
                      html.Tr( m_table_min      ),
                      html.Tr( m_table_max      ),
                      html.Tr( m_table_average  ),
                      html.Tr( m_table_dev      ) ]

            if( re.search( "watts?|power", m_dataframes[m_key]['data'], re.I ) ):
                m_ret.append( html.Tr( m_table_energy  ) )
                
            return [ m_ret, {'display':'block'} ]
            
        return [ [], {'display':'block'} ]

            
#### Generate loadgen stats table
    @app.callback(Output( 'table-loadgen-stats', 'children' ),
                  [Input( 'dropdown-graph-select', 'value' ),
                   Input( 'div-loadgen-stats-trigger', 'children' ),
                   Input( { 'type':'graph-obj', 'data': ALL, 'index': ALL }, 'restyleData' )],
                  [State( { 'type':'graph-obj', 'data':ALL, 'index':ALL }, 'figure' )] )
    def f_dash_generateLoadgenStats( p_dropdown_graph_select, p_dummy_trigger, p_dummy_restyle, s_graph_obj_figures ):
    
        m_figure = s_graph_obj_figures[p_dropdown_graph_select]

        m_table_run_id     = [ html.Th( "Run"    ) ]
        m_table_workload   = [ html.Th( "Workload" ) ]
        m_table_scenario   = [ html.Th( "Scenario" ) ]
        m_table_run_mode   = [ html.Th( "Mode"     ) ]
        m_table_metric     = [ html.Th( "Metric"   ) ]
        m_table_score      = [ html.Th( "Score"    ) ]
        m_table_samples    = [ html.Th( "Samples"  ) ]
        m_table_duration   = [ html.Th( "Duration" ) ]
        m_table_min        = [ html.Th( "Minimum"  ) ]
        m_table_max        = [ html.Th( "Maximum"  ) ]
        m_table_average    = [ html.Th( "Average"  ) ]
        m_table_dev        = [ html.Th( "Std.Dev"  ) ]
        
        if( m_figure['layout']['yaxis']['title']['text'] == 'Watts' ):
            m_table_energy = [ html.Th( "Energy"   ) ]

        m_iter = 0
        for m_dataset in s_graph_obj_figures[p_dropdown_graph_select]['data'] :
            if( m_dataset['visible'] == True ):
                (m_run_id, m_workload, m_scenario, m_run_mode) = m_dataset['name'].split(", ")
                
                m_table_run_id.append( html.Td( f"{m_run_id}" ) )
                m_table_workload.append( html.Td( f"{m_workload}" ) )
                m_table_scenario.append( html.Td( f"{m_scenario}" ) )
                m_table_run_mode.append( html.Td( f"{m_run_mode}" ) )
                m_table_metric.append( html.Td( f"{g_loadgen_data[m_iter]['Metric']}" ) )
                m_table_score.append( html.Td( f"{g_loadgen_data[m_iter]['Score']}" ) )
                m_table_samples.append( html.Td( f"{g_graph_data[m_iter].shape[0]}" ) )
                m_duration = g_graph_data[m_iter]['Datetime'].max() - g_graph_data[m_iter]['Datetime'].min()
                m_table_duration.append( html.Td( f"{(datetime(2011, 1, 13) + m_duration).strftime('%H:%M:%S.%f')[:-3]}" ) )

                if( numpy.issubdtype(g_graph_data[m_iter][m_figure['layout']['yaxis']['title']['text']].dtype, numpy.number ) ):
                    m_table_average.append( html.Td( f"{g_graph_data[m_iter][m_figure['layout']['yaxis']['title']['text']].mean():.3f}" ) )
                    m_table_min.append( html.Td( f"{g_graph_data[m_iter][m_figure['layout']['yaxis']['title']['text']].min():.3f}" ) )
                    m_table_max.append( html.Td( f"{g_graph_data[m_iter][m_figure['layout']['yaxis']['title']['text']].max():.3f}" ) )
                    m_table_dev.append( html.Td( f"{g_graph_data[m_iter][m_figure['layout']['yaxis']['title']['text']].std():.3f}" ) )
                else:  
                    m_table_average.append( html.Td( "n/a" ) )
                    m_table_min.append( html.Td( "n/a" ) )
                    m_table_max.append( html.Td( "n/a" ) )
                    m_table_dev.append( html.Td( "n/a" ) )
                
                
                if( m_figure['layout']['yaxis']['title']['text'] == 'Watts' ):
                    m_table_energy.append( html.Td( f"{(g_graph_data[m_iter][m_figure['layout']['yaxis']['title']['text']].mean() * (m_duration.seconds + m_duration.microseconds / 1000000)):.3f}" ) )

            m_iter += 1

        if( len(m_table_run_id) == 1 ):
            return html.B( "No datasets match filter settings." )
             
        m_ret = [ html.Tr( m_table_run_id   ),
                  html.Tr( m_table_workload ),
                  html.Tr( m_table_scenario ),
                  html.Tr( m_table_run_mode ),
                  html.Tr( m_table_metric   ),
                  html.Tr( m_table_score    ),
                  html.Tr( m_table_samples  ),
                  html.Tr( m_table_duration ),
                  html.Tr( m_table_min      ),
                  html.Tr( m_table_max      ),
                  html.Tr( m_table_average  ),
                  html.Tr( m_table_dev      ) ]
                  
        if( m_figure['layout']['yaxis']['title']['text'] == 'Watts' ):
            m_ret.append( html.Tr( m_table_energy  ) )
            
        return m_ret


    if( g_verbose ) : print( "graph: starting DASH server.  use a web browser to connect to IP to view graphs.\n" +
                             "       press CTRL-C to stop server and end script" )

#### Begin graphing
    app.run_server(debug=True)

    
#### Parse Loadgen log files
####  Specify directory and search for ""*detail.txt" & "*summary.txt"
####  Loadgen directory structure should be:
####     .\.*\year.month.day-hour.minute.second\device\workload\scenario\*.*
####  The workload name must be contained in m_worklist since it is not recorded in the .txt files
def f_parse_Loadgen( p_dirin, p_fileout, p_custom_workloads ):
    m_worklist         = [ "resnet50", "resnet",
                           "mobilenet",
                           "gnmt",
                           "ssdmobilenet", "ssd-small",
                           "ssdresnet34",  "ssd-large" ]
    m_workload         = None
    m_scenario         = ""
    m_testmode         = ""
    m_loadgen_start_dt = None
    m_loadgen_begin_ts = 0
    m_loadgen_end_ts   = 0
    m_system_begin_dt  = None
    m_system_end_dt    = None
    m_score_valid      = None
    m_score_value      = None
    m_metric           = defaultdict( lambda : "No metric defined." )

    if( type(p_custom_workloads) is list ): 
        if( g_verbose ) : print( f"parseLoadgen: parsing custom list of workloads {p_custom_workloads}" )
        m_worklist = p_custom_workloads

    m_metric.update( { "offline"      : "result_samples_per_second",
                       "multistream"  : "effective_samples_per_query",
                       "singlestream" : "result_90.00_percentile_latency_ns",
                       "server"       : "result_scheduled_samples_per_sec" } )
    
    m_counter = 0

    m_storage = []
    m_storage.append( ["Workload", "Scenario", "Mode",
                       "Loadgen Start Date", "Loadgen Start Time",  # time of test: <iso datetime>
                       "Loadgen Begin TS",   "Loadgen End TS",      # "ts": (\d*)ns
                       "System Begin Date",  "System Begin Time",   # POWER_BEGIN ... "time": <non-iso datetime>
                       "System End Date",    "System End Time",     # POWER_END   ... "time": <non-iso datetime>
                       "Result", "Score", "Metric"] )

    # Assumes both *detail.txt and *summary.txt files exists
    for m_dirname, m_subdirs, m_filelist in os.walk( p_dirin ):
        for m_filename in m_filelist:
            if m_filename.endswith( 'detail.txt' ):
                m_fullpath = os.path.join(m_dirname, m_filename)

                m_workload = None
                for m_re in m_worklist:
                    if( re.search( r"\\" + m_re + r"\\", m_fullpath, re.I ) or 
                        re.search( r"/"  + m_re + r"/" , m_fullpath, re.I ) ):
                        m_workload = m_re
                        break
                if( not m_workload ):
                    print( f"parseLoadgen: warning: {m_filename} found, but workload name is missing from directory structure: {m_dirname}\n" +
                           f"                       please place files into a structure with supported workload names in the path\n" +
                           f"                       or use --workload to specify a custom workload.  parsing will be skipped for: {m_filename}" )
                    continue
                else:
                    m_counter += 1

                try:
                    m_file = open( m_fullpath, 'r' )
                except:
                    print( "error opening file:", m_fullpath )
                    exit(1)

                m_scenario = None
                for m_line in m_file:
                    logger_prefix = ":::MLLOG "
                    if m_line.startswith(logger_prefix):
                        try:
                            m_line_json = json.loads(m_line[len(logger_prefix):])
                        except Exception as e:
                            print( f"Invalid format in detailed log. Error: {e}.\nSkipping line: {m_line}" )
                            continue

                        m_line_key = m_line_json["key"]
                        m_line_value = m_line_json["value"]
                        if m_line_key == "test_datetime":
                            m_loadgen_start_dt = dateutil.parser.parse(m_line_value)
                            m_loadgen_begin_ts = int(m_line_json["time_ms"] * 1000000)
                        elif m_line_key == "power_begin":
                            m_system_begin_dt = dateutil.parser.parse(m_line_value)
                        elif m_line_key == "power_end":
                            m_system_end_dt = dateutil.parser.parse(m_line_value)
                            m_loadgen_end_ts = int(m_line_json["time_ms"] * 1000000)
                        elif m_line_key == "effective_scenario":
                            m_scenario = m_line_value.lower()
                        elif m_line_key == "effective_test_mode":
                            m_testmode = m_line_value.replace("Only","")
                        elif m_line_key == "result_validity":
                            m_score_valid = m_line_value
                        elif m_scenario is not None and m_line_key == m_metric[m_scenario]:
                            m_score_value = m_line_value

            if( not None in [m_loadgen_start_dt, m_system_begin_dt, m_system_end_dt, m_score_valid, m_score_value] ):
                m_storage.append( [ m_workload, m_scenario, m_testmode,
                                    m_loadgen_start_dt.date(), m_loadgen_start_dt.time(),
                                    m_loadgen_begin_ts, m_loadgen_end_ts,
                                    m_system_begin_dt.date(), m_system_begin_dt.time(),
                                    m_system_end_dt.date(), m_system_end_dt.time(),
                                    m_score_valid, m_score_value, m_metric[m_scenario] ] )
                m_loadgen_start_dt = m_system_begin_dt = m_system_end_dt = m_score_valid = m_score_value = None

    if( g_verbose ) : print( f"parseLoadgen: {m_counter} loadgen log files found and {len(m_storage)-1} parsed" )

    try:
        if( g_verbose ) : print( f"parseLoadgen: storing CSV data into: {p_fileout}" )
        with open( p_fileout, 'w', newline='') as m_file:
            m_csvWriter = csv.writer( m_file, delimiter=',' )

            for m_entry in m_storage:
                m_csvWriter.writerow( m_entry )
        m_file.close()
    except:
        print( "parseLoadgen: error while creating csv output file:", p_fileout )
        exit(1)


#### Parse PTDaemon Power Log Filename (legacy support)
#### Format should be:
####   Time,MM-DD-YYYY HH:MM:SS.mmm,Watts,D*.D*,Volts,D*.D*,Amps,D*.D*,PF,D*.D*,Mark,String
#### Output format will be:
####   Date,Time,Watts,Volts,Amps,PF,Mark
####   YYYY-MM-DD,HH:MM:SS.mmm,D*.D*,D*.D*,D*.D*,D*.D*,String
def f_parse_SPECPowerlog( p_filein, p_fileout ):
    m_counter = 0
    m_storage = []

    try:
        if( g_verbose ) : print( f"parseSPEC: opening power log file: {p_filein}" )
        m_file = open( p_filein, 'r' )
    except:
        print( f"parseSPEC: error opening power log file: {p_filein}" )
        exit(1)

    # Create headers
    m_storage.append( ["Date", "Time", "Watts", "Volts", "Amps", "PF", "Mark"] )

    # Store data
    for m_line in m_file :
    
        if( not re.match("^Time,.*,Watts,.*,Volts,.*,Amps,.*,PF,.*,Mark,.*$", m_line ) ):
            continue
    
        m_counter = m_counter + 1
        m_line = m_line.strip()
        m_line = m_line.replace( "Time", "Date", 1 )
        m_line = m_line.replace( " ", ",Time,", 1)
        m_line = m_line.split(',')[1::2]

        # need to re-order date to iso format
        m_line[0] = m_line[0][-4:] + m_line[0][-5:-4] + m_line[0][:5]

        m_storage.append( m_line )

    m_file.close()

    if( g_verbose ) : print( f"parseSPEC: done parsing PTDaemon power log.  {m_counter} entries processed" )

    try:
        if( g_verbose ) : print( f"parseSPEC: storing csv data into: {p_fileout}" )
        with open( p_fileout, 'w', newline='') as m_file:
            m_csvWriter = csv.writer( m_file, delimiter=',' )

            for m_entry in m_storage:
                m_csvWriter.writerow( m_entry )
        m_file.close()
    except:
        print( f"parseSPEC: error while creating PTDaemon power log csv output file: {p_fileout}" )
        exit(1)



def f_parseParameters():
    global g_verbose
    global g_power_add_td
    global g_power_sub_td
    
    m_argparser = argparse.ArgumentParser()

    # Inputs
    m_argparser.add_argument( "-lgi", "--loadgen_in",   help="Specify directory of loadgen log files to parase from",
                                                        default="" )
    m_argparser.add_argument( "-spl", "--specpower_in", help="Specify PTDaemon power log file (in custom PTD format)",
                                                        default="" )
    m_argparser.add_argument( "-pli", "--powerlog_in",  help="Specify power or data input file (in CSV format)",
                                                        default="" )

    # Outputs
    m_argparser.add_argument( "-lgo", "--loadgen_out",  help="Specify loadgen CSV output file (default: loadgen_out.csv)",
                                                        default="loadgen_out.csv" )
    m_argparser.add_argument( "-plo", "--powerlog_out", help="Specify power or data CSV output file (default: power_out.csv)",
                                                        default="power_out.csv" )

    # Function options
    m_argparser.add_argument( "-g",   "--graph",        help="Draw/output graphable data over time using the lgi/lgo and pli/plo as input.\n"
                                                             "(Optional) Input a list of strings to filter data",
                                                        nargs="*")
    m_argparser.add_argument( "-s",   "--stats",        help="Outputs statistics between loadgen & power/data timestamps using lgi/lgo and pli/plo as inputs.\n" +
                                                             "(Optional) Input a list of strings to filter data",
                                                        nargs="*")
    m_argparser.add_argument( "-csv", "--csv",          help="Outputs statistics to a CSV file (optional parameter, default: stats_out.csv) instead of stdout.",
                                                        nargs="?",
                                                        const="" )
    m_argparser.add_argument( "-w",   "--workload",     help="Parse for workloads other than [mobilenet, gnmt, resenet50/resnet, ssd-large/ssdresnet34, or ssd-small/ssdmobilenet]",
                                                        nargs="+" )

    m_argparser.add_argument( "-v",   "--verbose",      action="store_true" )

                                                        
    # Timing parameters
    m_argparser.add_argument( "-deskew", "--deskew",    help="Adjust timing skew between loadgen and power/data logs (in seconds)",
                                                        type=int,
                                                        default=0)

    m_args = m_argparser.parse_args()
    
    g_verbose = m_args.verbose
    
    if( m_args.csv == "" ):
        m_args.csv = "stats_out.csv"

    if( m_args.workload ):
        m_args.workload = list(dict.fromkeys(m_args.workload))

    if( m_args.specpower_in == m_args.powerlog_out ):
        print( "**** ERROR: Power log output file cannot be the same as power log input file!" )
        exit(1)

    if( m_args.specpower_in != "" and m_args.powerlog_in != "" and m_args.graph ):
        print( "**** ERROR: Only one set of power data can be graphed." )
        exit(1)

    if( m_args.powerlog_out != "" and m_args.powerlog_in == "" and m_args.graph ):
        m_args.powerlog_in = m_args.powerlog_out

    if( m_args.graph ) :
        if( m_args.powerlog_in is None and m_args.powerlog_out is None and m_args.specpower_in is None ) :
            print( "**** ERROR: Need power/data log to graph" )
            exit(1)
        if( m_args.loadgen_in is None and m_args.loadgen_out is None ) :
            print( "**** ERROR: Need loadgen log to graph" )
            exit(1)
        
        
    if( m_args.deskew >= 0 ):
        g_power_add_td           = timedelta(seconds=m_args.deskew)
        g_power_sub_td           = timedelta(seconds=0)
    else:
        g_power_add_td           = timedelta(seconds=0)
        g_power_sub_td           = timedelta(seconds=abs(m_args.deskew))


    return m_args


if __name__ == '__main__':
    main()

