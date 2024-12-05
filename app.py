from flask import Flask, g, render_template, jsonify, request
import sqlite3
import os
import pandas as pd
import pickle

#specifies  the token provided by the map creation API
MAPBOX_ACCESS_TOKEN = 'pk.eyJ1IjoiYXZlcnlraW0xMjMiLCJhIjoiY200NGVycDdxMGxrcjJtcTVtNnc3dzAzaSJ9.nG9HktJDNlPe4bHsmWDYhg'

app = Flask(__name__)

# Define the database path relative to the current file
DATABASE = os.path.join(os.path.dirname(__file__), 'finance.db')



@app.route("/")
def home():
    """
    Render the homepage with a Mapbox map of NYC.
    """
    token = MAPBOX_ACCESS_TOKEN  # Retrieve token from environment
    return render_template('index.html', mapbox_token=token)

@app.route("/recommend", methods=["POST"])
def recommend_neighborhood():
    """
    Handle user inputs and return the best neighborhood recommendation.
    """
    try:
        # Parse JSON data from the POST request
        data = request.get_json()
        price = float(data.get("price", 0))
        sqft = float(data.get("sqft", 0))
        total_units = int(data.get("total_units", 0))

        # Wrap inputs into a DataFrame with the correct column names
        input_data = pd.DataFrame([{
            "price": price,        # Match the column names used in the model
            "sqft": sqft,         # Match the column names used in the model
            "total_units": total_units  # Match the column names used in the model
        }])

        # Load the trained model
        with open("recommendation_model.pkl", "rb") as f:
            model = pickle.load(f)

        # Predict the best neighborhood
        prediction = model.predict(input_data)
        print(model.named_steps['preprocessor'])

        return jsonify({"neighborhood": prediction[0]})
    
    except Exception as e:
        app.logger.error(f"Error during recommendation: {e}")
        return jsonify({"error": "An error occurred while processing your request. Please try again later."}), 400

@app.route("/search")
def display_search():
    """
    Display the search page.
    """
    return render_template('search.html')

@app.route("/transactions")
def display_first_transaction():
    """
    Display the first row from the transactions table.
    """
    query = "SELECT * FROM transactions LIMIT 1"
    first_row = query_db(query, one=True)  # Fetch the first row

    if first_row:
        # Convert the row into a readable format (dictionary)
        row_dict = dict(first_row)
        return f"<p>First Transaction: {row_dict}</p>"
    else:
        return "<p>No transactions found in the database.</p>"
    
@app.route("/info")
def display_info():
    """
    display project info
    """
    return render_template('info.html')


if __name__ == "__main__":
    app.run(debug=True)



# helper functions for the database
def get_db():
    """Connect to the database and return the connection with sqllite3."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # Enable dictionary-style row access
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Close the database connection at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    """Execute a database query and return the results."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

