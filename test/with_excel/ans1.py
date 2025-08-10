import pandas as pd
import json
from pathlib import Path

def analyze_flight_data(file_name='q1.xlsx'):
    """
    Analyzes airline flight data from an Excel file to answer specific questions.

    Args:
        file_name (str): The name of the Excel file.

    Returns:
        dict: A dictionary containing the answers to the questions.
    """
    try:
        # Get the directory where the script is located
        script_dir = Path(__file__).parent
        # Build the full path to the data file
        file_path = script_dir / file_name

        if not file_path.is_file():
            return {"error": f"The file '{file_path}' was not found. Please ensure it's in the same directory as the script."}

        # Load the dataset from the specified Excel file
        df = pd.read_excel(file_path)

    except Exception as e:
        return {"error": f"An error occurred: {e}"}

    answers = {}

    # --- Question 1: Which airline has the highest average flight price for business class tickets? ---
    business_flights = df[df['class'] == 'Business']
    if not business_flights.empty:
        avg_price_by_airline = business_flights.groupby('airline')['price'].mean()
        answers['q1_highest_avg_price_airline'] = avg_price_by_airline.idxmax()
    else:
        answers['q1_highest_avg_price_airline'] = "No business class flights found."


    # --- Question 2: What are the top 5 most frequent flight routes? ---
    df['route'] = df['source_city'] + ' to ' + df['destination_city']
    top_5_routes = df['route'].value_counts().head(5).index.tolist()
    answers['q2_top_5_routes'] = top_5_routes

    # --- Question 3: On which departure time of day are the flights with the longest duration most frequent? ---
    longest_duration = df['duration'].max()
    longest_flights = df[df['duration'] == longest_duration]
    answers['q3_departure_time_for_longest_flights'] = longest_flights['departure_time'].mode()[0]

    # --- Question 4: What is the total number of "Vistara" flights from "Delhi" to "Mumbai" with zero stops? ---
    vistara_del_mum_zero_stops = df[
        (df['airline'] == 'Vistara') &
        (df['source_city'] == 'Delhi') &
        (df['destination_city'] == 'Mumbai') &
        (df['stops'] == 'zero')
    ]
    answers['q4_vistara_del_mum_zero_stops_count'] = len(vistara_del_mum_zero_stops)

    # --- Question 5: How many unique airlines offer flights with a duration of less than 2 hours? ---
    short_haul_flights = df[df['duration'] < 2]
    answers['q5_unique_airlines_short_haul'] = short_haul_flights['airline'].nunique()

    # --- Question 6: What is the average price of flights with more than 30 days left for departure, for each class? ---
    flights_long_departure = df[df['days_left'] > 30]
    avg_price_by_class = flights_long_departure.groupby('class')['price'].mean().to_dict()
    # Rounding for cleaner output
    answers['q6_avg_price_by_class_long_departure'] = {k: round(v, 2) for k, v in avg_price_by_class.items()}


    # --- Question 7: What is the source city with the highest average flight price for flights that have 'two_or_more' stops? ---
    multi_stop_flights = df[df['stops'] == 'two_or_more']
    if not multi_stop_flights.empty:
        avg_price_by_source = multi_stop_flights.groupby('source_city')['price'].mean()
        answers['q7_source_city_highest_avg_price_multi_stop'] = avg_price_by_source.idxmax()
    else:
        answers['q7_source_city_highest_avg_price_multi_stop'] = "No flights with two or more stops found."


    return answers

if __name__ == '__main__':
    # Get the answers by running the analysis function
    final_answers = analyze_flight_data()

    # Print the answers in a formatted JSON object
    print(json.dumps(final_answers, indent=4))
    
    
#     {
#     "q1_highest_avg_price_airline": "Vistara",
#     "q2_top_5_routes": [
#         "Delhi to Mumbai",
#         "Mumbai to Delhi",
#         "Delhi to Bangalore",
#         "Bangalore to Delhi",
#         "Bangalore to Mumbai"
#     ],
#     "q3_departure_time_for_longest_flights": "Evening",
#     "q4_vistara_del_mum_zero_stops_count": 1401,
#     "q5_unique_airlines_short_haul": 6,
#     "q6_avg_price_by_class_long_departure": {
#         "Business": 51648.56,
#         "Economy": 4919.2
#     },
#     "q7_source_city_highest_avg_price_multi_stop": "Delhi"
# }