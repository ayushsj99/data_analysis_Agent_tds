import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime
from sklearn.linear_model import LinearRegression
import numpy as np

# S3 Parquet path
PARQUET_PATH = "s3://indian-high-court-judgments/metadata/parquet/year=*/court=*/bench=*/metadata.parquet?s3_region=ap-south-1"

# Initialize DuckDB with HTTPFS & Parquet
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute("INSTALL parquet; LOAD parquet;")

# 1️⃣ Which high court disposed the most cases from 2019 - 2022
query_most_cases = f"""
SELECT court, COUNT(*) as case_count
FROM read_parquet('{PARQUET_PATH}')
WHERE year BETWEEN 2019 AND 2022
GROUP BY court
ORDER BY case_count DESC
LIMIT 1
"""
most_cases_df = con.execute(query_most_cases).df()
most_cases_court = most_cases_df.iloc[0]["court"]

# 2️⃣ Regression slope of date_of_registration - decision_date for court=33_10
query_court_delay = f"""
SELECT date_of_registration, decision_date, year
FROM read_parquet('{PARQUET_PATH}')
WHERE court = '33_10'
"""
court_df = con.execute(query_court_delay).df()

# Convert to datetime & calculate delay in days
court_df["date_of_registration"] = pd.to_datetime(court_df["date_of_registration"], errors="coerce", format="%d-%m-%Y")
court_df["decision_date"] = pd.to_datetime(court_df["decision_date"], errors="coerce")
court_df["delay_days"] = (court_df["decision_date"] - court_df["date_of_registration"]).dt.days

# Drop NaN or negative delays
court_df = court_df.dropna(subset=["delay_days", "year"])
court_df = court_df[court_df["delay_days"] >= 0]

# Regression: year vs delay_days
X = court_df[["year"]].values
y = court_df["delay_days"].values
model = LinearRegression().fit(X, y)
regression_slope = model.coef_[0]

# 3️⃣ Plot scatter + regression line
plt.figure(figsize=(6, 4))
plt.scatter(court_df["year"], court_df["delay_days"], alpha=0.3, s=10)
plt.plot(court_df["year"], model.predict(X), color="red", linewidth=2)
plt.xlabel("Year")
plt.ylabel("Delay (days)")
plt.title("Year vs Delay Days (Court=33_10)")

# Save plot to base64 (webp)
buf = io.BytesIO()
plt.savefig(buf, format="webp", bbox_inches="tight")
buf.seek(0)
img_base64 = base64.b64encode(buf.read()).decode("utf-8")
img_data_uri = f"data:image/webp;base64,{img_base64}"
buf.close()

# 4️⃣ Prepare JSON output
result = {
    "Which high court disposed the most cases from 2019 - 2022?": most_cases_court,
    "What's the regression slope of the date_of_registration - decision_date by year in the court=33_10?": regression_slope,
    "Plot the year and # of days of delay from the above question as a scatterplot with a regression line. Encode as a base64 data URI under 100,000 characters": img_data_uri
}

print(result)
