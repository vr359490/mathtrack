import boto3
import os
from io import BytesIO
import pandas as pd
import calendar
import datetime
from datetime import timedelta
import warnings
from collections import OrderedDict

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

def attend_scrape(sessions_left):

    filename = "Attendance_(All).xlsx"

    attendance = down(s3, filename)

    # path = "/Users/victorruan/Desktop/mathnasium_dash_files/" + filename

    # attendance = pd.read_excel(path)

    attendance['Full Name'] = attendance['First Name'].astype(str) + ' ' + attendance['Last Name'].astype(str)

    sessions_left, all_attendance_df, sessions_per_m, center_attend_avg = attend_process(attendance, sessions_left)

    return sessions_left, all_attendance_df, sessions_per_m, center_attend_avg

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
        
        attend_keys = []
        attend_vals = []

        # Inactive students are sometimes listed in roster, but not attendance?
        if student in list(attendance['Full Name']):

            attend_dict[student] = OrderedDict()

            # Get attendance rows for student. There will more than one if they've had multiple attendance packages in the given time range.
            attend_packages = attendance.loc[attendance['Full Name']==student]
            attend_packages = attend_packages.to_dict(into=OrderedDict,orient='records')

            # We are assuming current month doesn't appear twice.
            # We should test if it's possible by grabbing a date range longer than a year.
            
            for column_name in attend_packages[0].keys():
                if column_name in month_list:
                    attend_keys.append(column_name)

            for package in attend_packages:    
                pack_attend_vals = []
                for col, value in package.items():
                    if col in month_list:
                        attend_count = string_check(value)
# ----------------------------------------------------------------
                        # If there is only one attendance pack, we store directly store into list
                        if len(attend_packages)==1:                          
                            attend_vals.append(attend_count)

                        # If multiple packs, we store as nested list and consolidate into one list later.
                        else:
                            pack_attend_vals.append(attend_count)
        
                if len(attend_packages)>1:
                    attend_vals.append(pack_attend_vals)

            if type(attend_vals[0]) is list:
                # Consolidate all attend lists if there were multiple attend_packs
                final_attend_vals = attend_vals[0]

                for remaining_attend in attend_vals[1:]:
                    for i,j in enumerate(remaining_attend):

                        final_attend_vals[i]+=j

                attend_vals = final_attend_vals

            # Do not include initial months that have zero attend.
            # We will assume they were not active at that time, although we should check exact date in the future.                
            attend_vals, attend_keys = truncate_zero_attend(attend_vals, attend_keys, student)
# ----------------------------------------------------------------

            attend_dict[student] = dict(zip(attend_keys, attend_vals))

            # Exclude students with zero attendance in time range.
            attend_check = attend_dict.get(student)
            if not attend_check:
                attendance_col.append(0)
                avg_attendance_col.append(0)
                continue

            current_month_attendance = attend_dict[student].get(load_month, 0)
            attendance_col.append(current_month_attendance)

            # Calculate time range up to current day
            current_day = datetime.datetime.today().day
            current_month = datetime.datetime.now().month
            current_year = datetime.datetime.now().year

            days_in_current_month = calendar.monthrange(current_year, current_month)[1]
            percent_current_month = current_day/days_in_current_month

            time_range = len(list(attend_dict[student].values())) - 1 + percent_current_month

            total_sessions = sum(list(attend_dict[student].values()))
            revised_avg_attend = total_sessions/time_range

            avg_attendance_col.append(revised_avg_attend)

    all_attendance_df = pd.DataFrame(attend_dict)

    # Calculate average excluding students with 0 attendance, they're considered inactive.
    center_attend_avg = sum(avg_attendance_col)/(len(avg_attendance_col) - avg_attendance_col.count(0))

    sessions_per_m = {}
    index = []

    for i,colName in enumerate(all_attendance_df.T.columns):
        
        sessions_per_m[colName] = all_attendance_df.T[colName].sum()
        index.append(i)

    sessions_per_m = pd.DataFrame(sessions_per_m, index=[0])
    sessions_per_m = sessions_per_m.T

    sessions_left['This Month Attendance'] = attendance_col 

    avg_attendance_col = [round(average, 2) for average in avg_attendance_col]
    sessions_left['Avg Attend/m'] = avg_attendance_col

    return sessions_left, all_attendance_df, sessions_per_m, center_attend_avg

def string_check(string):
    if string[0:2].isnumeric():
        value = string[0:2]
    elif string[0:1].isnumeric():
        value = string[0]
    else:
        value = 0
    return int(value)

def truncate_zero_attend(attend_list, month_list, student):

    #Truncate beginning zeros
    while attend_list[0]==0:
        
        attend_list = attend_list[1:]
        month_list = month_list[1:]

        if not attend_list: 
            break

    return attend_list, month_list