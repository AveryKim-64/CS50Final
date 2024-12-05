#%%
import sqlite3
import pandas as pd
import json
import numpy as np
from shapely.geometry import Point, shape
from tqdm import tqdm
import os

# Path to the database file
db_path = "housing.db"

# Check if the file exists
if os.path.exists(db_path):
    os.remove(db_path)
    print(f"Database '{db_path}' has been cleared.")
else:
    print(f"Database '{db_path}' does not exist.")


# Load CSV files
nyc_zip_codes = pd.read_csv("nyc-zip-codes.csv", dtype={"ZipCode": str})  # Load NYC ZIP codes
nyc_zip_codes["ZipCode"] = nyc_zip_codes["ZipCode"].str.zfill(5)  # Ensure 5-digit ZIP codes

zip_data = pd.read_csv("zip_lat_long.csv", dtype={"ZIP": str})  # Load all ZIP codes with coordinates
zip_data["ZIP"] = zip_data["ZIP"].str.zfill(5)  # Ensure 5-digit ZIP codes

# Filter ZIP codes to include only those in NYC
valid_zip_data = zip_data[zip_data["ZIP"].isin(nyc_zip_codes["ZipCode"])]  # Filter for NYC ZIP codes

# Load GeoJSON file
current_dir = os.path.dirname(__file__)
file_path = os.path.join(current_dir, "../static/nyc_neighborhoods.json")
with open(file_path, "r") as f:
    geojson_data = json.load(f)

# Function to find the neighborhood for given coordinates
def find_neighborhood(lat, lng):
    point = Point(lng, lat)  # Shapely uses (longitude, latitude)
    for feature in geojson_data["features"]:
        geometry = feature.get("geometry")  # Safely get the geometry
        if geometry is None:
            continue  # Skip features without geometry
        polygon = shape(geometry)  # Convert GeoJSON geometry to Shapely shape
        if polygon.contains(point):
            properties = feature.get("properties", {})
            neighborhood = properties.get("neighborhood", "Unknown")
            borough = properties.get("borough", "Unknown")
            return neighborhood, borough
    return None, None  # If no match is found

# Create SQLite3 database
conn = sqlite3.connect("housing.db")
cursor = conn.cursor()

# Create the table
cursor.execute("""
CREATE TABLE IF NOT EXISTS zip_neighborhood (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zip_code TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    neighborhood TEXT,
    borough TEXT
);
""")

# Process the filtered ZIP data and insert into the table
zip_mappings = []
print("Processing NYC ZIP codes...")
for _, row in tqdm(valid_zip_data.iterrows(), total=valid_zip_data.shape[0], desc="Progress", unit="zip"):
    zip_code = row["ZIP"]
    lat = row["LAT"]
    lng = row["LNG"]
    neighborhood, borough = find_neighborhood(lat, lng)
    zip_mappings.append((zip_code, lat, lng, neighborhood, borough))

# Insert data into the table
cursor.executemany("""
INSERT INTO zip_neighborhood (zip_code, lat, lng, neighborhood, borough)
VALUES (?, ?, ?, ?, ?);
""", zip_mappings)

# Commit changes
conn.commit()

# Verify data
cursor.execute("SELECT * FROM zip_neighborhood LIMIT 10;")
print("Sample Data:", cursor.fetchall())

# Close the connection
conn.close()

#-------------------------------------
#%%
# Load the NYC rolling sales CSV file
sales_data = pd.read_csv("nyc-rolling-sales.csv", dtype={"ZIP CODE": str})

# Select and clean relevant columns
sales_data = sales_data[[
    "ZIP CODE", "ADDRESS", "RESIDENTIAL UNITS", "COMMERCIAL UNITS", 
    "TOTAL UNITS", "LAND SQUARE FEET", "GROSS SQUARE FEET", "SALE PRICE"
]]

# Rename columns to match the database schema
sales_data = sales_data.rename(columns={
    "ZIP CODE": "zip_code",
    "ADDRESS": "address",
    "RESIDENTIAL UNITS": "residential_units",
    "COMMERCIAL UNITS": "commercial_units",
    "TOTAL UNITS": "total_units",
    "LAND SQUARE FEET": "land_sqft",
    "GROSS SQUARE FEET": "gross_sqft",
    "SALE PRICE": "sale_price"
})

# Replace "NaN" strings with actual NaN values
sales_data.replace("NaN", np.nan, inplace=True, regex=False)
sales_data.replace("nan", np.nan, inplace=True, regex=False)

# Drop rows with null values in the required columns
sales_data = sales_data.dropna(subset=[
    "zip_code", "address", "residential_units", "commercial_units", 
    "total_units", "land_sqft", "gross_sqft", "sale_price"
])

# Convert numeric columns to appropriate types
numeric_columns = ["residential_units", "commercial_units", "total_units", "land_sqft", "gross_sqft", "sale_price"]
sales_data[numeric_columns] = sales_data[numeric_columns].apply(pd.to_numeric, errors="coerce")

# Drop rows where numeric conversion failed (sale_price or others became NaN)
sales_data = sales_data.dropna(subset=numeric_columns)

# Connect to SQLite database
conn = sqlite3.connect("housing.db")
cursor = conn.cursor()

# Create the `sales` table
cursor.execute("""
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zip_code TEXT NOT NULL,
    address TEXT NOT NULL,
    residential_units INTEGER NOT NULL,
    commercial_units INTEGER NOT NULL,
    total_units INTEGER NOT NULL,
    land_sqft REAL NOT NULL,
    gross_sqft REAL NOT NULL,
    sale_price REAL NOT NULL
);
""")

#%%
# Insert the cleaned data into the `sales` table
chunk_size = 1000  # Insert in chunks
for i in range(0, len(sales_data), chunk_size):
    sales_data.iloc[i:i+chunk_size].to_sql("sales", conn, if_exists="append", index=False)

# Commit and close the connection
conn.commit()
conn.close()

# Verify no rows with NaN in sale_price remain
print("Rows with NaN in sale_price after cleaning:", sales_data[sales_data["sale_price"].isnull()])

