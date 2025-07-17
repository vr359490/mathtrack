import pandas as pd
import dash
from dash import dash_table, dcc, html, Input, Output, State, callback, ctx, Patch, MATCH, ALL
import os
import plotly.graph_objects as go
from io import BytesIO
import math
import statistics
import dash_bootstrap_components as dbc
import time
import json
from collections import OrderedDict
from process import string_check

import calendar
import datetime
from datetime import timedelta
import warnings
from scrape import deploy

import boto3

import process

bucket = "mathdashbucket"

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

s3 = boto3.client("s3",
                      aws_access_key_id=AWS_ACCESS_KEY,
                      aws_secret_access_key=AWS_SECRET_KEY,
                      region_name="us-east-2")

# Import files from AWS S3
def down(s3, filename):

    ulti = s3.list_objects_v2(Bucket=bucket)
    
    xlsx_keys = [obj["Key"] for obj in ulti.get("Contents", [])
            if obj["Key"].endswith(".xlsx")]
    
    if filename: xlsx_keys=[filename]

    for obj in xlsx_keys:

        response = s3.get_object(Bucket=bucket, Key=obj)
        obj_content_0 = response["Body"].read()
        obj_content = BytesIO(obj_content_0)

        if ".csv" in filename:
            df = pd.read_csv(obj_content)
        elif ".json" in filename:            
            df = json.loads(obj_content_0)
        else:
            df = pd.read_excel(obj_content)
    return df

def dwp_scrape_ALL():

    filename = "DWP_Report_(All).xlsx"

    #path = "/Users/victorruan/Desktop/mathnasium_dash_files/" + filename

    data = down(s3, filename)

    #data = pd.read_excel(path)  

    pk_completion = dwp_process(data)

    return pk_completion

def dwp_process(data):
    
    pk_completion = {}
    mr_list =  []

    rows = data.shape[0]

    for i in range(rows):

        student = data['Student Name'][i]

        # Skip empty cells
        if type(data['LP Assignment'][i])!=type('string'):
            continue

        pk_status_list = data['LP Assignment'][i].split(';')
        
        # Create dict entry for new student
        if student not in pk_completion.keys():
            pk_completion[student] = {}
            pk_completion[student]["Number of PKs"] = 0
            pk_completion[student]["Total Sessions Worked On"] = 0

        for pk_stat_pair in pk_status_list:
            pk_ID_name_pair = ''
            paren_count = 0

            for index, char in enumerate(pk_stat_pair):
                pk_ID_name_pair += char

                if char=="(":
                    paren_count+=1
                if char==")":
                    paren_count-=1
                if char==")" and paren_count==0:
                    status = pk_stat_pair[index+2:]
                    break

            worked_on = 'Worked On'
            mastered = 'Mastered'
            completed = 'Completed'
            
            pk_ID_name_pair = pk_ID_name_pair.strip()

            if pk_ID_name_pair not in pk_completion[student].keys():
                pk_completion[student]["Number of PKs"] += 1
                pk_completion[student][pk_ID_name_pair] = {}

                if worked_on in status: 
                    pk_completion[student][pk_ID_name_pair][worked_on]=1
                    pk_completion[student][pk_ID_name_pair][mastered]=0
                    pk_completion[student][pk_ID_name_pair][completed]=0
                    pk_completion[student]["Total Sessions Worked On"] += 1

                elif mastered in status: 
                    pk_completion[student][pk_ID_name_pair][worked_on]=1
                    pk_completion[student][pk_ID_name_pair][mastered]=1
                    pk_completion[student]["Total Sessions Worked On"] += 1
                    
                elif completed in status: 
                    pk_completion[student][pk_ID_name_pair][worked_on]=1
                    pk_completion[student][pk_ID_name_pair][completed]=1
                    pk_completion[student]["Total Sessions Worked On"] += 1
            else:       
                if worked_on in status: 
                    pk_completion[student][pk_ID_name_pair][worked_on]+=1
                    pk_completion[student]["Total Sessions Worked On"] += 1

                elif mastered in status:
                    pk_completion[student][pk_ID_name_pair][mastered]=1
                    pk_completion[student][pk_ID_name_pair][worked_on]+=1
                    pk_completion[student]["Total Sessions Worked On"] += 1

                elif completed in status: 
                    pk_completion[student][pk_ID_name_pair][completed]+=1
                    pk_completion[student][pk_ID_name_pair][worked_on]+=1
                    pk_completion[student]["Total Sessions Worked On"] += 1

    for student in pk_completion.keys():

        mastery_rate = pk_completion[student]["Total Sessions Worked On"]/pk_completion[student]["Number of PKs"]

        pk_completion[student]["Average Sessions to Master PK"] = mastery_rate
        mr_list.append(mastery_rate)
    
    return pk_completion

