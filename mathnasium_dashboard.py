import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
import dash
from dash import dash_table
import time
import threading
import os
from dotenv import load_dotenv
import webbrowser
from dash import dcc, html
import plotly.graph_objects as go
from io import StringIO


def get_browser(url):
    options = Options()
    #options.add_argument("--headless")
    options.add_argument('--disable-dev-shm-usage')

    browser = webdriver.Chrome(options=options)
    browser.get(url)
    return browser

def login(browser):

    # Load credentials securely
    # load_dotenv()
    # USERNAME = os.getenv("MATHNASIUM_USERNAME")
    # PASSWORD = os.getenv("MATHNASIUM_PASSWORD")

    USERNAME = 'scott.zettek'
    PASSWORD = 'notredame70'

    # Login
    username_field = browser.find_element(By.ID, "UserName")
    username_field.send_keys(USERNAME)

    password_field = browser.find_element(By.ID, "Password")
    password_field.send_keys(PASSWORD)

    login_field = browser.find_element(By.ID, "login")
    login_field.click()

def learn_plan_scrape_re(browser, wait):

    studentDropdown = wait.until(EC.presence_of_all_elements_located((By.ID, "studentDropDownList")))

    browser.execute_script("arguments[0].click();", studentDropdown[0])

    AJ = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Kuehn')]")))
    AJ.click()

    data = export_excel(wait)
    
    # export = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Excel')]")))
    # export.click()

    # download_path = "/Users/victorruan/Downloads"

    # pee = os.listdir(download_path)

    # # Instead of hardcoding seconds, implement dynamic checking of download
    # time.sleep(7)

    # poo = os.listdir(download_path)

    # filename = None
    # for i,j in enumerate(poo): 
    #     if filename != None:
    #         break
    #     elif poo[i] != pee[i]:
    #         filename = poo[i]

    # student_path = download_path + "/" + filename

    # data = pd.read_excel(student_path)

    return data

def export_excel(wait):
    export = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Excel')]")))
    export.click()

    download_path = "/Users/victorruan/Downloads"

    pee = os.listdir(download_path)

    # Instead of hardcoding seconds, implement dynamic checking of download
    time.sleep(7)

    poo = os.listdir(download_path)

    filename = None
    for i,j in enumerate(poo): 
        if filename != None:
            break
        elif poo[i] != pee[i]:
            filename = poo[i]

    student_path = download_path + "/" + filename

    data = pd.read_excel(student_path)
    return data

def find_sessions_left(browser, wait):
    sessions_left = None
    url = 'https://radius.mathnasium.com/Attendance/Roster'
    browser.get(url)

    #centerDropdown = wait.until(EC.visibility_of_element_located((By.ID, "AllCenterListMultiSelect_taglist")))
    #centerDropdown = wait.until(EC.presence_of_element_located((By.XPATH, "theGCSMulti")))
    #centerDropdown = browser.find_element(By.XPATH, "//div[@class='theGCSMulti']//input[@class='k-input k-readonly']")
    centerDropdown = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@class='theGCSMulti']//input[@class='k-input k-readonly']")))

    time.sleep(2)

    centerDropdown.send_keys('v')

    time.sleep(5)
    centerDropdown.send_keys(Keys.ENTER)

    time.sleep(3)

    table = wait.until(EC.presence_of_all_elements_located((By.ID, "gridRoster")))
    roster = table[0].get_attribute('outerHTML')

    df = pd.read_html(StringIO(roster))[0]

    for i in df['Remaining']:
        print('Sessions remaining: ',i)

    return sessions_left

def worked_on_status(browser, wait):

    worked_on = None

    url = "https://radius.mathnasium.com/DigitalWorkoutPlan/Report"

    browser.get(url)

    #quickDateList = browser.find_element(By.XPATH, "//div[@class='form_group']//span[@class='k-input']") 
    quickDateList = browser.find_element(By.XPATH, "//span[@class='k-widget k-dropdown form-control searchGridDropDown qdFilter']") 
    #print(len(quickDateList))
    print(quickDateList)
    print(quickDateList.get_attribute('outerHTML'))
    quickDateList.click()

    time.sleep(2)

    browser.execute_script("$('#dwpQuickDate').data('kendoDropDownList').value('3');")  # Select "Today"
    browser.execute_script("$('#dwpQuickDate').data('kendoDropDownList').trigger('change');")  # Trigger change event

    time.sleep(5)

    searchButton = browser.find_element(By.ID, "btnsearch")
    searchButton.click()

    time.sleep(5)

    DWP_table = browser.find_element()

    # data = export_excel(wait)
    # print(data)
    
    return worked_on

def process_pk_completion(browser, df):

    process_df = pd.DataFrame()
    process_df = df[['Description','Questions','LP Order', 'Topic/Sub-Topic', 'Date Assigned', 'Date Completed']]

    browser.quit() 

    xval = process_df['Description'].values.tolist()

    for i,j in enumerate(xval):
        new_val = j.split(' ')[0]
        xval[i] = new_val

    begin_date = process_df['Date Assigned']
    complete_date = process_df['Date Completed']

    num_completed = len(complete_date.dropna())

    yval2 = []
    for k in range(num_completed):
        start = pd.to_datetime(begin_date[k])
        end = pd.to_datetime(complete_date[k])
        days_to_complete = end-start
        if days_to_complete.days > 0:
            yval2.append(days_to_complete.days)
        else:
            yval2.append(0)

    test_df = pd.DataFrame({
        'Category': xval[0:num_completed],
        'Value': yval2
    })

    return test_df, process_df

