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

import pprint

import calendar
import datetime
from datetime import timedelta

import boto3
bucket = "mathdashbucket"

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

s3 = boto3.client("s3",
                      aws_access_key_id=AWS_ACCESS_KEY,
                      aws_secret_access_key=AWS_SECRET_KEY,
                      region_name="us-east-2")

def learn_plan_scrape():

    inactive_students = []

    all_student_LP = {}

    ulti = s3.list_objects_v2(Bucket=bucket, Prefix="learning_plans/")

    xlsx_keys = [
            obj["Key"] for obj in ulti.get("Contents",[])
            if obj["Key"].endswith(".xlsx")
        ]

    #path = "/Users/victorruan/Desktop/mathnasium_dash_files/learning_plans/"

    for obj in xlsx_keys:

    #for file in os.listdir(path):

        response = s3.get_object(Bucket=bucket, Key=obj)
        
        obj_content = response["Body"].read()
        obj_content = BytesIO(obj_content)

        #print(file)

        #full_path = path + file

        lp = pd.read_excel(obj_content)
        #lp = pd.read_excel(full_path)

        full_name=lp['Student'][0].strip()

        # Separate ID and title/name of each PK. This helps de-clutter the LP chart display
        list_pk_dual_keys = list(lp['Description'])

        list_pk_id = []
        list_pk_title = []

        for dual_key in list_pk_dual_keys:
            list_pk_id.append(dual_key[0:dual_key.find(" ")])
            list_pk_title.append(dual_key[dual_key.find(" "):])

        list_pk_id = pd.DataFrame(list_pk_id)
        list_pk_title = pd.DataFrame(list_pk_title)

        lp['ID'] = list_pk_id
        lp['Title'] = list_pk_title

        lp_trunc = lp[['ID','Title', 'Date Assigned', 'Date Completed', 'Learning Plan Name']]
        lp_trunc = lp_trunc.rename(columns = {'Date Assigned': 'Assigned'})
        lp_trunc = lp_trunc.rename(columns = {'Date Completed': 'Completed'})

        all_student_LP[full_name] = lp_trunc

    return all_student_LP, inactive_students

def sessions_scrape():

    sessions_left = down(s3, 'sessions_left.csv')
    
    #filename = "sessions_left.csv"

    #path = "/Users/victorruan/Desktop/mathnasium_dash_files/" + filename

    #sessions_left = pd.read_csv(path)

    return sessions_left

#Import files from AWS S3
def down(s3, filename):

    ulti = s3.list_objects_v2(Bucket=bucket)
    
    xlsx_keys = [
            obj["Key"] for obj in ulti.get("Contents", [])
            if obj["Key"].endswith(".xlsx")
        ]
    
    if filename: xlsx_keys=[filename]

    for obj in xlsx_keys:

        response = s3.get_object(Bucket=bucket, Key=obj)
        
        obj_content = response["Body"].read()

        obj_content = BytesIO(obj_content)

        if ".csv" in filename:
            df = pd.read_csv(obj_content)
        else:
            df = pd.read_excel(obj_content)

    return df