def find_recent_lp(process_df,student):

    assigned = pd.to_datetime(process_df[student]['Assigned'])
    max_date = assigned.max()
    index = assigned[assigned==max_date].index

    if list(index): 
        index_max_date = list(index)[0]
        most_recent_lp = process_df[student]['Learning Plan Name'][index_max_date]
    else:
        most_recent_lp=None

    return most_recent_lp

def create_student_summaries(students, attendance_df, pk_completion):
    # Lots of pandas warnings here, ignore for now.
    warnings.filterwarnings('ignore')

    summaries = pd.DataFrame()

    for student in students:

        student_data = pk_completion.get(student, None)
        if not student_data: continue

        student_summary = attendance_df.loc[attendance_df['Full Name']==student]
        student_summary['Mastery Rate'] = round(student_data["Average Sessions to Master PK"],2)
        student_summary['Learning Rate'] = float(round(1/student_summary['Mastery Rate'], 3)) 
        summaries = pd.concat([summaries, student_summary], ignore_index=True)

    summaries_dict = summaries.to_dict('records')

    with open("student_summaries.json", "w") as f:
        json.dump(summaries_dict, f)

    return summaries

def create_center_attendance_graph(all_attendance_df):
    # Calculate mean attendance for each month
    monthly_means = all_attendance_df.mean(axis=1)
    y_max = math.ceil(max(monthly_means))
    
    # Create bar trace for monthly averages
    bar_trace = go.Bar(
        name="Center Average",
        x=list(all_attendance_df.index),
        y=monthly_means,
        showlegend=False
    )
    
    # Calculate and create moving average trace
    moving_avg = monthly_means.rolling(window=3, min_periods=1).mean()
    scatter_trace = go.Scatter(
        name="3-Month Average",
        x=list(all_attendance_df.index),
        y=moving_avg,
        showlegend=False
    )
    
    # Create figure with both traces
    fig = go.Figure(data=[bar_trace, scatter_trace])
    
    return fig, y_max

def create_modal_filter_row(id_number):

    filter_name = "filter-" + id_number
    
    filter_column_id = "filter-column-" + id_number
    filter_sign_id = "filter-sign-" + id_number
    filter_input_id = "filter-input-" + id_number
    button_id = "button-" + id_number

    if id_number=="0":
        display = "block"
    else: 
        display = "none"

    filter_row =  html.Div(
                [html.Div([
                dcc.Dropdown(
                    id = filter_column_id,
                    options = [{'label':'Average Attendance per Month', 'value':'Avg Attend/m'},
                                {'label':'Learning Rate','value':'Learning Rate'},
                                {'label':'Mastery Rate','value':'Mastery Rate'},
                                {'label':'Remaining Sessions','value':'Remaining'}],
                    placeholder = "Select a column...",
                    value = None
                                )   
                ],style={'display':'inline-block','width':'46%', 'verticalAlign':'top'}),
                html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
                html.Div([
                    dcc.Dropdown(
                        id = filter_sign_id,
                        options = [{'label':'equal to', 'value': '=='},
                                    {'label':'greater than', 'value':'>'},
                                    {'label':'less than', 'value':'<'},
                                    {'label':'greater than or equal to', 'value':'>='},
                                    {'label':'less than or equal to', 'value': '<='}],
                        placeholder = "equal to")   
                ],style={'display':'inline-block','width':'32%', 'verticalAlign':'top'}),
                html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
                html.Div([
                    dbc.Input(
                        id=filter_input_id,
                        type = "number",
                        style={"height":36},
                        placeholder="")   
                ],style={'display':'inline-block','width':'17%', 'verticalAlign':'top'}),
                html.Div([
                    html.Div(style={'height':'4px'}),
                    html.Div([dbc.Button("❌", color="light", id = button_id, n_clicks=0)])   
                ],style={'display':'inline-block','width':'3%', 'verticalAlign':'top'}),
                html.Div(style={'display':'block','height':'9px'}),],

                style={"display":display},
                id = filter_name)
    return filter_row

