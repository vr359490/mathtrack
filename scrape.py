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
import tempfile

def deploy():
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
    
    # Essential options for GitHub Actions
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Use a temporary directory for downloads
    download_dir = os.path.join(os.getcwd(), "downloads")
    os.makedirs(download_dir, exist_ok=True)
    
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
    browser = webdriver.Chrome(options=options)
    browser.get(url)
    return browser, download_dir

def login(browser, wait):
    USERNAME = os.getenv("MATHNASIUM_USERNAME")
    PASSWORD = os.getenv("MATHNASIUM_PASSWORD")

    username_field = browser.find_element(By.ID, "UserName")
    username_field.send_keys(USERNAME)

    password_field = browser.find_element(By.ID, "Password")
    password_field.send_keys(PASSWORD)

    login_field = wait.until(EC.presence_of_all_elements_located((By.ID, "login")))
    browser.execute_script("arguments[0].click();", login_field[0])

def export_excel(wait, download_path):
    pre = set(os.listdir(download_path))

    export_buttons = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//button[contains(text(), 'Excel')]")))
    export = export_buttons[1] if len(export_buttons) > 1 else export_buttons[0]
    browser.execute_script("arguments[0].click();", export)

    # Wait for new file to appear
    timeout = 180  # Reduced timeout for CI
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

# 1. Scrape sessions_left/student roster first
print("Starting scraper...")

url = "https://radius.mathnasium.com/Attendance/Roster"
browser, download_path = get_browser(url)

try:
    wait = WebDriverWait(browser, 60)  # Increased wait time

    login(browser, wait)
    print("Logged in successfully")

    centerDropdown = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@class='theGCSMulti']//input[@class='k-input k-readonly']")))

    time.sleep(2)
    centerDropdown.send_keys('v')
    time.sleep(5)
    centerDropdown.send_keys(Keys.ENTER)

    time.sleep(3)
    table = wait.until(EC.presence_of_all_elements_located((By.ID, "gridRoster")))
    roster = table[0].get_attribute('outerHTML')

    roster_df = pd.read_html(StringIO(roster))[0]
    sessions_left = roster_df[['First Name', 'Last Name','Membership Type', 'Remaining']]

    path = os.path.join(download_path, "sessions_left.csv")
    sessions_left.to_csv(path, index=False)

    sessions_left['Full Name'] = sessions_left['First Name'].astype(str) + " " + sessions_left['Last Name'].astype(str)
    up(s3, path, "sessions_left.csv")

    print("Student roster scraped.")

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
    time.sleep(3)

    _, file_beta, _ = export_excel(wait, download_path)
    up(s3, file_beta, "Attendance_(All).xlsx")
    print("Attendance scraped.")

    # 3. Scrape DWP
    url = "https://radius.mathnasium.com/DigitalWorkoutPlan/Report"
    browser.get(url)

    time.sleep(0.5)
    dwpFromDate = wait.until(EC.element_to_be_clickable((By.ID, "dwpFromDate")))
    dwpFromDate.clear()
    time.sleep(1)

    date_string = "09/01/2024"
    for char in date_string:
        dwpFromDate.send_keys(char)
        time.sleep(0.1)

    dwp_search_btn = wait.until(EC.element_to_be_clickable((By.ID, "btnsearch")))
    dwp_search_btn.click()

    _, file_zeta, _ = export_excel(wait, download_path)
    up(s3, file_zeta, "DWP_Report_(All).xlsx")
    print("Digital workout plans scraped.")

    # 4. Scrape Learning Plans
    inactive_students = []
    all_student_LP = {}

    url = 'https://radius.mathnasium.com/LearningPlan'
    browser.get(url)

    studentDropdown = wait.until(EC.presence_of_all_elements_located((By.ID, "studentDropDownList")))
    showInactiveCheckBox = wait.until(EC.presence_of_all_elements_located((By.ID, "showinactive")))
    browser.execute_script("arguments[0].click();", showInactiveCheckBox[0])

    # Process first 5 students for testing in CI
    for i in range(min(5, len(sessions_left))):
        full_name = sessions_left["Full Name"][i]
        print(f'Processing: {full_name}')

        browser.execute_script("arguments[0].click();", studentDropdown[0])
        string_match = "//*[contains(text(), " + "'" + full_name + "'" + ")]"

        try:
            student_dropdown_item = wait.until(EC.element_to_be_clickable((By.XPATH, string_match)))
            browser.execute_script("arguments[0].click();", student_dropdown_item)
        except TimeoutException:
            print(f"Element not clickable for {full_name}")
            inactive_students.append(full_name)
            continue
        
        lp, file_eta, filename = export_excel(wait, download_path)

        if len(filename.split(" "))<2:
            print(f'Anomalous file: {filename}')
            continue

        with open(file_eta, "rb") as f:
            name = filename.split(" ")[0] + " " + filename.split(" ")[1] + ".xlsx"
            print(f'Uploading: {name}')
            s3.upload_fileobj(f, bucket, "learning_plans/"+name)

    print("Learning plans scraped.")
    print(f"Inactive students: {inactive_students}")

    # deploy()

finally:
    browser.quit()
    print("Browser closed")
