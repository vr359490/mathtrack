# MathTrack: Education Analytics Dashboard for Mathnasium

MathTrack is an analytics dashboard designed to enable managers at Mathnasium learning centers to easily visualize and track key metrics related to student progress, retention, and performance. The dashboard consolidates a variety of data sources, automates data scraping, and provides actionable insights to support student outcomes and operational efficiency.

---

## Features

- **Comprehensive Student Metrics**: Visualize student attendance, learning plan progress, session usage, and more.
- **Automated Data Scraping**: Uses Selenium to log in and extract up-to-date information from Mathnasium Radius, including:
  - Student Attendance
  - Digital Workout Plan (DWP)
  - Sessions Left and Student Roster
  - Individual Learning Plans
- **Cloud Integration**: All raw and processed data is stored and retrieved from AWS S3 for persistence and sharing.
- **Business Intelligence Summaries**: Generates concise, actionable summaries for each student using AI, highlighting academic strengths, weaknesses, and attendance trends.
- **Modern Dashboard Interface**: Built using Dash and Plotly to provide interactive charts and tables.

---

## Directory Structure

```
mathtrack/
├── agent.py         # Generates student summaries using AI and manages uploads to S3
├── mathDash_s3.py   # Main dashboard application (Dash/Plotly code)
├── process.py       # Data processing, cleaning, and feature engineering
├── scrape.py        # Automated scraping of Mathnasium Radius and uploads to S3
├── requirements.txt # Python dependencies
└── README.md        # Project documentation
```

---

## How It Works

### 1. Data Collection & Scraping

- `scrape.py` uses Selenium WebDriver to:
  - Log into Mathnasium Radius
  - Extract tables and reports (Attendance, DWP, Learning Plans, Roster)
  - Export data as Excel files
  - Upload all files to AWS S3 (`mathdashbucket`) for persistence

### 2. Data Processing

- `process.py` retrieves raw data from S3, processes learning plans, attendance, and sessions data, and prepares clean datasets for visualization and analysis.

### 3. AI-Driven Summaries

- `agent.py` loads processed data and generates individualized student summaries using OpenAI's GPT models. Summaries include:
  - Academic performance insights
  - Attendance analysis
  - Learning plan progress
  - Session utilization

### 4. Dashboard Visualization

- `mathDash_s3.py` is the main entry point for the Dash app:
  - Connects to S3 to load data
  - Displays data tables, interactive charts, and BI-generated summaries for student and center-level insights

---

## Setup & Installation

1. **Clone this repository:**
   ```bash
   git clone https://github.com/vr359490/mathtrack.git
   cd mathtrack
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure AWS Credentials:**
   - Set `AWS_ACCESS_KEY` and `AWS_SECRET_KEY` as environment variables.

4. **(Optional) Set up ChromeDriver for Selenium:**
   - Download the appropriate ChromeDriver for your system and ensure it's in your PATH.

---

## Usage

1. **Run the Scraper:**
   - Scrape latest data and upload to S3:
     ```bash
     python scrape.py
     ```

2. **Process Data:**
   - Prepare and clean the raw data:
     ```bash
     python process.py
     ```

3. **Generate Student Summaries:**
   - Use AI to create student performance summaries:
     ```bash
     python agent.py
     ```

4. **Launch the Dashboard:**
   - Start the Dash application:
     ```bash
     python mathDash_s3.py
     ```
   - Open the provided local URL in your browser.

---

## Customization & Extensibility

- **Add New Metrics:** Enhance `process.py` or `mathDash_s3.py` to compute or visualize additional metrics.
- **Modify Scraping Targets:** Update `scrape.py` to add or change scraped pages/reports.
- **Change S3 Bucket:** Set the desired bucket name in the relevant scripts (default: `mathdashbucket`).


---

## License

This project is for internal analytics purposes at Mathnasium centers. For other use cases, please contact the author.

---

## Authors

- **Victor Ruan** ([vr359490](https://github.com/vr359490))

---
