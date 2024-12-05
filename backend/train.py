import sqlite3
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, FunctionTransformer
from sklearn.pipeline import Pipeline
import pickle
import os
import numpy as np

# Connect to the SQLite database and load data
conn = sqlite3.connect("housing.db")
query = """
    SELECT 
        z.neighborhood AS neighborhood,
        (
            SELECT AVG(sub.sale_price)
            FROM (
                SELECT s.sale_price
                FROM sales AS s
                WHERE s.zip_code = z.zip_code AND s.total_units > 0 AND s.commercial_units = 0
                ORDER BY s.sale_price
                LIMIT 2 - (SELECT COUNT(*) FROM sales WHERE zip_code = z.zip_code AND total_units > 0 AND commercial_units = 0) % 2
                OFFSET (SELECT (COUNT(*) - 1) / 2 FROM sales WHERE zip_code = z.zip_code AND total_units > 0 AND commercial_units = 0)
            ) AS sub
        ) AS median_price,
        (
            SELECT AVG(sub.gross_sqft)
            FROM (
                SELECT s.gross_sqft
                FROM sales AS s
                WHERE s.zip_code = z.zip_code AND s.total_units > 0 AND s.commercial_units = 0
                ORDER BY s.gross_sqft
                LIMIT 2 - (SELECT COUNT(*) FROM sales WHERE zip_code = z.zip_code AND total_units > 0 AND commercial_units = 0) % 2
                OFFSET (SELECT (COUNT(*) - 1) / 2 FROM sales WHERE zip_code = z.zip_code AND total_units > 0 AND commercial_units = 0)
            ) AS sub
        ) AS median_sqft,
        (
            SELECT AVG(sub.total_units)
            FROM (
                SELECT s.total_units
                FROM sales AS s
                WHERE s.zip_code = z.zip_code AND s.total_units > 0 AND s.commercial_units = 0
                ORDER BY s.total_units
                LIMIT 2 - (SELECT COUNT(*) FROM sales WHERE zip_code = z.zip_code AND total_units > 0 AND commercial_units = 0) % 2
                OFFSET (SELECT (COUNT(*) - 1) / 2 FROM sales WHERE zip_code = z.zip_code AND total_units > 0 AND commercial_units = 0)
            ) AS sub
        ) AS median_total_units
    FROM 
        zip_neighborhood AS z
    GROUP BY 
        z.neighborhood;

"""

data = pd.read_sql_query(query, conn)
conn.close()

# Drop rows with missing data
data.dropna(inplace=True)

# Split features and target
X = data[["price", "sqft", "total_units"]]
y = data["neighborhood"]

# Split the data into train and test sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Define log transformation for skewed columns
log_transformer = FunctionTransformer(np.log1p, validate=True)  # np.log1p(x) = log(1 + x)

# Specify preprocessing steps
preprocessor = ColumnTransformer(
    transformers=[
        ("log", log_transformer, ["price"]),  # Apply log transformation to 'price'
        ("scale", StandardScaler(), ["sqft", "total_units"])  # Standardize other features
    ],
    remainder="passthrough"  # Leave other columns as they are (if any)
)

# Create a pipeline with preprocessing and KNN
pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("knn", KNeighborsClassifier(n_neighbors=10))  # Use 10 neighbors (can be optimized)
])

# Train the pipeline on your data
pipeline.fit(X_train, y_train)

# Evaluate the pipeline
accuracy = pipeline.score(X_test, y_test)
print(f"Model Accuracy: {accuracy:.2f}")

# Save the pipeline
target_folder = os.path.abspath(os.path.join(os.getcwd(), ".."))  # One level up from the current directory
file_path = os.path.join(target_folder, "recommendation_model.pkl")
with open(file_path, "wb") as f:
    pickle.dump(pipeline, f)

print(f"Model saved as '{file_path}'.")

# Get predictions on the test set
y_pred = pipeline.predict(X_test)

# Create a DataFrame to compare predictions and actual values
results = pd.DataFrame({
    "Actual": y_test,
    "Predicted": y_pred
})

# Display mismatches
print("Comparison of Actual and Predicted:")
print(results.head())
mismatches = results[results["Actual"] != results["Predicted"]]
print(f"Number of mismatches: {len(mismatches)}")
