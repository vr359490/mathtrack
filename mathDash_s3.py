import pandas as pd
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
import dash
from dash import dash_table, dcc, html, Input, Output, callback
import pprint
import threading
import os
from dotenv import load_dotenv
import webbrowser
import plotly.graph_objects as go
from io import StringIO, BytesIO

import time
import calendar
import datetime

import boto3
bucket = "mathdashbucket"

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

s3 = boto3.client("s3",
                      aws_access_key_id=AWS_ACCESS_KEY,
                      aws_secret_access_key=AWS_SECRET_KEY,
                      region_name="us-east-2")

def get_browser(url):
    options = Options()
    #options.add_argument("--headless")
    options.add_argument('--disable-dev-shm-usage')
    browser = webdriver.Chrome(options=options)
    browser.get(url)
    return browser

def login(browser, wait):

    # Load credentials securely
    # load_dotenv()
    USERNAME = os.getenv("MATHNASIUM_USERNAME")
    PASSWORD = os.getenv("MATHNASIUM_PASSWORD")

    # Login
    username_field = browser.find_element(By.ID, "UserName")
    username_field.send_keys(USERNAME)

    password_field = browser.find_element(By.ID, "Password")
    password_field.send_keys(PASSWORD)

    login_field = wait.until(EC.presence_of_all_elements_located((By.ID, "login")))
    browser.execute_script("arguments[0].click();", login_field[0])

def learn_plan_scrape(browser, wait, student_roster):

    inactive_students = []

    all_student_LP = {}

    # url = 'https://radius.mathnasium.com/LearningPlan'
    # browser.get(url)

    # studentDropdown = wait.until(EC.presence_of_all_elements_located((By.ID, "studentDropDownList")))

    # showInactiveCheckBox = wait.until(EC.presence_of_all_elements_located((By.ID, "showinactive")))
    # browser.execute_script("arguments[0].click();", showInactiveCheckBox[0])

    # for i in range(len(student_roster)):
        
    #     full_name = student_roster["Full Name"][i]

    #     browser.execute_script("arguments[0].click();", studentDropdown[0])

    #     string_match = "//*[contains(text(), " + "'" + full_name + "'" + ")]"

    #     try:
    #         # wait up to 10 seconds for the element to be clickable
    #         student_dropdown_item = wait.until(EC.element_to_be_clickable((By.XPATH, string_match)))
    #         browser.execute_script("arguments[0].click();", student_dropdown_item)

    #     except TimeoutException:
    #         print("Element not clickable—doing something else instead.")
    #         inactive_students.append(full_name)
    #         continue
        
    #     lp = export_excel(wait)
    #-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0
    # def round2(s3):

    #     ulti = s3.list_objects_v2(Bucket=bucket, Prefix="learning_plans/")
    #     pprint.pprint(ulti)
    #     xlsx_keys = [
    #             obj["Key"] for obj in ulti.get("Contents",[])
    #             if obj["Key"].endswith(".xlsx")
    #         ]
    #     pprint.pprint(xlsx_keys)
    #     for obj in xlsx_keys:

    #         response = s3.get_object(Bucket=bucket, Key=obj)
            
    #         obj_content = response["Body"].read()
    #         obj_content = BytesIO(obj_content)

    #         lp = pd.read_excel(obj_content)
    #     return lp

    ulti = s3.list_objects_v2(Bucket=bucket, Prefix="learning_plans/")
    pprint.pprint(ulti)

    xlsx_keys = [
            obj["Key"] for obj in ulti.get("Contents",[])
            if obj["Key"].endswith(".xlsx")
        ]

    #for i in range(len(student_roster)):


    for obj in xlsx_keys:

        response = s3.get_object(Bucket=bucket, Key=obj)
        
        obj_content = response["Body"].read()
        obj_content = BytesIO(obj_content)

        lp = pd.read_excel(obj_content)

        print(lp)
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

def sessions_scrape(wait):

    # centerDropdown = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@class='theGCSMulti']//input[@class='k-input k-readonly']")))

    # time.sleep(2)

    # centerDropdown.send_keys('v') # 'v' for Verona

    # time.sleep(5)
    # centerDropdown.send_keys(Keys.ENTER)

    # time.sleep(3)
    # table = wait.until(EC.presence_of_all_elements_located((By.ID, "gridRoster")))
    # roster = table[0].get_attribute('outerHTML')

    # roster_df = pd.read_html(StringIO(roster))[0]

    # sessions_left = roster_df[['First Name', 'Last Name','Membership Type', 'Remaining']]

    # sessions_left.to_csv('sessions_left.csv', index=False)

    sessions_left = down(s3, 'sessions_left.csv')
    print(sessions_left)
    print(sessions_left.columns)

    return sessions_left

