
from openai import OpenAI
import pprint
#import pandas as pd
import json
from collections import OrderedDict

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
                                            PK stands for prescriptive.
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

def assistant_call():
    client = OpenAI()

    path = "/Users/victorruan/Desktop/Remaining sessions.docx"

    paths = [path]
    streams = [open(path, "rb") for path in paths]

    # Upload a file (e.g., PDF, DOCX, or TXT)
    file = client.files.create(
        file=open(path, "rb"),
        purpose="assistants"
    )
    vector_store = client.vector_stores.create(name="sessions-left")

    # Add the uploaded file to the vector store
    client.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id,
        files = streams
        #files=[file.id]
    )
    assistant = client.beta.assistants.create(
        name="Business Analyst",
        instructions="You are an experienced business intelligence analyst for a large mathematics tutoring center.",
        model="gpt-4-turbo",
        tools=[{"type": "file_search"}],
    )

    assistant = client.beta.assistants.update(
    assistant_id=assistant.id,
    tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )

    thread = client.beta.threads.create()

    # Ask a question that requires looking into the file
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="What are some business insights that you have extracted from the given files?"
    )
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id
    )

    # Poll for completion
    while run.status != "completed":
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

    # Get the response
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    for message in messages.data:
        print(f"{message.role}: {message.content[0].text.value}")
