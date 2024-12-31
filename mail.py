from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

app = Flask(__name__)
app.secret_key = "super_secret_key"  # Used for session handling and flash messages

# MySQL Database Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Chinnu@08',
    'database': 'horcrux',
    'charset': 'utf8mb4'
}

# Email Configuration
smtp_server = 'smtp.gmail.com'
smtp_port = 587
smtp_user = 'murugeshpavana86@gmail.com'
smtp_password = 'qrzf ctff yaxg iuqh'
from_email = 'murugeshpavana86@gmail.com'

# Route for the login page
@app.route('/')
def login():
    return render_template('login.html')

# Route to handle login form submission
@app.route('/login', methods=['POST'])
def login_post():
    username = request.form['username']
    password = request.form['password']

    # Connect to MySQL database
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    # Query to check if the user exists and the password matches
    query = "SELECT * FROM employees WHERE id = %s AND password = %s"
    cursor.execute(query, (username, password))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user:
        flash('Login successful!', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash('Invalid username or password', 'error')
        return redirect(url_for('login'))

# A sample dashboard route (after login success)
@app.route('/index')
def dashboard():
    return render_template('index.html')

# Route to handle form submission for product quantities
@app.route('/update_stock', methods=['POST'])
def update_stock():
    try:
        # Connect to MySQL database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Get form data
        product_names = request.form.getlist('product_name[]')
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')

        for product_id, quantity in zip(product_ids, quantities):
            # Fetch the current quantity_in_stock for the product
            cursor.execute("SELECT quantity_in_stock FROM products WHERE id = %s", (product_id,))
            result = cursor.fetchone()
            if result:
                current_stock = result[0]
                new_stock = current_stock - int(quantity)

                # Update the quantity_in_stock in the database
                cursor.execute("UPDATE products SET quantity_in_stock = %s WHERE id = %s", (new_stock, product_id))

                # If restocking is needed, send an email
                if new_stock <= 10:  # Example threshold for restocking notification
                    cursor.execute("SELECT supplier_email FROM products WHERE id = %s", (product_id,))
                    supplier_email = cursor.fetchone()[0]
                    send_restock_email(product_id, supplier_email)

        conn.commit()
        cursor.close()
        conn.close()

        flash('Stock updated successfully!', 'success')
    except mysql.connector.Error as err:
        flash(f"Error: {err}", 'error')
    except Exception as e:
        flash(f"An error occurred: {e}", 'error')

    return redirect(url_for('dashboard'))

def send_restock_email(product_id, supplier_email):
    subject = 'Restocking Needed'
    body = f"""
    Dear Supplier,

    We need to restock the following product:

    Product ID: {product_id}
    Please arrange to send more stock at your earliest convenience.

    Thank you,
    Your Company Name
    """

    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = supplier_email
    msg['Subject'] = subject

    # Attach the email body with proper encoding
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        # Set up the email server
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)

            # Send the email
            server.send_message(msg)
        print(f'Email sent to {supplier_email} regarding product {product_id}')
    except smtplib.SMTPException as e:
        print(f"Failed to send email: {e}")

if __name__ == '__main__':
    app.run(debug=True)