def dwp_scrape(browser, wait):

    # Should we have different functions for scraping ALL data vs. scraping the
    # most recent? Or can we get away with scraping all data manually one time?

    url = "https://radius.mathnasium.com/DigitalWorkoutPlan/Report"
    browser.get(url)

    quickDateList = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[@class='k-widget k-dropdown form-control searchGridDropDown qdFilter']")))
    quickDateList.click()

    time.sleep(2)

    # The following is pulled from the UI element. It tells what number corresponds to what time range
    # 3 is "Last 7 Days" for example
    # {"dataSource":[{"Text":"Last 90 days","Value":"-1"},{"Text":"Last 60 days","Value":"1"},{"Text":"Last 30 days","Value":"2"},{"Text":"Last 7 days","Value":"3"},{"Text":"This month","Value":"0"},{"Text":"Today","Value":"7"}],"dataTextField":"Text","dataValueField":"Value","optionLabel":"Select"});});

    # Can we figure out how to do longer date ranges? We would need to interact with the Kendo calender element

    browser.execute_script("$('#dwpQuickDate').data('kendoDropDownList').value('-1');")  # 3 corresponds with "Last 7 Days"
    browser.execute_script("$('#dwpQuickDate').data('kendoDropDownList').trigger('change');")  # Trigger change event

    searchButton = browser.find_element(By.ID, "btnsearch")

    time.sleep(3)
    searchButton.click()

    time.sleep(5)

    data = export_excel(wait)

    pk_completion = str_process(data)

    return pk_completion

def down(s3, filename):

    #filename = None

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
            zaza = pd.read_csv(obj_content)
        else:
            zaza = pd.read_excel(obj_content)
        

    return zaza

def dwp_scrape_ALL():

    # path = "/Users/victorruan/Desktop/mathnasium_dash_files/DWP_Report_(All).xlsx"

    # data = pd.read_excel(path)

    filename = "DWP_Report_(All).xlsx"

    data = down(s3, filename)

    pk_completion = str_process(data)

    return pk_completion

def str_process(data):
    
    pk_completion = {}

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

        pk_completion[student]["Average Sessions to Master PK"] = pk_completion[student]["Total Sessions Worked On"]/pk_completion[student]["Number of PKs"] 
    
    return pk_completion

def export_excel(wait):

    download_path = "/Users/victorruan/Downloads"

    # List current files in Downloads
    pre = os.listdir(download_path)

    export = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Excel')]")))
    export.click()

    post = os.listdir(download_path)

    # Check download files before and after hitting export to check completed downloaded
    while len(pre)==len(post):
        time.sleep(1)
        post = os.listdir(download_path)

    new_files = set(post) - set(pre)

    # If there's a new file, pop it from the set
    filename = new_files.pop() if new_files else None

    if filename is None:
        raise FileNotFoundError("No new file was downloaded.")

    path = download_path + "/" + filename

    data = pd.read_excel(path)

    return data

