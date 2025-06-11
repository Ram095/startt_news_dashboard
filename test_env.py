from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Print Firebase configuration
print("Firebase Configuration:")
print(f"API Key: {os.getenv('FIREBASE_API_KEY')}")
print(f"Auth Domain: {os.getenv('FIREBASE_AUTH_DOMAIN')}")
print(f"Project ID: {os.getenv('FIREBASE_PROJECT_ID')}")
print(f"Storage Bucket: {os.getenv('FIREBASE_STORAGE_BUCKET')}")
print(f"Messaging Sender ID: {os.getenv('FIREBASE_MESSAGING_SENDER_ID')}")
print(f"App ID: {os.getenv('FIREBASE_APP_ID')}")
print(f"Measurement ID: {os.getenv('FIREBASE_MEASUREMENT_ID')}")

# Print Backend URL
print("\nBackend Configuration:")
print(f"API URL: {os.getenv('BACKEND_API_URL')}") 