import streamlit as st
import pyrebase
import os
from dotenv import load_dotenv
import requests
from typing import Optional, Dict, Any
import time

# Load environment variables
load_dotenv()

def validate_firebase_config(config: Dict[str, str]) -> bool:
    """Validate Firebase configuration"""
    required_keys = [
        "apiKey",
        "authDomain",
        "projectId",
        "storageBucket",
        "messagingSenderId",
        "appId"
    ]
    
    missing_keys = [key for key in required_keys if not config.get(key)]
    if missing_keys:
        st.error(f"Missing required Firebase configuration keys: {', '.join(missing_keys)}")
        return False
    
    if config["apiKey"] == "None" or not config["apiKey"]:
        st.error("Firebase API key is not properly configured")
        return False
        
    return True

def get_firebase_config() -> Dict[str, str]:
    """Get Firebase configuration from environment variables"""
    config = {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "databaseURL": os.getenv("FIREBASE_DATABASE_URL"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID"),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID")
    }
    
    if not validate_firebase_config(config):
        st.error("Invalid Firebase configuration. Please check your .env file.")
        return {}
        
    return config

def initialize_firebase():
    """Initialize Firebase client"""
    try:
        # Initialize Pyrebase with client configuration
        config = get_firebase_config()
        if not config:
            return None
            
        return pyrebase.initialize_app(config)
    except Exception as e:
        st.error(f"Failed to initialize Firebase: {str(e)}")
        return None

def get_auth():
    """Get Firebase Auth instance"""
    firebase = initialize_firebase()
    if not firebase:
        st.error("Failed to initialize Firebase. Please check your configuration.")
        return None
    return firebase.auth()

def get_api_key() -> Optional[str]:
    """Get Firebase API key from environment variables"""
    return os.getenv("FIREBASE_API_KEY")

async def verify_token_with_backend(id_token: str) -> bool:
    """Verify the Firebase ID token with your backend"""
    try:
        backend_url = os.getenv("BACKEND_API_URL", "http://api-dev.startt.in/api")
        headers = {"Authorization": f"Bearer {id_token}"}
        response = requests.get(f"{backend_url}/v1/users", headers=headers)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Token verification failed: {str(e)}")
        return False

def refresh_token(user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Refresh the Firebase ID token"""
    try:
        auth = get_auth()
        if not auth:
            return None
            
        # Refresh the token
        user = auth.refresh(user['refreshToken'])
        return user
    except Exception:
        return None

async def login_user(email: str, password: str) -> bool:
    """Login user with email and password"""
    try:
        auth = get_auth()
        if not auth:
            return False
        
        # Pass API key explicitly to avoid issues with some pyrebase versions
        api_key = get_api_key()
        if not api_key:
            st.error("Firebase API Key is not configured.")
            return False
            
        request_ref = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={api_key}"
        headers = {"Content-Type": "application/json"}
        data = {"email": email, "password": password, "returnSecureToken": True}
        
        response = requests.post(request_ref, headers=headers, json=data)
        response.raise_for_status()
        user = response.json()
        
        # Get the ID token
        id_token = user.get('idToken')
        if not id_token:
            st.error("Failed to retrieve ID token after login.")
            return False
        
        # Verify the token with your backend
        if await verify_token_with_backend(id_token):
            st.session_state['user'] = user
            st.session_state['id_token'] = id_token
            st.session_state['last_token_refresh'] = time.time()
            return True
        else:
            st.error("Token verification failed")
            return False
            
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
        return False

async def signup_user(email: str, password: str) -> bool:
    """Sign up new user with email and password"""
    try:
        auth = get_auth()
        if not auth:
            return False
            
        # Pass API key explicitly to avoid issues with some pyrebase versions
        api_key = get_api_key()
        if not api_key:
            st.error("Firebase API Key is not configured.")
            return False

        request_ref = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser?key={api_key}"
        headers = {"Content-Type": "application/json"}
        data = {"email": email, "password": password, "returnSecureToken": True}
        
        response = requests.post(request_ref, headers=headers, json=data)
        response.raise_for_status()
        user = response.json()
        
        # Get the ID token
        id_token = user.get('idToken')
        if not id_token:
            st.error("Failed to retrieve ID token after signup.")
            return False
        
        # Verify the token with your backend
        if await verify_token_with_backend(id_token):
            st.session_state['user'] = user
            st.session_state['id_token'] = id_token
            st.session_state['last_token_refresh'] = time.time()
            return True
        else:
            st.error("Token verification failed")
            return False
            
    except Exception as e:
        st.error(f"Signup failed: {str(e)}")
        return False

def logout_user():
    """Logout current user"""
    if 'user' in st.session_state:
        del st.session_state['user']
    if 'id_token' in st.session_state:
        del st.session_state['id_token']
    if 'last_token_refresh' in st.session_state:
        del st.session_state['last_token_refresh']

def get_current_user() -> Optional[Dict[str, Any]]:
    """Get current user from session state"""
    return st.session_state.get('user', None)

def get_id_token() -> Optional[str]:
    """Get current user's ID token"""
    return st.session_state.get('id_token', None)

async def check_auth_status() -> bool:
    """Check if the user is authenticated and token is valid"""
    user = get_current_user()
    if not user:
        return False
        
    # Check if token needs refresh (Firebase tokens expire after 1 hour)
    last_refresh = st.session_state.get('last_token_refresh', 0)
    if time.time() - last_refresh > 3300:  # Refresh 5 minutes before expiry
        # Try to refresh the token
        refreshed_user = refresh_token(user)
        if refreshed_user:
            st.session_state['user'] = refreshed_user
            st.session_state['id_token'] = refreshed_user['idToken']
            st.session_state['last_token_refresh'] = time.time()
            return True
        else:
            logout_user()
            return False
            
    # Verify token with backend
    id_token = get_id_token()
    if id_token and await verify_token_with_backend(id_token):
        return True
        
    logout_user()
    return False

def is_user_logged_in() -> bool:
    """Check if user is logged in"""
    return 'user' in st.session_state and 'id_token' in st.session_state 