def app_layout(app, process_df, student_roster, attendance_df, all_attendance_df, low_attend_report):

    pk_completion = dwp_scrape_ALL()

    student_summary = attendance_df.loc[attendance_df['Full Name']=='A.J. Kuehn']
    student_summary.loc[0, 'Mastery Rate']= round(pk_completion['A.J. Kuehn']["Average Sessions to Master PK"],2)

    learning_rate = float(round(1/student_summary['Mastery Rate'], 2))
    
    student_summary.loc[0,'Learning Rate'] = learning_rate

    low_attend_report = low_attend_report[['Full Name','Membership Type','Remaining','This Month Attendance','Avg Attend/m']]

    student_summary = student_summary.drop('Full Name', axis = 1)
    
    learning_plans = list(process_df['A.J. Kuehn']['Learning Plan Name'].unique())

    # Initialize main page layout
    main_view = html.Div([
        html.Div([
        html.H5(id = 'lp-header'),
        dash_table.DataTable(
            id='lp-table',
            columns=[{"name": i, "id": i} for i in process_df['A.J. Kuehn'].columns if i != 'Learning Plan Name'],
            style_table={'height': '300px'},
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
    ],style={'display':'inline-block','width':'48%', 'verticalAlign':'top'}),
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
                    "Learning Rate":"Average number of PKs completed per session. This is calculated as 1/(Mastery Rate)"},
                style_header_conditional=[{
                    'if': {'column_id': col},
                    'textDecoration': 'underline'
                } for col in ['Mastery Rate', 'Learning Rate']],

                tooltip_delay=0,
                tooltip_duration=None,
                    
                # The following has no effect.
                # How can we change tooltip font size (to match table font)?
                css=[{
                    'selector': '.dash-table-tooltip',
                    'font-size': '12px'
                }]
            )
        ]),
        html.Div(style={'width':'10%', 'height':'10px'}),
        html.H5("Number of Sessions to Complete PK"),
        
        # Graph component to display the Plotly bar chart
        dcc.Graph(
            id='pk-chart',
        ),
        
    ], style={'display':'inline-block','width':'51%', 'verticalAlign': 'top'}), 
    ])

    attend_view = html.Div([
                    html.Div([
                        html.H5('Student Attendance'), 
                        html.Div([
                        html.Div(['I only want to see students with average attendance below '],
                                     title = 'Filter report to show students with below a certain attendance number'
                                     ,style={'display':'inline-block', 'verticalAlign': 'top'}),
                        html.Div([
                        dcc.Dropdown(list(range(21)),
                                     clearable = False,
                                     optionHeight = 25,
                                     value = 20,
                                     id = 'attend-dropdown',
                                     className = "attendDropdown")]
                                     ,style={'display':'inline-block','width':'8%', 'font-size':'88%','verticalAlign': 'top','margin-left':'5px'}),
                        ]),
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
                                {'if' :{'column_id': 'Remaining'}, 'width':'14%' },
                                {'if' :{'column_id': 'Avg Attend/m'}, 'width':'16%' },
                                {'if' :{'column_id': 'Avg Attend/m'}, 'textAlign':'right'}
                                ]
            
        )],style={'display':'inline-block','width':'48%', 'verticalAlign':'top'}),
        html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
        html.Div([
            html.H5(id = 'attendance-header'),
            dcc.Graph(
                id = 'attend-graph',
            ),
            html.Div(id='test')
    ],style={'display':'inline-block','width':'51%', 'verticalAlign':'top'}),
    ])

    @callback(
        Output('low-attend', 'data'),
        Input('attend-dropdown', 'value')
    )
    def update_attendance_report(threshold):
        return low_attend_report[low_attend_report['Avg Attend/m']<threshold].to_dict('records')
    
    @callback(
        Output('attend-graph', 'figure'),
        Output('low-attend', 'active_cell'),
        Output('attendance-header', 'children'),
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
        
        bar_trace = go.Bar(x = list(all_attendance_df.index), y = all_attendance_df[student])
        moving_avg = list(all_attendance_df[student].copy(deep=True).rolling(window=3, min_periods=1).mean())

        scatter_trace = go.Scatter(x = list(all_attendance_df.index), y = moving_avg)
        
        fig2 = go.Figure(data=[bar_trace, scatter_trace])
        fig2.update_layout(bargap=0.2, height=350, margin=dict(l=30, r=30, b=25, t=25), showlegend=False)

        updated_header = 'Attendance Over Time For ' + student.split(" ")[0]
        
        return fig2, None, updated_header

    @callback(
            Output('student-summary-table','data'),
            Input('pandas-dropdown-1', 'value')
    )
    def update_attendance(student):
        student_summary = attendance_df.loc[attendance_df['Full Name']==student]
        student_summary['Mastery Rate'] = round(pk_completion[student]["Average Sessions to Master PK"], 2)
        
        learning_rate = 1/student_summary['Mastery Rate']
        student_summary['Learning Rate'] = float(round(learning_rate,2))

        return student_summary.to_dict('records')

    @callback(
        Output('pandas-dropdown-3', 'options'),
        Input('pandas-dropdown-1', 'value')
    )
    def update_dropdown3_list(student):
        return list(process_df[student]['Learning Plan Name'].unique())

    @callback(
        Output('pandas-dropdown-3', 'disabled'),
        Input('pandas-dropdown-2', 'value')
    )
    def update_dropdown2_selectable(report):
        disabled=False
        if report=="Attendance Report":
            disabled = True
        return disabled

    @callback(
        Output('pandas-dropdown-3', 'value'),
        Input('pandas-dropdown-1', 'value'))
    def update_dropdown3_val(student):
        assigned = pd.to_datetime(process_df[student]['Assigned'])
    
        max_date = assigned.max()

        index = assigned[assigned==max_date].index

        index_max_date = list(index)[0]
        
        most_recent_lp = process_df[student]['Learning Plan Name'][index_max_date]

        return most_recent_lp

    @callback(
        Output('lp-table', 'data'),
        Input('pandas-dropdown-1', 'value'),
        Input('pandas-dropdown-3', 'value'))
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

# --------------------------------------------------------------------------------------------------------------
    # APP LAYOUT
    app.layout = html.Div([ 
    html.Div(['Student'],style={'display':'inline-block','width':'48%', 'verticalAlign':'top'}),
    html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
    html.Div(['Learning Plan'],style={'display':'inline-block','width':'33%', 'verticalAlign':'top'}),
    html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
    html.Div(['Display'],style={'display':'inline-block','width':'17%', 'verticalAlign':'top'}),
# --------------------------------------------------------------------------------------------------------------
    html.Div([
        dcc.Dropdown(
            options = list(student_roster),
            value = 'A.J. Kuehn',
            id='pandas-dropdown-1')   
    ],style={'display':'inline-block','width':'48%', 'verticalAlign':'top'}),
    html.Div(style={'display':'inline-block','width':'1%', 'verticalAlign':'top'}),
    html.Div([
        dcc.Dropdown(
            options = learning_plans,
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
            "label":dcc.Link(children="Attendance Report" ,href='/attend'),
            "value":"Attendance Report"
            },
        ],
            value = 'Student Report',
            id='pandas-dropdown-2')   
    ],style={'display':'inline-block','width':'17%', 'verticalAlign':'top'}),
    dash.page_container])