filter_row_0 = create_modal_filter_row("0")
filter_row_1 = create_modal_filter_row("1")
filter_row_2 = create_modal_filter_row("2")
filter_row_3 = create_modal_filter_row("3")

def query_report(query_list, low_attend_report):
    # Every query should have exactly three parts. If less, we can't and don't process.
    for query in query_list:
        col = query[0]
        sign = query[1]
        val = str(query[2])

        data = []

        for data_point in low_attend_report[col]:

            if type(data_point)==str:
                data_point = string_check(data_point)
            elif math.isnan(data_point):
                data_point = None

            data.append(data_point)

        data = pd.DataFrame(data, columns=['useless name'])

        code = "low_attend_report[data['useless name']" + sign + val + "]"

        low_attend_report = eval(code)
        low_attend_report = low_attend_report.reset_index(drop=True)

    return low_attend_report.to_dict('records')

def app_layout(app, process_df,sessions_left, all_attendance_df, sessions_per_m, center_attend_avg):

    student_roster = sessions_left['Full Name']
    first_student = student_roster[0]
    attendance_df = sessions_left[['Full Name','Membership Type','Remaining','Avg Attend/m','This Month Attendance']]

    pk_completion = dwp_scrape_ALL()

    summaries = create_student_summaries(list(student_roster), attendance_df, pk_completion)

    student_summary = pd.DataFrame(summaries.iloc[0]).T
    student_summary = student_summary.drop('Full Name', axis = 1)

    mr_list = []
    lr_list = []

    for student in student_roster:
        mr, lr = None, None
        student_dict = pk_completion.get(student, None)

        if student_dict: 
            mr = round(student_dict["Average Sessions to Master PK"], 2)
            lr = round(1/mr, 3)

        mr_list.append(mr)
        lr_list.append(lr)
    
    low_attend_report = sessions_left.copy(deep = True)
    low_attend_report['Mastery Rate'] = mr_list
    low_attend_report['Learning Rate'] = lr_list
    low_attend_report = low_attend_report[['Full Name','Membership Type','Remaining','Mastery Rate','Learning Rate','Avg Attend/m']]
    low_attend_report = low_attend_report.rename(columns = {'Membership Type': 'Member Type'})

    f_mr_list = [mr for mr in mr_list if mr is not None]
    f_lr_list = [lr for lr in lr_list if lr is not None]

    avg_mr = round(statistics.mean(f_mr_list),2)
    avg_lr = round(statistics.mean(f_lr_list),3)

    center_summary = pd.DataFrame({"Center": ["Verona"], "Mastery Rate":[avg_mr],"Learning Rate":[avg_lr],"Avg Attend/m":[round(center_attend_avg,2)]})

    center_sum_json = center_summary.to_dict('records')

    with open("center_averages.json", "w") as f:
        json.dump(center_sum_json[0], f)

    # with open("generated_summaries.json", "r") as f:
    #     generated_summaries = json.load(f)

    generated_summaries = down(s3, 'generated_summaries.json')

    # Truncate Membership Type to be shorter and more readable
    for index, member_type in enumerate(low_attend_report['Member Type']):
        if "Package" in member_type:
            low_attend_report.loc[index,'Member Type'] = member_type.split(" ")[0]
    
    learning_plans = list(process_df[first_student]['Learning Plan Name'].unique())

    most_recent_lp = find_recent_lp(process_df, first_student)

    # Initialize main page layout
    main_view = html.Div([
        html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
        html.Div([
            html.H5(id = 'lp-header'),
            dash_table.DataTable(
                id = 'student-summary-table',
                columns=[{"name": i, "id": i} for i in student_summary.columns],  
                data=student_summary.to_dict('records'),
                style_cell={
                    'color': 'black',
                    'overflow': 'hidden',
                    'textOverflow': 'ellipsis',
                    'maxWidth': 0,
                    'textAlign': 'left',
                    'font-family':'Arial',
                    'fontSize':12
            },
                style_cell_conditional=[
                    {'if' :{'column_id': 'Remaining'},
                                                'width':'11.5%' },
                    {'if' :{'column_id': 'Avg Attend/m'},
                                                'width':'14%' },
                    {'if' :{'column_id': 'Mastery Rate'},
                                                'width':'13.5%' },
                    {'if' :{'column_id': 'Learning Rate'},
                                                'width':'13.5%' },
                                                    ],
                tooltip_header={
                    "Avg Attend/m":"Average number of sessions attended per month",
                    "Mastery Rate":"Average number of sessions to master PK.",
                    "Learning Rate":"Average number of PKs completed per session."},
                style_header_conditional=[{
                    'if': {'column_id': col},
                    'textDecoration': 'underline'
                } for col in ['Mastery Rate', 'Learning Rate']],

                tooltip_delay=0,
                tooltip_duration=None,
            ),
        html.H6(["Learning Plan"]),
        dash_table.DataTable(
            id='lp-table',
            columns=[{"name": i, "id": i} for i in process_df[first_student].columns if i != 'Learning Plan Name'],
            style_cell={
                'color': 'black',
                'overflow': 'hidden',
                'textOverflow': 'ellipsis',
                'maxWidth': 0,
                'textAlign': 'left',
                'font-family':'Arial',
                'fontSize':12
            },
            style_cell_conditional=[
                        {'if' :{'column_id': 'ID'},
                                                    'width':'16%' },
                        {'if' :{'column_id': 'Assigned'},
                                                    'width':'14.5%' },
                        {'if' :{'column_id': 'Completed'},
                                                    'width':'14.5%' }],
        )
    ],style={'display':'inline-block','width':'47%', 'verticalAlign':'top'}),
    html.Div(style={'display':'inline-block','width':'1.5%', 'verticalAlign':'top'}),
    html.Div([  # This will be the right side with the Graph
        
        html.H5("Student Trends"),
        html.Div([dcc.Graph(id='pk-chart')
                ],style={'display':'inline-block','width':'51%', 'verticalAlign': 'top'}),
        html.Div([dcc.Graph(id='initial-attend-graph')
                ],style={'display':'inline-block','width':'49%', 'verticalAlign': 'top'}),

        html.Div(style={'height':'9px'}),

        # html.H6(["Data Summary ✨"],style={'marginBottom':-1}),
        html.Div(["Data was last updated on: ", datetime.datetime.now().strftime("%I:%M %p %Y-%m-%d")],style={'fontSize':11}),
        html.Div(style={'height':'4px'}),
        html.Div(style={'display':'inline-block','width':'1.5%', 'verticalAlign':'top'}),
        # html.Div([
        #     dcc.Store(id="clicks"),
        #     dbc.Fade(
        #         dbc.Card(
        #             dbc.CardBody(
        #                 html.P(
        #                     children=[generated_summaries["A.J. Kuehn"]],
        #                     id="generated-summary",
        #                     className="card-text")
        #             )
        #         ),
        #         is_in=True,
        #         appear=True,
        #         exit=False, 
        #         style={"transition": "opacity 1000ms ease"},
        #         timeout=1000,
        #     ),
        # ],id="summary-div",
        # style = {'display':'inline-block','width':'96.5%', 'verticalAlign':'top', 'fontSize':13}),
        html.Div(style={'display':'inline-block','width':'2%', 'verticalAlign':'top'}),
    ], style={'display':'inline-block','width':'50.5%', 'verticalAlign': 'top'}), 
    ])

    center_view = html.Div([
    html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign': 'top'}),
    html.Div([
        html.H5(['Center Averages'],style={'display':'inline-block','width':'84.5%', 'verticalAlign': 'top'}), 
        dash_table.DataTable(
                id = 'center-summary',
                columns=[{"name": i, "id": i} for i in center_summary.columns],  
                data=center_summary.to_dict('records'),
                style_cell={
                    'color': 'black',
                    'overflow': 'hidden',
                    'textOverflow': 'ellipsis',
                    'maxWidth': 0,
                    'textAlign': 'left',
                    'font-family':'Arial',
                    'fontSize':12
            },
                tooltip_header={
                    "Avg Attend/m":"Average number of sessions attended per month",
                    "Mastery Rate":"Average number of sessions to master PK.",
                    "Learning Rate":"Average number of PKs completed per session."},
                style_header_conditional=[{
                    'if': {'column_id': col},
                    'textDecoration': 'underline'
                } for col in ['Mastery Rate', 'Learning Rate']],

                tooltip_delay=0,
                tooltip_duration=None,
            ),
        html.Div(style={'height':'15px'}),
        html.H5(['Student Averages'],style={'display':'inline-block','width':'84.5%', 'verticalAlign': 'top'}), 
        html.Div([
            html.Div(style={'height':'12px'}),
            dbc.Button("Filter table", id="open", n_clicks=0),
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("I want to filter by...")),
                dbc.ModalBody(
                    html.Div([
                        filter_row_0,
                        filter_row_1,
                        filter_row_2,
                        filter_row_3
                    ])
                    ),
                dbc.ModalFooter(
                    html.Div([
                    html.Div([
                    dbc.Button("Add filter", size = "lg",color="secondary", id="add-filter", n_clicks=0)
                    ],style={'display':'inline-block'}),
                    html.Div(style={'display':'inline-block', 'width':'16px'}),
                    html.Div([
                    dbc.Button("Search", size="lg",id="run", n_clicks=0)
                    ],style={'display':'inline-block', 'width':'84px'})])
                ),
                    ],
                    id="modal",
                    size="lg",
                    centered=True,
                    backdrop="static",
                    is_open=False,
                ),
                ],style={'display':'inline-block','width':'15.5%', 'horizontalAlign': 'right'}),
                dash_table.DataTable(
                    id = 'low-attend',
                    columns = [{"name":j, "id":j} for j in low_attend_report.columns],
                    data = low_attend_report.to_dict('records'),
                    style_cell =                 
                    {'color': 'black',
                        'overflow': 'hidden',
                        'textOverflow': 'ellipsis',
                        'maxWidth': 0,
                        'textAlign': 'left',
                        'font-family':'Arial',
                        'fontSize':12},
                    style_cell_conditional=[
                        {'if' :{'column_id': 'Full Name'}, 'width':'26%'},
                        {'if' :{'column_id': 'Member Type'}, 'width':'19%'},
                        {'if' :{'column_id': 'Avg Attend/m'}, 'textAlign':'right'},
                        ],
            tooltip_header={
                "Mastery Rate":"Average number of sessions to master PK.",
                "Learning Rate":"Average number of PKs completed per session."},

            tooltip_delay=0,
            tooltip_duration=None,

            style_header_conditional=[{
                'if': {'column_id': col},
                'textDecoration': 'underline'
        } for col in ['Mastery Rate', 'Learning Rate']],
            
        )],style={'display':'inline-block','width':'47%', 'verticalAlign':'top'}),
        html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
        html.Div([
            html.H6(['Student Summary']),
            dash_table.DataTable(
                id = 'student-summary-table',
                columns=[{"name": i, "id": i} for i in student_summary.columns],  
                data=student_summary.to_dict('records'),
                style_cell={
                    'color': 'black',
                    'overflow': 'hidden',
                    'textOverflow': 'ellipsis',
                    'maxWidth': 0,
                    'textAlign': 'left',
                    'font-family':'Arial',
                    'fontSize':12
            },
                style_cell_conditional=[
                    {'if' :{'column_id': 'Remaining'},
                                                'width':'11.5%' },
                    {'if' :{'column_id': 'Avg Attend/m'},
                                                'width':'14%' },
                    {'if' :{'column_id': 'Mastery Rate'},
                                                'width':'13.5%' },
                    {'if' :{'column_id': 'Learning Rate'},
                                                'width':'13.5%' },
                                                    ],
                tooltip_header={
                    "Avg Attend/m":"Average number of sessions attended per month",
                    "Mastery Rate":"Average number of sessions to master PK.",
                    "Learning Rate":"Average number of PKs completed per session."},
                style_header_conditional=[{
                    'if': {'column_id': col},
                    'textDecoration': 'underline'
                } for col in ['Mastery Rate', 'Learning Rate']],

                tooltip_delay=0,
                tooltip_duration=None,
            ),

            html.Div(style={'height':'5px'}),

            html.H6(id = 'attendance-header', style={'display':'inline-block','width':'47%', 'verticalAlign':'top'}),
            html.H6(["Verona's Average Attendance"], style={'display':'inline-block','width':'47%', 'verticalAlign':'top'}),
            
            dcc.Graph(
                id = 'attend-graph',
            style={'display':'inline-block','width':'47%', 'verticalAlign':'top'}),
            
            dcc.Graph(
                id='center-attendance-graph',
        style={'display':'inline-block','width':'47%', 'verticalAlign':'top'}),
    ],style={'display':'inline-block','width':'51%', 'verticalAlign':'top', 'position':'fixed'}),#'position': 'fixed'}),
    ])

    # Important note when revising/refactor: 
    # 
    # We need to use Pattern Matching callbacks in Dash to account for a dynamic number of filters.
    # This will be necessary if we'd like to add an indefinite amount of filters.
    # https://dash.plotly.com/pattern-matching-callbacks

    # Instead of directly clearing filter values, can we create a new copy from out create_filter function?
    @callback(
        Output("filter-0","style"),
        Output("filter-1","style"),
        Output("filter-2","style"),
        Output("filter-3","style"),
        Output("filter-0","children"),
        Output("filter-1","children"),
        Output("filter-2","children"),
        Output("filter-3","children"),
        Input("button-0", "n_clicks"),
        Input("button-1", "n_clicks"),
        Input("button-2", "n_clicks"),
        Input("button-3", "n_clicks"),
        Input("add-filter", "n_clicks"),
        State("filter-0", "style"),
        State("filter-1", "style"),
        State("filter-2", "style"),
        State("filter-3", "style"),
        State("filter-0", "children"),
        State("filter-1", "children"),
        State("filter-2", "children"),
        State("filter-3", "children"),

        prevent_initial_call=True
    )
    def filter_toggle(x1,x2,x3,x4,add,s1,s2,s3,s4,c0,c1,c2,c3):

        style_list = [s1,s2,s3,s4]
        # child_list = [c0,c1,c2,c3]

        pressed_btn = ctx.triggered_id

        if pressed_btn=="add-filter":
            for i in range(len(style_list)-1):
                if style_list[i] != style_list[i+1]:
                    style_list[i+1]= style_list[i]
                    return style_list[0],style_list[1],style_list[2],style_list[3], c0,c1,c2,c3
                
        elif "button" in pressed_btn:

            # Alter the following to return a newly created filter row instead of directly clearing values.
            # This will avoid the eval() function as well, which is generally bad practice

            index = int(pressed_btn.split("-")[1])

            filter_id = "c"+str(index)
            filter_name = eval(filter_id)

            for j,child in enumerate(filter_name):

                # Following is deeply nested and likely unnecessary.
                # Further, if dropdown/filter structure changes, this will break. 
                # We should refactor. 
                g_child = child['props']['children']

                if g_child:
                    if g_child[0]['props'].get('value', None):
                        filter_name[j]['props']['children'][0]['props']['value'] = None

            if index==0:
                return s1,s2,s3,s4, c0,c1,c2,c3
            else:
                style_list[index]={"display":"none"}
                return style_list[0],style_list[1],style_list[2],style_list[3], c0,c1,c2,c3
 
    @callback(
        Output('low-attend', 'data'),
        State('filter-column-0','value'),
        State('filter-column-1','value'),
        State('filter-column-2','value'),
        State('filter-column-3','value'),
        State('filter-sign-0', 'value'),
        State('filter-sign-1', 'value'),
        State('filter-sign-2', 'value'),
        State('filter-sign-3', 'value'),
        State('filter-input-0', 'value'),
        State('filter-input-1', 'value'),
        State('filter-input-2', 'value'),
        State('filter-input-3', 'value'),
        Input('run', 'n_clicks')
    )
    def modal_query(col0,col1,col2,col3, sign0,sign1,sign2,sign3, in0,in1,in2,in3, n_clicks):
        
        time.sleep(0.4)

        num_cols = 4

        params = ["col", "sign", "in"]

        query_list = []
        
        for id in range(num_cols):
            query = []
            for param in params:
                param_id = eval(param + str(id))
                if param_id:
                    query.append(param_id)

            if len(query)==3:
                query_list.append(query)

        if query_list:  
            filtered_report = query_report(query_list, low_attend_report)
            return filtered_report
        else: 
            return low_attend_report

    @app.callback(
    Output("modal", "is_open"),
    [Input("open", "n_clicks"), Input("run", "n_clicks")],
    [State("modal", "is_open")],
)
    def modal_toggle(n1, n2, is_open):
        if n1 or n2:
            return not is_open
        return is_open

    @callback(
        Output('pandas-dropdown-3', 'value'),
        Output('pandas-dropdown-3', 'options'),
        Input('pandas-dropdown-1', 'value')
        )
    def update_dropdown3_val(student):

        most_recent_lp = find_recent_lp(process_df, student)

        return most_recent_lp, list(process_df[student]['Learning Plan Name'].unique())

    # @callback(
    #     Output('generated-summary', 'children'),
    #     Input('pandas-dropdown-1', 'value'),
    #     prevent_initial_call=True
    #     )
    # def update_generated_summary(student):
    #     return [generated_summaries[student]]
    
    @callback(
        Output('attend-graph', 'figure'),
        Output('low-attend', 'active_cell'),
        Output('attendance-header', 'children'),
        Output('pandas-dropdown-1', 'value'),
        Output('center-attendance-graph', 'figure'),
        Input('pandas-dropdown-1', 'value'),
        Input('low-attend', 'active_cell'),
        Input('low-attend', 'data'),
    )
    def update_attendance_graph(student, active_cell, low_attend_data):
        
        low_attend_data = pd.DataFrame(low_attend_data)

        if active_cell: 
            rowNum = active_cell['row']
            colNum = active_cell['column']
            student = low_attend_data.iloc[rowNum, colNum]
        
        bar_trace = go.Bar(name="Attendance",x=list(all_attendance_df.index), y=all_attendance_df[student], showlegend=False)#, marker_color='#292929')

        attend_list_no_nan = [i for i in list(all_attendance_df[student]) if not math.isnan(i)]

        if attend_list_no_nan:
            y_max1 = max(attend_list_no_nan)
        else:
            y_max1 = 0

        moving_avg = list(all_attendance_df[student].copy(deep=True).rolling(window=3, min_periods=1).mean())
        scatter_trace = go.Scatter(name="Avg", x=list(all_attendance_df.index), y=moving_avg, showlegend=False)
        
        fig2 = go.Figure(data=[bar_trace, scatter_trace])
        center_attend_fig, y_max2 = create_center_attendance_graph(all_attendance_df)

        if math.isnan(y_max1):
            y_range = y_max2+0.5
        else:
            y_range = max(y_max1, y_max2)+1

        fig2.update_layout(yaxis_range=[0, y_range], height=350, margin=dict(l=10, r=10, t=0))
        center_attend_fig.update_layout(yaxis_range=[0, y_range], height=350, margin=dict(l=10, r=10, t=0))

        updated_header = student.split(" ")[0] + "'s Attendance"

        # Update averages later
        #avg_mr = statistics.mean(list(low_attend_report['Mastery Rate']))

        #center_summary = pd.DataFrame({'Mastery Rate': [avg_mr]})

        return fig2, None, updated_header, student, center_attend_fig

    @callback(
        Output('initial-attend-graph', 'figure'),
        Input('pandas-dropdown-1', 'value')
    )
    def update_initial_attend_graph(student):
        
        bar_trace = go.Bar(name="Attendance",x=list(all_attendance_df.index), y=all_attendance_df[student], showlegend=False)#, marker_color='#292929')
        
        moving_avg = list(all_attendance_df[student].copy(deep=True).rolling(window=3, min_periods=1).mean())
        scatter_trace = go.Scatter(name="Avg", x=list(all_attendance_df.index), y=moving_avg, showlegend=False)

        fig3 = go.Figure(data=[bar_trace, scatter_trace])
        fig3.update_layout(font_family = "Arial", font_color="black", bargap=0.2, height=350, margin=dict(l=5, r=20, b=20, t=40), title="Attendance Over Time")

        return fig3

    @callback(
            Output('student-summary-table','data'),
            Input('pandas-dropdown-1', 'value')
    )
    def update_student_summary(student):

        student_summary = summaries[summaries['Full Name']==student]
        student_summary = student_summary.drop('Full Name', axis = 1)

        return student_summary.to_dict('records')

    @callback(
        Output('pandas-dropdown-3', 'disabled'),
        Input('pandas-dropdown-2', 'value')
    )
    def update_dropdown2_selectable(report):
        disabled=False
        if report=="Center Report":
            disabled = True
        return disabled

    @callback(
        Output('lp-table', 'data'),
        Input('pandas-dropdown-1', 'value'),
        Input('pandas-dropdown-3', 'value')
        )
    def update_LP(student, learning_plan_name):
        chosen_LP = process_df[student]
        chosen_LP = chosen_LP[chosen_LP['Learning Plan Name']==learning_plan_name].to_dict('records')
        return chosen_LP
    
    @callback(
        Output('pk-chart', 'figure'),
        Input('pandas-dropdown-1', 'value'),
    )
    def update_PK_graph(student):
        fig = pk_process_fig(student, pk_completion)
        fig.update_layout(font_family = "Arial", font_color="black", bargap=0.2, height=350, margin=dict(l=5, r=20, b=20, t=40), title='Number of Sessions to Complete PK')
        return fig
    
    @callback(
        Output('lp-header', 'children'),
        Input('pandas-dropdown-1', 'value')
    )
    def update_lp_header(student):
        first_name = student.split(" ")[0]
        updated_header = first_name + "'s Student Summary"
        return updated_header
    
    dash.register_page("main", path = '/', layout = main_view)
    dash.register_page("attend",layout = center_view)

