from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import mysql.connector
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import pickle
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error

app = Flask(__name__)
app.secret_key = "super_secret_key"  # Used for session handling and flash messages

# MySQL Database Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Chinnu@08',
    'database': 'horcrux'
}

# Email Configuration
smtp_server = 'smtp.gmail.com'
smtp_port = 587
smtp_user = 'murugeshpavana86@gmail.com'
smtp_password = 'qrzf ctff yaxg iuqh'
from_email = 'murugeshpavana86@gmail.com'

# Load CSV data into DataFrame
df = pd.read_csv('INVENTORY6.csv')
df['PRICE'] = pd.to_numeric(df['PRICE'], errors='coerce')

# Load model and scaler
def load_model():
    # Load your data
    sales_df = pd.read_csv('sales_data1.csv')

    # Convert 'date_of_purchase' to datetime format
    sales_df['date_of_purchase'] = pd.to_datetime(sales_df['date_of_purchase'], format='%d-%m-%Y')

    # Set 'date_of_purchase' as the index
    sales_df.set_index('date_of_purchase', inplace=True)

    # Normalize the target variable
    target_column = 'quantity'
    scaler = MinMaxScaler()
    sales_df[target_column] = scaler.fit_transform(sales_df[target_column].values.reshape(-1, 1))

    # Create a new column for the shifted target values
    shift_steps = 7
    sales_df['shifted_target'] = sales_df[target_column].shift(-shift_steps)

    # Drop the last 'shift_steps' rows
    sales_df = sales_df.dropna()

    # Split into features and target
    X = sales_df.drop(columns=['shifted_target', target_column])
    y = sales_df['shifted_target']

    # Handle categorical features
    categorical_cols = X.select_dtypes(include=['object']).columns

    # Create a pipeline for pre-processing
    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_cols),
            ('num', 'passthrough', X.select_dtypes(include=['float64', 'int64']).columns)
        ]
    )

    # Create a pipeline for linear regression
    pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('model', LinearRegression())
    ])

    # Train the model
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    pipeline.fit(X_train, y_train)

    # Make predictions
    y_pred = pipeline.predict(X_test)

    # Inverse transform the predictions to the original scale
    y_pred_inv = scaler.inverse_transform(y_pred.reshape(-1, 1))
    y_test_inv = scaler.inverse_transform(y_test.values.reshape(-1, 1))

    # Evaluate the model
    mse = mean_squared_error(y_test_inv, y_pred_inv)
    mae = mean_absolute_error(y_test_inv, y_pred_inv)

    print("Mean Squared Error:", mse)
    print("Mean Absolute Error:", mae)

    # Add predictions to X_test
    X_test['Predicted Demand'] = y_pred_inv.flatten()

    # Ensure 'product_name' is in X_test for aggregation
    if 'product_name' not in X_test.columns:
        X_test = X_test.merge(sales_df[['product_name']], left_index=True, right_index=True, how='left')

    # Aggregate predicted demand for each product
    agg_predictions_df = X_test.groupby('product_name').agg({
        'Predicted Demand': 'mean'
    }).reset_index()

    # Define a function to determine the order quantity based on predicted demand
    def determine_order_quantity(demand):
        if demand > 58:
            return 40, 'High Quantity'
        elif 50 <= demand <= 69:
            return 30, 'Medium Quantity'
        else:
            return 15, 'Low Quantity'

    # Apply the function to the DataFrame
    agg_predictions_df[['Order Quantity', 'Quantity Category']] = agg_predictions_df['Predicted Demand'].apply(lambda x: pd.Series(determine_order_quantity(x)))

    # Sort by order quantity (high to low) and then by predicted demand
    agg_predictions_df.sort_values(by=['Order Quantity', 'Predicted Demand'], ascending=[False, False], inplace=True)

    return agg_predictions_df

# Route for the login page
@app.route('/')
def login():
    return render_template('login.html')