def dwp_scrape_ALL():

    filename = "DWP_Report_(All).xlsx"

    # path = "/Users/victorruan/Desktop/mathnasium_dash_files/" + filename

    # data = pd.read_excel(path)  

    data = down(s3, filename)

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
            pk_completion[student]["Number of Mastered PKs"] = 0
            pk_completion[student]["Total Sessions Worked On"] = 0
            pk_completion[student]["Total Sessions Worked On Mastered"] = 0

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

            worked_on_label = 'Worked On'
            mastered_label = 'Mastered'
            completed_label = 'Completed'

            # Clear extra spaces in string
            pk_ID_name_pair = pk_ID_name_pair.strip()

            if pk_ID_name_pair not in pk_completion[student].keys():
                pk_completion[student]["Number of PKs"] += 1
                pk_completion[student][pk_ID_name_pair] = {}

                if worked_on_label in status: 
                    pk_completion[student][pk_ID_name_pair][worked_on_label]=1
                    pk_completion[student][pk_ID_name_pair][mastered_label]=0
                    pk_completion[student]["Total Sessions Worked On"] += 1
                elif mastered_label in status: 
                    pk_completion[student][pk_ID_name_pair][worked_on_label]=1
                    pk_completion[student][pk_ID_name_pair][mastered_label]=1
                    pk_completion[student]["Total Sessions Worked On"] += 1
                    pk_completion[student]["Number of Mastered PKs"]+=1
                    pk_completion[student]["Total Sessions Worked On Mastered"]+=pk_completion[student][pk_ID_name_pair][worked_on_label]
                elif completed_label in status: 
                    pk_completion[student][pk_ID_name_pair][worked_on_label]=1
                    pk_completion[student][pk_ID_name_pair][completed_label]=1
                    pk_completion[student]["Total Sessions Worked On"] += 1
            else:       
                if worked_on_label in status: 
                    pk_completion[student][pk_ID_name_pair][worked_on_label]+=1
                    pk_completion[student]["Total Sessions Worked On"] += 1

                elif mastered_label in status:
                    if completed_label in list(pk_completion[student][pk_ID_name_pair].keys()):
                        pk_completion[student][pk_ID_name_pair][mastered_label]=1
                        pk_completion[student]["Number of Mastered PKs"]+=1
                        pk_completion[student]["Total Sessions Worked On Mastered"]+=pk_completion[student][pk_ID_name_pair][worked_on_label]
                    elif completed_label not in list(pk_completion[student][pk_ID_name_pair].keys()):
                        pk_completion[student][pk_ID_name_pair][mastered_label]=1
                        pk_completion[student]["Number of Mastered PKs"]+=1
                        
                        pk_completion[student][pk_ID_name_pair][worked_on_label]+=1
                        pk_completion[student]["Total Sessions Worked On Mastered"]+=pk_completion[student][pk_ID_name_pair][worked_on_label]
                        pk_completion[student]["Total Sessions Worked On"] += 1

                elif completed_label in status: 
                    if mastered_label not in list(pk_completion[student][pk_ID_name_pair].keys()):
                        # Addresses rare edges case of a PK being initially marked as Completed
                        # then marked as Completed again
                        pk_completion[student][pk_ID_name_pair][completed_label]=1
                    elif pk_completion[student][pk_ID_name_pair][mastered_label]==1:
                        pk_completion[student][pk_ID_name_pair][completed_label]=1
                    elif pk_completion[student][pk_ID_name_pair][mastered_label]==0:
                        pk_completion[student][pk_ID_name_pair][completed_label]=1
                        pk_completion[student][pk_ID_name_pair][worked_on_label]+=1

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
    index_max_date = list(index)[0]
    most_recent_lp = process_df[student]['Learning Plan Name'][index_max_date]
    return most_recent_lp

