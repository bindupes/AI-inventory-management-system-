import pandas as pd
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

# Load your data
df = pd.read_csv('sales_data1.csv')

# Convert 'date_of_purchase' to datetime format
df['date_of_purchase'] = pd.to_datetime(df['date_of_purchase'], format='%d-%m-%Y')

# Set 'date_of_purchase' as the index
df.set_index('date_of_purchase', inplace=True)

# Select the target variable (e.g., 'quantity')
target_column = 'quantity'

# Normalize the target variable for better model performance
scaler = MinMaxScaler()
df[target_column] = scaler.fit_transform(df[target_column].values.reshape(-1, 1))

# Create a new column for the shifted target values (e.g., for a 7-day prediction)
shift_steps = 7
df['shifted_target'] = df[target_column].shift(-shift_steps)

# Drop the last 'shift_steps' rows due to the shifted target
df = df.dropna()

# Keep track of product names
df['product_name'] = df['product_name']  # Ensure product_name column exists

# Split into features and target
X = df.drop(columns=['shifted_target', target_column])
y = df['shifted_target']

# Handle categorical features using OneHotEncoder
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

# Split into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

# Train the model
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
    # Merge X_test with original DataFrame to include 'product_name'
    X_test = X_test.merge(df[['product_name']], left_index=True, right_index=True, how='left')

# Aggregate predicted demand for each product
agg_predictions_df = X_test.groupby('product_name').agg({
    'Predicted Demand': 'mean'  # Or another aggregation function as needed
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

# Display the results
print(agg_predictions_df)