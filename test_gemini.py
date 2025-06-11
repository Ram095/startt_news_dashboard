import os
import requests
import json
from dotenv import load_dotenv

def test_gemini_api():
    """
    Tests the Gemini API with a sample request.
    """
    # Load environment variables from .env file
    load_dotenv()
    
    # Get the API key from environment variables
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("Error: GEMINI_API_KEY not found.")
        print("Please create a .env file in the root directory and add the following line:")
        print('GEMINI_API_KEY="YOUR_API_KEY"')
        return

    print(f"Using API Key: ...{api_key[-4:]}")

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Explain how AI works in a few words"
                    }
                ]
            }
        ]
    }
    
    params = {
        'key': api_key
    }

    try:
        response = requests.post(url, headers=headers, params=params, json=data)
        response.raise_for_status()  # Raises an exception for bad status codes (4xx or 5xx)
        
        print("\n✅ API call successful!")
        print("\nResponse JSON:")
        # Pretty print the JSON response
        print(json.dumps(response.json(), indent=2))

    except requests.exceptions.HTTPError as http_err:
        print(f"\n❌ HTTP error occurred: {http_err}")
        print(f"\nResponse Code: {http_err.response.status_code}")
        print(f"Response Body: {http_err.response.text}")
    except Exception as err:
        print(f"\n❌ An other error occurred: {err}")

if __name__ == "__main__":
    test_gemini_api() 