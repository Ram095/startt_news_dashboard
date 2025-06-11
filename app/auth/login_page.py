import streamlit as st
import asyncio
from .firebase_config import login_user, signup_user, logout_user, is_user_logged_in

def show_login_page():
    """Show the login page"""
    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("Login")
        
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if not email or not password:
                    st.error("Please fill in all fields")
                    return
                    
                # Create a placeholder for the spinner
                with st.spinner("Logging in..."):
                    # Run the async login function
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        success = loop.run_until_complete(login_user(email, password))
                        if success:
                            st.success("Login successful!")
                            st.rerun()
                        else:
                            st.error("Login failed. Please check your credentials.")
                    finally:
                        loop.close()

    # Commented out signup section
    """
    with tab2:
        with st.form("signup_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submit = st.form_submit_button("Sign Up")
            
            if submit:
                if not email or not password or not confirm_password:
                    st.error("Please fill in all fields")
                    return
                    
                if password != confirm_password:
                    st.error("Passwords do not match")
                    return
                    
                # Create a placeholder for the spinner
                with st.spinner("Creating account..."):
                    # Run the async signup function
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        success = loop.run_until_complete(signup_user(email, password))
                        if success:
                            st.success("Account created successfully!")
                            st.rerun()
                        else:
                            st.error("Signup failed. Please try again.")
                    finally:
                        loop.close()
    """

def show_logout_button():
    """Display logout button"""
    if st.sidebar.button("Logout"):
        logout_user()
        st.rerun() 