# --------------------------------------------------------------------------------------------------------------
    # APP LAYOUT
    app.layout = html.Div([ 
    html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
    html.Div(['Student'],style={'display':'inline-block','width':'47%', 'verticalAlign':'top'}),
    html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
    html.Div(['Learning Plan'],style={'display':'inline-block','width':'33%', 'verticalAlign':'top'}),
    html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
    html.Div(['Display'],style={'display':'inline-block','width':'17%', 'verticalAlign':'top'}),
# --------------------------------------------------------------------------------------------------------------
    html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
    html.Div([
        dcc.Dropdown(
            options = list(student_roster),
            value = first_student,
            id='pandas-dropdown-1')   
    ],style={'display':'inline-block','width':'47%', 'verticalAlign':'top'}),
    html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
    html.Div([
        dcc.Dropdown(
            options = learning_plans,
            value = most_recent_lp,
            id='pandas-dropdown-3')   
    ],style={'display':'inline-block','width':'33%', 'verticalAlign':'top'}),
    html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
    html.Div([
        dcc.Dropdown(
            options = [
            {
            "label":dcc.Link(children="Student Report" ,href='/'),
            "value":"Student Report"},
            {
            "label":dcc.Link(children="Center Report" ,href='/attend'),
            "value":"Center Report"
            },
        ],
            value = 'Student Report',
            id='pandas-dropdown-2')   
    ],style={'display':'inline-block','width':'16.5%', 'verticalAlign':'top'}),
    html.Div(style={'display':'inline-block','width':'0.5%', 'verticalAlign':'top'}),
    dash.page_container])

