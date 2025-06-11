import streamlit as st
from datetime import datetime
from typing import List

class UILogger:
    """A simple logger to capture messages for display in the Streamlit UI."""
    def __init__(self):
        if 'ui_logs' not in st.session_state:
            st.session_state.ui_logs = []
    
    def log(self, message: str):
        st.session_state.ui_logs.append(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} - {message}")
    
    def get_logs(self) -> List[str]:
        return st.session_state.ui_logs

    def clear(self):
        st.session_state.ui_logs = [] 