# --------------------------------------------------------------------------------------------------------------
# def open_browser():
#     time.sleep(2)  # Allow a brief moment for the server to start
#     webbrowser.open("http://127.0.0.1:8050/")
#     quit()

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

    # path = "/Users/victorruan/Desktop/mathnasium_dash_files/Attendance_(All).xlsx"
    # attendance = pd.read_excel(path)

    attendance = down(s3, "Attendance_(All).xlsx")

    attendance['Full Name'] = attendance['First Name'].astype(str) + ' ' + attendance['Last Name'].astype(str)

    attendance_df, all_attendance_df, low_attend_report = attend_process(attendance, sessions_left)

    return attendance_df, all_attendance_df, low_attend_report

def attend_process(attendance, sessions_left):

    roster = list(sessions_left['Full Name'])

    attendance_col = []
    avg_attendance_col = []
    now = datetime.datetime.now()
    current_month = now.strftime("%B")

    month_list = list(calendar.month_name)

    attend_dict = {}

    for student in roster:
        # Inactive students are sometimes listed in roster, but not attendance?
        if student in list(attendance['Full Name']):

            attend_dict[student] = {}

            # Grab all attendance rows for student. 
            # There will be two if they've had two different attendance packages
            attend_packages = attendance.loc[attendance['Full Name']==student]
            attend_packages = attend_packages.to_dict('records')

            # We are assuming current month doesn't appear twice.
            # We should test if it's possible by grabbing a date range longer than a year.
            for package in attend_packages: 
                for key, value in package.items():
                    if key in month_list:
                        if key not in attend_dict[student].keys():
                            attend_dict[student][key] = 0

                        value = string_check(value)
                        attend_dict[student][key] += value 

            current_month_attendance = attend_dict[student][current_month]
            attendance_col.append(current_month_attendance)

            all_attendance_df = pd.DataFrame(attend_dict)

            avg_attendance = all_attendance_df[student].mean()
            avg_attendance_col.append(avg_attendance)

    sessions_left['This Month Attendance'] = attendance_col 

    avg_attendance_col = [round(average, 2) for average in avg_attendance_col]
    sessions_left['Avg Attend/m'] = avg_attendance_col

    # We should probably send sessions_left in full then separate in to attendance_df and low_attend_report later
    low_attend_report = sessions_left.copy(deep = True)

    attendance_df = sessions_left[['Full Name','Membership Type','Remaining','Avg Attend/m','This Month Attendance']]

    return attendance_df, all_attendance_df, low_attend_report

def string_check(string):
    if string[0:2].isnumeric():
        value = string[0:2]
    elif string[0:1].isnumeric():
        value = string[0]
    else:
        value = 0
    return int(value)

app = dash.Dash(__name__, use_pages=True, pages_folder="")
server = app.server

#def main():
print("run")

# Initialize browser at given URL
# Scraping Roster first allows us to gather list of student names
# url = 'https://radius.mathnasium.com/Attendance/Roster'
# browser = get_browser(url)

browser = ""
wait = ""

# wait = WebDriverWait(browser, 10)

# Grab credentials and login
#login(browser, wait)

# Web scrape stage
sessions_left = sessions_scrape(wait)
sessions_left['Full Name'] = sessions_left['First Name'].astype(str) + " " + sessions_left['Last Name'].astype(str)
#sessions_left = sessions_left.head(2)

# Do we care about attendance of inactive students?
attendance_df, all_attendance_df, low_attend_report = attend_scrape(sessions_left)
learn_plan_df, inactive_students = learn_plan_scrape(browser, wait, sessions_left)
print("Unable to find data for the following students: ", inactive_students)

# Done scraping
#browser.quit()

# Initialize CSS styling and dash app
# external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
# CSS is placed in styles.css

# App settings and layout
app_layout(app, learn_plan_df, sessions_left['Full Name'], attendance_df, all_attendance_df, low_attend_report)

# Run dash app
if __name__ == '__main__':
    #threading.Thread(target=open_browser, daemon=True).start()  # Start browser in background
    app.run() 
#main()