def pk_process_fig(student, pk_completion):

    pk_names = []
    worked_on_num = []
    
    with open("pk_completion.json", "w") as f:
        json.dump(pk_completion, f)

    # process...
    for key, val in pk_completion[student].items():
        
        if type(val) != dict: continue

        full_pk_id = key.split('(')[0].strip()
        
        pk_delim = full_pk_id.split("-")

        if len(pk_delim)>=3:
            pk_id = pk_delim[0] + "-" + pk_delim[1]
        else:
            pk_id = full_pk_id

        pk_names.append(pk_id)
    
        worked_on_num.append(val['Worked On'])

    pk_df = pd.DataFrame({'Name':pk_names, 'Sessions Worked On': worked_on_num})

    # Create bar chart
    fig = go.Figure(
        data=[go.Bar(
            x=pk_df['Name'],
            y=pk_df['Sessions Worked On'])])

    avg_sessions = pk_completion[student]["Average Sessions to Master PK"]

    y = [avg_sessions]*len(pk_df['Name'])

    fig.add_traces(
        go.Scatter(
            x=pk_df['Name'],
            y=y,
            mode = 'lines',
            line=dict(color='red',dash='dash')))

    fig.update_layout(showlegend = False)

    return fig

sessions_left = process.sessions_scrape()
sessions_left['Full Name'] = sessions_left['First Name'].astype(str) + " " + sessions_left['Last Name'].astype(str)

sessions_left, all_attendance_df, sessions_per_m, center_attend_avg = process.attend_scrape(sessions_left)
learn_plan_df, inactive_students = process.learn_plan_scrape()
print("Unable to find data for the following students: ", inactive_students)

app = dash.Dash(__name__,use_pages=True, pages_folder="",external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

app_layout(app, learn_plan_df, sessions_left, all_attendance_df, sessions_per_m, center_attend_avg)

attendance_json = all_attendance_df.to_dict('index', into=OrderedDict)

with open("attendance.json", "w") as f:
    json.dump(attendance_json, f)

deploy()

# if __name__ == '__main__':
#     app.run() 

if __name__ == '__main__':
    if not os.getenv('DASH_NO_SERVER'):
        app.run()
