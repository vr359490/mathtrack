# Education Analytics Dashboard for Mathnasium 

This is a dashboard project to enable managers at Mathnasium to see key metrics in one location. This will aid in tracking student progress and retention.

mathDash_s3.py contains main dashboard code. This involves downloading scraped and cleaned data from AWS S3 cloud storage.

Before the data was stored and pulled from S3, the scraping stage was done every time the dashboard was executed. This is in mathDash_with_scraping.py

To maintain updated data in the dashboard and S3, a separate scraping script should be made.
