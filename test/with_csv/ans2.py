import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import json
from pathlib import Path

def analyze_co2_data(file_path):
    """
    Loads the CO2 emissions dataset and answers a series of analytical questions.

    Args:
        file_path (str or Path): The path to the q2.csv file.

    Returns:
        dict: A dictionary containing the answers to the questions.
    """
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return None

    # --- Data Cleaning and Preparation ---
    # Ensure 'year' is an integer for proper filtering and analysis
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    df.dropna(subset=['year'], inplace=True)
    df['year'] = df['year'].astype(int)

    # --- 1. Which 5 countries have the highest total CO2 emissions in the most recent year? ---
    most_recent_year = df['year'].max()
    df_recent = df[df['year'] == most_recent_year]
    top_5_countries_co2 = df_recent.sort_values(by='co2', ascending=False).head(5)['country'].tolist()

    # --- 2. Year-over-year percentage growth of coal-based CO2 for China (2010-2020) ---
    df_china_coal = df[
        (df['country'] == 'China') & 
        (df['year'].between(2010, 2020))
    ][['year', 'coal_co2']].set_index('year')
    df_china_coal['yoy_growth_%'] = df_china_coal['coal_co2'].pct_change() * 100
    china_yoy_growth = df_china_coal['yoy_growth_%'].dropna().to_dict()

    # --- 3. Line chart of total CO2 for USA, India, UK (1990-present) ---
    countries_for_trend = ['United States', 'India', 'United Kingdom']
    df_trend = df[
        (df['country'].isin(countries_for_trend)) & 
        (df['year'] >= 1990)
    ]
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df_trend, x='year', y='co2', hue='country')
    plt.title('Total CO2 Emissions (1990-Present)')
    plt.xlabel('Year')
    plt.ylabel('CO2 Emissions (Million Tonnes)')
    plt.grid(True)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    trend_chart_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    trend_chart_uri = f"data:image/png;base64,{trend_chart_base64}"

    # --- 4. Average co2_per_capita for Africa vs. Europe (2019) ---
    df_2019 = df[df['year'] == 2019]
    avg_co2_africa_2019 = df_2019[df_2019['country'] == 'Africa']['co2_per_capita'].mean()
    avg_co2_europe_2019 = df_2019[df_2019['country'] == 'Europe']['co2_per_capita'].mean()

    # --- 5. Country with the highest energy_per_capita in 2021 ---
    df_2021 = df[df['year'] == 2021].dropna(subset=['energy_per_capita'])
    highest_energy_country_2021 = df_2021.loc[df_2021['energy_per_capita'].idxmax()]['country']

    # --- 6. Correlation between GDP and total CO2 in 2018 ---
    df_2018 = df[df['year'] == 2018].dropna(subset=['gdp', 'co2'])
    gdp_co2_correlation_2018 = df_2018['gdp'].corr(df_2018['co2'])

    # --- 7. Bar chart of top 10 countries by cumulative CO2 ---
    # Note: 'cumulative_co2' is already in the data for the most recent year
    df_cumulative = df_recent.dropna(subset=['cumulative_co2']).sort_values(by='cumulative_co2', ascending=False).head(10)
    plt.figure(figsize=(12, 7))
    sns.barplot(data=df_cumulative, x='cumulative_co2', y='country', palette='viridis')
    plt.title('Top 10 Countries by Cumulative CO2 Emissions')
    plt.xlabel('Cumulative CO2 Emissions (Million Tonnes)')
    plt.ylabel('Country')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    cumulative_chart_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    cumulative_chart_uri = f"data:image/png;base64,{cumulative_chart_base64}"

    # --- 8. Percentage contribution of fuels for Germany in 2020 ---
    df_germany_2020 = df[(df['country'] == 'Germany') & (df['year'] == 2020)]
    if not df_germany_2020.empty:
        oil_co2 = df_germany_2020['oil_co2'].iloc[0]
        coal_co2 = df_germany_2020['coal_co2'].iloc[0]
        gas_co2 = df_germany_2020['gas_co2'].iloc[0]
        total_fossil_co2 = oil_co2 + coal_co2 + gas_co2
        contribution_germany_2020 = {
            'oil_%': (oil_co2 / total_fossil_co2) * 100,
            'coal_%': (coal_co2 / total_fossil_co2) * 100,
            'gas_%': (gas_co2 / total_fossil_co2) * 100
        }
    else:
        contribution_germany_2020 = "Data not available for Germany in 2020."

    # --- 9. Countries with negative co2_growth_prct in 2020 ---
    countries_negative_growth_2020 = df[
        (df['year'] == 2020) & 
        (df['co2_growth_prct'] < 0)
    ]['country'].tolist()

    # --- 10. Scatter plot of GDP vs. CO2 by continent ---
    # Note: The dataset uses country names like 'Africa', 'Europe' for continents.
    continents = ['Africa', 'Asia', 'Europe', 'North America', 'South America', 'Oceania']
    df_scatter = df_recent[df_recent['country'].isin(continents)].dropna(subset=['gdp', 'co2'])
    plt.figure(figsize=(12, 8))
    sns.scatterplot(data=df_scatter, x='gdp', y='co2', hue='country', s=200, alpha=0.8)
    plt.title(f'GDP vs. CO2 Emissions by Continent ({most_recent_year})')
    plt.xlabel('GDP (Gross Domestic Product)')
    plt.ylabel('CO2 Emissions (Million Tonnes)')
    plt.xscale('log')
    plt.yscale('log')
    plt.grid(True)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    scatter_chart_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    scatter_chart_uri = f"data:image/png;base64,{scatter_chart_base64}"

    # --- Compile final answers ---
    final_answers = {
        "1. Top 5 countries by CO2 emissions in the most recent year": top_5_countries_co2,
        "2. Year-over-year coal CO2 growth for China (2010-2020)": china_yoy_growth,
        "3. Trend of total CO2 emissions for USA, India, UK": trend_chart_uri,
        "4. Average CO2 per capita in 2019 (Africa vs. Europe)": {
            "Africa": avg_co2_africa_2019,
            "Europe": avg_co2_europe_2019
        },
        "5. Country with highest energy per capita in 2021": highest_energy_country_2021,
        "6. Correlation between GDP and total CO2 in 2018": gdp_co2_correlation_2018,
        "7. Top 10 countries by cumulative CO2 emissions": cumulative_chart_uri,
        "8. Fossil fuel contribution for Germany in 2020": contribution_germany_2020,
        "9. Countries with negative CO2 growth in 2020": countries_negative_growth_2020,
        "10. Scatter plot of GDP vs. CO2 by continent": scatter_chart_uri
    }

    return final_answers


if __name__ == '__main__':
    # Construct a reliable path to the CSV file
    script_dir = Path(__file__).parent
    csv_file_path = script_dir / 'q2.csv'
    
    # Run the analysis
    answers = analyze_co2_data(csv_file_path)
    
    # Print the final JSON object
    if answers:
        print(json.dumps(answers, indent=2))
