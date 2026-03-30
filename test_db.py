import os
from dotenv import load_dotenv
from pymongo import MongoClient

def test_connection():
    load_dotenv()
    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("Error: MONGO_URI is missing from .env")
        return
        
    try:
        print(f"Attempting to connect to MongoDB...")
        # Timeout after 5 seconds instead of waiting forever if there's an issue
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.server_info()
        print("Success! Connected to MongoDB.")
        
        # Test inserting a dummy record
        db = client["bbbot"]
        test_col = db["test_connection"]
        test_col.insert_one({"status": "ok"})
        test_col.delete_one({"status": "ok"})
        print("Success! Can read and write to the database.")
        
    except Exception as e:
        print(f"\nFailed to connect to MongoDB:\n{e}")

if __name__ == "__main__":
    test_connection()