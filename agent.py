from openai import OpenAI
import pprint
#import pandas as pd
import json
from collections import OrderedDict
import boto3
from datetime import datetime
import os

with open("pk_completion.json", "r") as f:
    pk_completion = json.load(f)

with open("student_summaries.json", "r") as f:
    student_summaries = json.load(f)

with open("attendance.json", "r") as f:
    attendance = json.load(f)

with open("center_averages.json", "r") as f:
    center_summary = json.load(f)

#pprint.pprint(pk_completion)

def nonfile_call(student, student_summary, student_pks, student_attend):
    client = OpenAI()

    completion = client.chat.completions.create(
    #model="gpt-4.1",
        model="o4-mini",
        #reasoning_effort="high",
        #Examples of preferred results may include things like student strengths and weaknesses, attendance trends over time, and overall student performance. 
        messages=[
            #{"role": "system", "content": "You are an experienced business intelligence analyst for a large mathematics tutoring center."},
            {"role": "user", "content": f"""You are an experienced educator with a background in business intelligence and you work for a large mathematics tutoring center. 
                                            I've gathered data for one of our students, {student}. You are to analyze and gather key insights 
                                            from the data I give you. Create a concise summary of about 100 words of the most significant findings regarding academic performance and attendance. 
                                            These results are to be presented to the owner. 
                                            Here's some data:
                                            General metrics: {student_summary}. Recall that Mastery Rate is the number of sessions on average the student takes to 
                                            master a PK and Learning Rate is the reciprocal of Mastery Rate - it represents the average number of PKs 
                                            completed per session. The Remaining column only applies to those with a session Membership type. It refers to 
                                            the number of sessions left in the student's attendance package.
                                            Average metrics for {center_summary.get('Center','')} center: {center_summary}
                                            PK completion data: {student_pks}. Recall that the Completed flag stands for 'Completed but not Mastered' and, as such, represents the number 
                                            of times the topic has been or will be repeated. A Mastered value of 1 means the student has mastered the topic, and a value of 0 means the student 
                                            is currently working on it and doesn't necessarily indicate weakness in that area. Do not mention Mastery percentage as this is not a helpful metric.
                                            Refer to PKs as PKs only - do not refer to them as 'topics' or 'concepts' or anything else.
                                            Attendance data: {student_attend}."""}
        ]
    )

    response = completion.choices[0].message.content

    print(response)

    return response

#student = 'A.J. Kuehn'
summaries = {}

student_attend = OrderedDict()
student_summary = {}

roster = {}

for summary in student_summaries:
    student2 = summary['Full Name']

    roster[student2] = {}
    #roster.append(student2)
    summaries[student2] = summary

# print(roster)
# print(len(roster))
# count = 0

for student in roster.keys():
# for student in ['A.J. Kuehn']:
    # # count+=1
    # if student not in new_students:
    #     continue
    
    student_pks = pk_completion[student]

    student_summary = summaries[student]
    del student_summary['This Month Attendance']
    # Delete this until we have accurate start and expiry data on membership
    # (Memberships with discrete # of sessions are good to go already.)
    del student_summary['Membership Type']

    # print(student)
    if student_summary['Remaining'] is int:
        print(student_summary['Remaining'])
        print('ok')
    else:
        # print(student_summary['Remaining'])
        # print('not okay')
        del student_summary['Remaining']

    for month in list(attendance.keys())[:-1]:
        student_attend[month] = attendance[month][student]

    excluded_pks = []

    for pk in student_pks.keys():

        pk_type = pk[0:3]

        if "WCH" in pk_type or "FO" in pk_type or "WOB" in pk_type:
            excluded_pks.append(pk)

    for delete_pk in excluded_pks:
        del student_pks[delete_pk]

    response = nonfile_call(student, student_summary, student_pks, student_attend)
    roster[student] = response

    # if count==3:
    #     break

pprint.pprint(roster)

with open("generated_summaries.json", "w") as f:
    json.dump(roster, f)

# Upload to S3

def upload_to_s3():

    AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
    AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
    
    # Initialize S3 client
    s3_client = boto3.client("s3",
                      aws_access_key_id=AWS_ACCESS_KEY,
                      aws_secret_access_key=AWS_SECRET_KEY,
                      region_name="us-east-2")
    
    # Get current date for file naming
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # S3 bucket and file path
    bucket_name = 'mathdashbucket'  # Replace with your actual bucket name
    s3_file_path = f'student-summaries/{current_date}/generated_summaries.json'
    
    try:
        # Upload the file
        s3_client.upload_file(
            'generated_summaries.json',
            bucket_name,
            s3_file_path
        )
        print(f"Successfully uploaded to s3://{bucket_name}/{s3_file_path}")
    except Exception as e:
        print(f"Error uploading to S3: {str(e)}")

# Call the upload function
upload_to_s3()