# Route to handle login form submission
@app.route('/login', methods=['POST'])
def login_post():
    username = request.form['username']
    password = request.form['password']

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    query = "SELECT * FROM employees WHERE id = %s AND password = %s"
    cursor.execute(query, (username, password))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user:
        flash('Login successful!', 'success')
        check_inventory_and_notify()  # Check inventory after login
        return redirect(url_for('dashboard'))
    else:
        flash('Invalid username or password', 'error')
        return redirect(url_for('login'))

# Manager credentials
MANAGER_ID = '100'
MANAGER_PASSWORD = 'manager@100'

# Route for the manager login page
@app.route('/login_manager', methods=['POST'])
def login_manager():
    username = request.form['username']
    password = request.form['password']

    if username == MANAGER_ID and password == MANAGER_PASSWORD:
        flash('Login successful!', 'success')
        return redirect(url_for('manage'))
    else:
        flash('Invalid manager credentials', 'error')
        return redirect(url_for('login'))

# Route for the manage products page (only accessible to manager)
@app.route('/manage', methods=['GET', 'POST'])
def manage():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    # Fetch all product names for the dropdown menu
    cursor.execute("SELECT `PRODUCT NAME` FROM products")
    products = cursor.fetchall()

    # Fetch product details if POST request is made
    product_details = None
    if request.method == 'POST':
        selected_product_name = request.form['product_name']
        cursor.execute("SELECT `id`, `PRODUCT NAME`, `PRICE`, `QUANTITY_IN_STOCK` FROM products WHERE `PRODUCT NAME` = %s", (selected_product_name,))
        product_details = cursor.fetchone()

    cursor.close()
    conn.close()

    # Load model and predictions
    predictions_df = load_model()
    
    # Pass predictions and product details to the template
    return render_template('manage.html', products=products, product_details=product_details, predictions=predictions_df.to_dict(orient='records'))

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    product_name = data.get('product_name')

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Fetch product details from the database
        query = """
            SELECT `PRODUCT NAME`, `PRICE`, `QUANTITY_IN_STOCK`
            FROM products
            WHERE `PRODUCT NAME` = %s
        """
        cursor.execute(query, (product_name,))
        product = cursor.fetchone()

        cursor.close()
        conn.close()

        if product:
            # Return product details as JSON
            product_details = {
                'name': product[0],
                'price': product[1],
                'quantity': product[2]
            }
            return jsonify(product_details)
        else:
            return jsonify({'error': 'Product not found'})
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return jsonify({'error': 'An error occurred while fetching product details'})

# Function to check inventory and send email notifications
def check_inventory_and_notify():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Select products that are at or below the reorder level
        query = "SELECT `PRODUCT NAME`, `QUANTITY_IN_STOCK`, `REORDER_LEVEL`, `MAIL_ID` FROM products WHERE `QUANTITY_IN_STOCK` <= `REORDER_LEVEL`"
        cursor.execute(query)
        products = cursor.fetchall()

        for product in products:
            product_name, quantity_in_stock, reorder_level, supplier_email = product
            if quantity_in_stock <= reorder_level:
                send_restock_email(product_name, supplier_email)

        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Function to send restock email
def send_restock_email(product_name, supplier_email):
    subject = 'Restocking Needed'
    body = f"""
    Dear Supplier,

    We need to restock the following product:

    Product Name: {product_name}

    Please send more stock at your earliest convenience.

    Thank you,
    Your Inventory System
    """

    try:
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = supplier_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        print(f"Restock email sent to {supplier_email} for product {product_name}.")
    except Exception as e:
        print(f"An error occurred while sending email: {e}")

# Route for the dashboard
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# Route for displaying the product information
@app.route('/product_info/<product_name>', methods=['GET'])
def product_info(product_name):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT `PRODUCT NAME`, `PRICE`, `QUANTITY_IN_STOCK` FROM products WHERE `PRODUCT NAME` = %s", (product_name,))
        product = cursor.fetchone()
        cursor.close()
        conn.close()

        if product:
            product_details = {
                'name': product[0],
                'price': product[1],
                'quantity': product[2]
            }
            return jsonify(product_details)
        else:
            return jsonify({'error': 'Product not found'})
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return jsonify({'error': 'An error occurred while fetching product details'})

# Route for handling error pages
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True)
