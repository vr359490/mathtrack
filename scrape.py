import pandas as pd
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from io import StringIO
import boto3

import os
import time
import warnings
warnings.filterwarnings('ignore')

import requests

def deploy():
    print("Deploying...")
    deploy_hook_url = "https://api.render.com/deploy/srv-d02knrbe5dus73btej50?key=qbZbmE7kcQ0"
    response = requests.post(deploy_hook_url)
    print(response.status_code)

bucket = "mathdashbucket"

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

s3 = boto3.client("s3",
                      aws_access_key_id=AWS_ACCESS_KEY,
                      aws_secret_access_key=AWS_SECRET_KEY,
                      region_name="us-east-2")

def up(s3, file_path, save_as):

    with open(file_path, "rb") as f:
        s3.upload_fileobj(f, bucket, save_as)

def get_browser(url):
    options = webdriver.ChromeOptions()

    options.add_argument("--headless")
    options.add_experimental_option("prefs", {'profile.default_content_setting_values.automatic_downloads': 1})
    options.add_argument('--disable-dev-shm-usage')

    # Add these for GitHub Actions compatibility
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--remote-debugging-port=9222")

    
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

def export_excel(wait):
    download_path = "/Users/victorruan/Downloads"
    pre = set(os.listdir(download_path))

    # Click the Excel export button
    export_buttons = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//button[contains(text(), 'Excel')]")))
    export = export_buttons[1] if len(export_buttons) > 1 else export_buttons[0]
    browser.execute_script("arguments[0].click();", export)

    # Wait for new file to appear
    timeout = 450
    start_time = time.time()
    while True:
        post = set(os.listdir(download_path))
        new_files = post - pre
        if new_files:
            if not any(f.endswith('.crdownload') for f in new_files):
                break
        if time.time() - start_time > timeout:
            raise TimeoutError("Download did not complete in time.")
        time.sleep(1)

    filename = new_files.pop()
    path = os.path.join(download_path, filename)
    data = pd.read_excel(path)

    return data, path, filename

# We will scrape the website then upload to s3.

# There are four pages to scrape:
# - Student Attendance
# - Digital Workout Plan
# - Sessions Left (which happens to contain also Student Roster)
# - Finally, individual Learning Plans (this will take the longest to download all )

# ------------------------------------------------------------------------------------------------

# 1. Scrape sessions_left/student roster first

url = "https://radius.mathnasium.com/Attendance/Roster"
browser = get_browser(url)

wait = WebDriverWait(browser, 10)

# Grab credentials and login
login(browser, wait)

centerDropdown = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@class='theGCSMulti']//input[@class='k-input k-readonly']")))

time.sleep(2)

centerDropdown.send_keys('v') # 'v' for Verona

time.sleep(5)
centerDropdown.send_keys(Keys.ENTER)

time.sleep(3)
table = wait.until(EC.presence_of_all_elements_located((By.ID, "gridRoster")))
roster = table[0].get_attribute('outerHTML')

roster_df = pd.read_html(StringIO(roster))[0]

sessions_left = roster_df[['First Name', 'Last Name','Membership Type', 'Remaining']]

download_path = "/Users/victorruan/Downloads"

path = os.path.join(download_path, "sessions_left.csv")

sessions_left.to_csv(path, index=False)

sessions_left['Full Name'] = sessions_left['First Name'].astype(str) + " " + sessions_left['Last Name'].astype(str)
# print(sessions_left)
# print(sessions_left.columns)
up(s3, path, "sessions_left.csv")

print("Student roster scraped.")

# ------------------------------------------------------------------------------------------------

# 2. Scrape attendance

url= "https://radius.mathnasium.com/StudentAttendanceMonthlyReport"
browser.get(url)

switch = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@class='switch-field col-md-4']")))
switch.click()

reportStart = wait.until(EC.element_to_be_clickable((By.ID, "ReportMonthlyStart")))
reportStart.clear()
time.sleep(1)

date_string = "09/01/2024"

for char in date_string:
    reportStart.send_keys(char)
    time.sleep(0.1)

time.sleep(0.5)

search_btn = browser.find_element(By.XPATH, "//button[@onclick='GetMonthlyData()']")

time.sleep(0.5)

search_btn.click()

time.sleep(1)

download_path = "/Users/victorruan/Downloads"

_, file_beta, _ = export_excel(wait)

up(s3, file_beta, "Attendance_(All).xlsx")

print("Attendance scraped.")

# ------------------------------------------------------------------------------------------------

# 3. Scrape DWP

url = "https://radius.mathnasium.com/DigitalWorkoutPlan/Report"
browser.get(url)

time.sleep(0.5)

dwpFromDate = wait.until(EC.element_to_be_clickable((By.ID, "dwpFromDate")))
dwpFromDate.clear()

time.sleep(1)

# Date when we transitioned to digital workout plan
date_string = "09/01/2024"

for char in date_string:
    dwpFromDate.send_keys(char)
    time.sleep(0.1)

dwp_search_btn = wait.until(EC.element_to_be_clickable((By.ID, "btnsearch")))
dwp_search_btn.click()

_, file_zeta, _ = export_excel(wait)

up(s3, file_zeta, "DWP_Report_(All).xlsx")

print("Digital workout plans scraped.")

# ------------------------------------------------------------------------------------------------

# 4. Scrape Learning Plans

inactive_students = []

all_student_LP = {}

url = 'https://radius.mathnasium.com/LearningPlan'
browser.get(url)

studentDropdown = wait.until(EC.presence_of_all_elements_located((By.ID, "studentDropDownList")))

showInactiveCheckBox = wait.until(EC.presence_of_all_elements_located((By.ID, "showinactive")))
browser.execute_script("arguments[0].click();", showInactiveCheckBox[0])

# Find the index of 'Owen Schaefer'
# start_index = None
# for i, full_name in enumerate(sessions_left["Full Name"]):
#     if full_name == 'Owen Schaefer':
#         start_index = i
#         break

# if start_index is None:
#     print("Could not find 'Owen Schaefer' in the list")
#     exit()

# Start from Owen Schaefer
#for i in range(start_index, len(sessions_left)):
for i in range(len(sessions_left)):
    
    full_name = sessions_left["Full Name"][i]
    print(f'Processing: {full_name}')

    browser.execute_script("arguments[0].click();", studentDropdown[0])

    string_match = "//*[contains(text(), " + "'" + full_name + "'" + ")]"

    try:
        # wait up to 10 seconds for the element to be clickable
        student_dropdown_item = wait.until(EC.element_to_be_clickable((By.XPATH, string_match)))
        browser.execute_script("arguments[0].click();", student_dropdown_item)

    except TimeoutException:
        print("Element not clickable—doing something else instead.")
        inactive_students.append(full_name)
        continue
    
    # Just need to wrap up S3 upload for Learning
    # Plans then auto scraping should be wrapped up!
    lp, file_eta, filename = export_excel(wait)

    if len(filename.split(" "))<2:
        print('Anomalous file')
        print(filename)
        continue

    with open(file_eta, "rb") as f:
        name = filename.split(" ")[0] + " " + filename.split(" ")[1] + ".xlsx"
        print(name)
        s3.upload_fileobj(f, bucket, "learning_plans/"+name)

print("Learning plans scraped.")

deploy()
