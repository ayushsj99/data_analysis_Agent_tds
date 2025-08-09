import pandas as pd
import json
import os

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(script_dir, "q1.csv")

# Load CSV file
df = pd.read_csv(file_path, parse_dates=["created_date"])

# 1. NYC agency assigned to the most complaints
most_complaints_agency = df["agency"].value_counts().idxmax()

# 2. Top 3 most common complaint types in the BRONX
top3_bronx_complaints = (
    df[df["borough"] == "BRONX"]["complaint_type"]
    .value_counts()
    .head(3)
    .index
    .tolist()
)

# 3. Date with the most 311 complaints
df["date_only"] = df["created_date"].dt.date
most_complaints_date = df["date_only"].value_counts().idxmax().isoformat()

# 4. Total number of "Traffic Signal Condition" complaints in STATEN ISLAND
traffic_signal_count_staten = df[
    (df["complaint_type"] == "Traffic Signal Condition") &
    (df["borough"] == "STATEN ISLAND")
].shape[0]

# 5. Unique complaint types reported by Department of Transportation (DOT)
unique_dot_complaints = df[df["agency"] == "DOT"]["complaint_type"].nunique()

# Prepare result
result = {
    "most_complaints_agency": most_complaints_agency,
    "top3_bronx_complaints": top3_bronx_complaints,
    "most_complaints_date": most_complaints_date,
    "traffic_signal_condition_staten_island": traffic_signal_count_staten,
    "unique_dot_complaint_types": unique_dot_complaints
}

# Print as JSON
print(json.dumps(result, indent=2))
