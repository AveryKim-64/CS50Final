import sqlite3
import pandas as pd
import os
import json

# Connect to the database
conn = sqlite3.connect("housing.db")

# Query to calculate number of sales, average price, and average square footage by neighborhood
query = """
    SELECT 
        z.neighborhood AS neighborhood,
        COUNT(s.id) AS num_sales,
        AVG(s.sale_price) AS avg_price,
        AVG(s.gross_sqft) AS avg_sqft,
        AVG(s.sale_price / s.total_units) AS avg_price_per_unit,
        AVG(s.gross_sqft / s.total_units) AS avg_sqft_per_unit
    FROM 
        sales AS s
    INNER JOIN 
        zip_neighborhood AS z
    ON 
        s.zip_code = z.zip_code
    WHERE 
        s.total_units > 0  AND s.commercial_units = 0 -- Avoid division by zero
    GROUP BY 
        z.neighborhood
    ORDER BY 
        num_sales DESC;
"""

# Execute the query and load the results into a pandas DataFrame
df = pd.read_sql_query(query, conn)

# Define the output path to save the CSV in the `static` folder
current_dir = os.path.dirname(__file__)
static_folder = os.path.join(current_dir, '../static')
os.makedirs(static_folder, exist_ok=True)  # Ensure the folder exists
output_file = os.path.join(static_folder, "neighborhood_info.csv")

# Save the DataFrame to the CSV file
df.to_csv(output_file, index=False)

# Close the connection
conn.close()

print(f"Neighborhood information saved to '{output_file}'.")


# NOW MERGE NEIGHBORHOOD INFO WITH THE ZONING INFORMATION TO ONE COHESIVE JSON
# Define paths to static files
current_dir = os.path.dirname(__file__)  # Directory of this script
static_folder = os.path.join(current_dir, "../static")  # Static folder

# File paths
csv_file_path = os.path.join(static_folder, "neighborhood_info.csv")
json_file_path = os.path.join(static_folder, "nyc_neighborhoods.json")
output_file_path = os.path.join(static_folder, "merged_neighborhoods.json")

# Load the CSV data into a Pandas DataFrame
neighborhood_info = pd.read_csv(csv_file_path)

# Load the GeoJSON data
with open(json_file_path, "r") as f:
    geojson_data = json.load(f)

# Create a lookup dictionary from the CSV for easy access
info_lookup = neighborhood_info.set_index("neighborhood").to_dict(orient="index")

# Merge information into the GeoJSON features
for feature in geojson_data["features"]:
    neighborhood = feature["properties"]["neighborhood"]
    
    # If the neighborhood exists in the CSV, add the extra information
    if neighborhood in info_lookup:
        feature["properties"]["num_sales"] = info_lookup[neighborhood]["num_sales"]
        feature["properties"]["avg_price"] = info_lookup[neighborhood]["avg_price"]
        feature["properties"]["avg_sqft"] = info_lookup[neighborhood]["avg_sqft"]
        feature["properties"]["avg_price_per_unit"] = info_lookup[neighborhood]["avg_price_per_unit"]
        feature["properties"]["avg_sqft_per_unit"] = info_lookup[neighborhood]["avg_sqft_per_unit"]

    else:
        # If no data is available, set default values
        feature["properties"]["num_sales"] = 0
        feature["properties"]["avg_price"] = None
        feature["properties"]["avg_sqft"] = None
        feature["properties"]["avg_price_per_unit"] = None
        feature["properties"]["avg_sqft_per_unit"] = None


# Save the merged GeoJSON data to a new file
with open(output_file_path, "w") as f:
    json.dump(geojson_data, f, indent=2)

print(f"Merged GeoJSON saved to '{output_file_path}'.")