def app_layout(app, process_df, fig):

    app.layout = html.Div([
    html.Div([
        html.H2('AJ Keuhn Learning Plan'),
        dash_table.DataTable(
            id='table',
            columns=[{"name": i, "id": i} for i in process_df.columns],
            style_table={'height': '300px'},
            style_cell={
                'overflow': 'hidden',
                'textOverflow': 'ellipsis',
                'maxWidth': 0,
                'textAlign': 'left',
                'font-family':'Arial',
                'fontSize':12
            },
            data=process_df.to_dict('records')
        )
    ],style={'width':'58%'}),
        html.Div([  # This will be the right side with the Graph
            html.H3("Days to Completion by PK"),
            
            # Graph component to display the Plotly bar chart
            dcc.Graph(
                id='bar-chart',
                figure=fig,
                style = {'height': '320px'}
            )
        ], style={'width': '48%', 'verticalAlign': 'top'})
    ], style={'display':'flex'})

def open_browser():
    time.sleep(2)  # Allow a brief moment for the server to start
    webbrowser.open("http://127.0.0.1:8050/")
    quit()

def main():

    # Initialize browser at given URL
    url = 'https://radius.mathnasium.com/LearningPlan'
    browser = get_browser(url)
    wait = WebDriverWait(browser, 10)

    # Grab credentials and login
    login(browser)
    
    # Scrape learning plan
    
    worked_on = None
    worked_on_status(browser, wait)
    if worked_on == None:
        return

    df = learn_plan_scrape_re(browser, wait)
    sessions_left = find_sessions_left(browser, wait)
    
    # Process, create df for PK Days to Completion data
    test_df, process_df = process_pk_completion(browser, df)

    # Create a bar chart using plotly.graph_objects
    fig = go.Figure(data=[go.Bar(x=test_df['Category'], y=test_df['Value'])])

    # Initialize dash app
    app = dash.Dash(__name__)

    # App settings and layout
    app_layout(app, process_df, fig)

    # Run dash app
    if __name__ == '__main__':
        threading.Thread(target=open_browser, daemon=True).start()  # Start browser in background
        app.run()  

main() 

#-----------------------------------------------------------------------------

# The following is unneeded



# import pytesseract
# from pytesseract import Output
# from PIL import Image
# import cv2
# from selenium.common.exceptions import WebDriverException

# pytesseract.pytesseract.tesseract_cmd = "/usr/local/bin/tesseract"



    # n = 54

    # completed_dates=['9/12/2024','9/17/2024','9/19/2024','9/24/2024','9/24/2024',
    #                 '10/1/2024','10/8/2024','10/10/2024','10/15/2024','10/17/2024',
    #                 '11/5/2024','11/21/2024','11/26/2024','11/27/2024',
    #                 '12/3/2024','12/10/2024','12/17/2024','12/17/2024','12/23/2024','12/23/2024','12/23/2024',
    #                 '1/2/2025','1/9/2025','1/13/2025','1/28/2025','1/28/2025',
    #                 '2/4/2025','2/4/2025','2/6/2025','2/25/2025','2/26/2025',
    #                 '3/4/2025','3/6/2025','3/11/2025','3/20/2025','3/24/2025','3/24/2025',]

    # num_completed = len(completed_dates)

    # completed_dates = completed_dates + [np.nan]*(n-len(completed_dates))

    # df['Date Completed'] = pd.DataFrame({'Date Completed': completed_dates})

# def save_screenshot(browser: webdriver.Chrome, path: str = '/tmp/screenshot.png') -> None:
#     original_size = browser.get_window_size()
#     required_width = browser.execute_script('return document.body.parentNode.scrollWidth')
#     required_height = browser.execute_script('return document.body.parentNode.scrollHeight')
#     browser.set_window_size(required_width, required_height)
#     browser.find_element(By.TAG_NAME,'body').screenshot(path)  # avoids scrollbar
#     browser.set_window_size(original_size['width'], original_size['height'])

# def learn_plan_scrape(browser, wait):

#     studentDropdown = wait.until(EC.presence_of_all_elements_located((By.ID, "studentDropDownList")))

#     browser.execute_script("arguments[0].click();", studentDropdown[0])

#     AJ = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Kuehn')]")))
#     AJ.click()

#     # DO WE NEED THIS SLEEP????? 5 SECONDS IS A LONG TIME
#     time.sleep(5)

#     table = wait.until(EC.presence_of_all_elements_located((By.ID, "gridLP")))
#     AJ_table = table[0].get_attribute('outerHTML')

#     AJ_table = StringIO(AJ_table)

#     df = pd.read_html(AJ_table)[0]

#     return df