def app_layout(app, process_df,sessions_left, all_attendance_df, sessions_per_m):

    student_roster = sessions_left['Full Name']
    first_student = student_roster[0]
    attendance_df = sessions_left[['Full Name','Membership Type','Remaining','Avg Attend/m','This Month Attendance']]

    pk_completion = dwp_scrape_ALL()

    mr_list = []
    lr_list = []

    for student in student_roster:
         
        student_dict = pk_completion.get(student, None)

        if student_dict: 
            mr = student_dict["Average Sessions to Master PK"]
            lr = 1/mr

            mr = round(mr,2)
            lr = round(lr,2)
        else: 
            mr = None
            lr = None

        mr_list.append(mr)
        lr_list.append(lr)

    student_summary = attendance_df.loc[attendance_df['Full Name']==first_student]
    student_summary.loc[0, 'Mastery Rate'] = round(pk_completion[first_student]["Average Sessions to Master PK"],2)
    student_summary.loc[0,'Learning Rate'] = float(round(1/student_summary['Mastery Rate'], 2)) 

    low_attend_report = sessions_left.copy(deep = True)
    low_attend_report = low_attend_report[['Full Name','Membership Type','Remaining','Avg Attend/m']]
    low_attend_report = low_attend_report.rename(columns = {'Membership Type': 'Member Type'})

    low_attend_report['Mastery Rate'] = mr_list
    low_attend_report['Learning Rate'] = lr_list

    low_attend_report = low_attend_report = low_attend_report[['Full Name','Member Type','Remaining','Mastery Rate','Learning Rate','Avg Attend/m']]

    low_attend_report = low_attend_report.rename(columns = {'Mastery Rate': 'MR'})
    low_attend_report = low_attend_report.rename(columns = {'Learning Rate': 'LR'})

    for index, member_type in enumerate(low_attend_report['Member Type']):
        if "Package" in member_type:
            low_attend_report.loc[index,'Member Type'] = member_type.split(" ")[0]

    student_summary = student_summary.drop('Full Name', axis = 1)
    
    learning_plans = list(process_df[first_student]['Learning Plan Name'].unique())

    most_recent_lp = find_recent_lp(process_df, first_student)

    figgy=go.Figure(data=[go.Bar(x=list(sessions_per_m.index), y=sessions_per_m[0], showlegend=False)]) 
    figgy.update_layout(bargap=0.2, height=290, margin=dict(l=20, r=20, b=20, t=20), title='Total number of sessions by month')

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
                                    {'label':'Learning Rate','value':'LR'},
                                    {'label':'Mastery Rate','value':'MR'},
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

    # Initialize main page layout
    main_view = html.Div([
        html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
        html.Div([
        html.H5(id = 'lp-header'),
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
    html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
    html.Div([  # This will be the right side with the Graph
        html.H5("Student Summary"),
        html.Div([
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
            )
        ],style = {'display':'inline-block','width':'98.8%', 'verticalAlign':'top'}),
        html.Div(style={'display':'inline-block','width':'1.2%', 'verticalAlign':'top'}),
        html.Div(style={'width':'10%', 'height':'10px'}),
        html.H5("Number of Sessions to Complete PK"),
        
        # Graph component to display the Plotly bar chart
        dcc.Graph(
            id='pk-chart',
        ),
        
    ], style={'display':'inline-block','width':'51%', 'verticalAlign': 'top'}), 
    ])

    attend_view = html.Div([
    html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign': 'top'}),
    html.Div([
        html.H5(['Student Attendance'],style={'display':'inline-block','width':'84.5%', 'verticalAlign': 'top'}), 
        html.Div([
            html.Div(style={'height':'9px'}),
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
                    dbc.Button("Add filter", id="add-filter", n_clicks=0)
                    ],style={'display':'inline-block'}),
                    html.Div(style={'display':'inline-block', 'width':'20px'}),
                    html.Div([
                    dbc.Button("Close", id="close", n_clicks=0)
                    ],style={'display':'inline-block'})])
                ),
                    ],
                    id="modal",
                    size="lg",
                    centered=True,
                    backdrop="static",
                    is_open=False,
                ),
                ],style={'display':'inline-block','width':'15.5%', 'horizontalAlign': 'right'}),
                html.Div(style={'height':'10px'}),
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
                        {'if' :{'column_id': 'Full Name'}, 'width':'30%'},
                        {'if' :{'column_id': 'Remaining'}, 'width':'15%'},
                        {'if' :{'column_id': 'MR'}, 'width':'10%'},
                        {'if' :{'column_id': 'LR'}, 'width':'10%'},
                        {'if' :{'column_id': 'Avg Attend/m'}, 'width':'15%'},
                        {'if' :{'column_id': 'Avg Attend/m'}, 'textAlign':'right'},
                        ],
            tooltip_header={
                "MR":"Mastery Rate: This is the average number of sessions to master PK.",
                "LR":"Learning Rate: This is the average number of PKs completed per session."},

            tooltip_delay=0,
            tooltip_duration=None,

            style_header_conditional=[{
                'if': {'column_id': col},
                'textDecoration': 'underline'
        } for col in ['MR', 'LR']],
            
        )],style={'display':'inline-block','width':'47%', 'verticalAlign':'top'}),
        html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
        html.Div([
            html.H6(id = 'attendance-header'),
            dcc.Graph(
                id = 'attend-graph',
            ),
    ],style={'display':'inline-block','width':'51%', 'verticalAlign':'top', 'position':'fixed'}),#'position': 'fixed'}),
    ])

    #center_view = html.Div(id = "test")

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
        Input('close', 'n_clicks')
    )
    def modal_query(col0,col1,col2,col3, sign0,sign1,sign2,sign3, in0,in1,in2,in3, n_clicks):# mean_attend, n_clicks):
        
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
    [Input("open", "n_clicks"), Input("close", "n_clicks")],
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
    
    @callback(
        Output('attend-graph', 'figure'),
        Output('low-attend', 'active_cell'),
        Output('attendance-header', 'children'),
        Output('pandas-dropdown-1', 'value'),
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
        moving_avg = list(all_attendance_df[student].copy(deep=True).rolling(window=3, min_periods=1).mean())

        scatter_trace = go.Scatter(name="Avg", x=list(all_attendance_df.index), y=moving_avg, showlegend=False)
        
        fig2 = go.Figure(data=[bar_trace, scatter_trace])
        fig2.update_layout(bargap=0.2, height=350, margin=dict(l=30, r=30, b=25, t=0))#, title="SDLFDLSFKJDSLKJDL")

        updated_header = 'Attendance Over Time For ' + student.split(" ")[0]

        return fig2, None, updated_header, student

    @callback(
            Output('student-summary-table','data'),
            Input('pandas-dropdown-1', 'value')
    )
    def update_student_summary(student):
        student_summary = attendance_df.loc[attendance_df['Full Name']==student]
        student_summary['Mastery Rate'] = round(pk_completion[student]["Average Sessions to Master PK"], 2)
        
        learning_rate = 1/student_summary['Mastery Rate']
        student_summary['Learning Rate'] = float(round(learning_rate,2))

        return student_summary.to_dict('records')

    @callback(
        Output('pandas-dropdown-3', 'disabled'),
        Input('pandas-dropdown-2', 'value')
    )
    def update_dropdown2_selectable(report):
        disabled=False
        if report=="Center Overview":
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
        fig.update_layout(bargap=0.2, height=350, margin=dict(l=20, r=20, b=20, t=20))
        return fig
    
    @callback(
        Output('lp-header', 'children'),
        Input('pandas-dropdown-1', 'value')
    )
    def update_lp_header(student):
        updated_header = student + ' Learning Plan'
        return updated_header
    
    dash.register_page("main", path = '/', layout = main_view)
    dash.register_page("attend",layout = attend_view)
    #dash.register_page("center",layout = center_view)

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
            "label":dcc.Link(children="Center Overview" ,href='/attend'),
            "value":"Center Overview"
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

    # process...
    for key, val in pk_completion[student].items():
        
        if type(val) != dict: continue

        pk_name = key.split('(')[0].strip()
        pk_names.append(pk_name)
    
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

def attend_scrape(sessions_left):

    attendance = down(s3, "Attendance_(All).xlsx")

    # filename = "Attendance_(All).xlsx"

    # path = "/Users/victorruan/Desktop/mathnasium_dash_files/" + filename

    # attendance = pd.read_excel(path)

    attendance['Full Name'] = attendance['First Name'].astype(str) + ' ' + attendance['Last Name'].astype(str)

    month_list = list(calendar.month_name)

    for column in attendance.columns:

        bonth = []
        if column in month_list:

            for attend in attendance[column]:
                int_attend = string_check(attend)
                bonth.append(int_attend)

    sessions_left, all_attendance_df, sessions_per_m = attend_process(attendance, sessions_left)

    return sessions_left, all_attendance_df, sessions_per_m

def attend_process(attendance, sessions_left):

    roster = list(sessions_left['Full Name'])

    attendance_col = []
    avg_attendance_col = []

    today = datetime.datetime.today().day

    # If it's the first of the month, we want to grab data from last month instead.
    # ^Do we need to do this?
    if today==1:
        load_day = datetime.datetime.today() - timedelta(days=1)
    else:
        load_day = datetime.datetime.today()
    
    load_month = load_day.strftime("%B")

    month_list = list(calendar.month_name)

    attend_dict = {}

    for student in roster:
        # Inactive students are sometimes listed in roster, but not attendance?
        if student in list(attendance['Full Name']):

            attend_dict[student] = {}

            # Get attendance rows for student. There will be two if they've had two different attendance packages
            attend_packages = attendance.loc[attendance['Full Name']==student]
            attend_packages = attend_packages.to_dict('records')

            # We are assuming current month doesn't appear twice.
            # We should test if it's possible by grabbing a date range longer than a year.
            for package in attend_packages:
                for col, value in package.items():
                    if col in month_list:
                        month=col
                        if month not in attend_dict[student].keys():
                            attend_dict[student][month] = 0

                        value = string_check(value)
                        attend_dict[student][month] += value 

            current_month_attendance = attend_dict[student][load_month]
            attendance_col.append(current_month_attendance)

            avg_attendance = statistics.mean(list(attend_dict[student].values()))
            avg_attendance_col.append(avg_attendance)

    all_attendance_df = pd.DataFrame(attend_dict)

    sessions_per_m = {}
    index = []

    for i,colName in enumerate(all_attendance_df.T.columns):
        
        sessions_per_m[colName] = all_attendance_df.T[colName].sum()
        index.append(i)

    sessions_per_m = pd.DataFrame(sessions_per_m, index=[0])
    sessions_per_m = sessions_per_m.T

    sessions_left['This Month Attendance'] = attendance_col 

    avg_attendance_col = [round(average, 1) for average in avg_attendance_col]
    sessions_left['Avg Attend/m'] = avg_attendance_col

    return sessions_left, all_attendance_df, sessions_per_m

def string_check(string):
    if string[0:2].isnumeric():
        value = string[0:2]
    elif string[0:1].isnumeric():
        value = string[0]
    else:
        value = 0
    return int(value)

app = dash.Dash(__name__,use_pages=True, pages_folder="",external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

sessions_left = sessions_scrape()
sessions_left['Full Name'] = sessions_left['First Name'].astype(str) + " " + sessions_left['Last Name'].astype(str)

sessions_left, all_attendance_df, sessions_per_m = attend_scrape(sessions_left)
learn_plan_df, inactive_students = learn_plan_scrape()
print("Unable to find data for the following students: ", inactive_students)

app_layout(app, learn_plan_df, sessions_left, all_attendance_df, sessions_per_m)

if __name__ == '__main__':
    app.run() 
