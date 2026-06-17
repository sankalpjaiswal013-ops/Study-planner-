import streamlit as st
import json
from database import get_db_connection, get_setting, set_setting

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")

if 'user_id' not in st.session_state or st.session_state.user_id is None:
    st.warning("Please log in from the main page.")
    st.stop()

user_id = st.session_state.user_id

st.title("⚙️ Settings")

# Profile & App Settings
st.subheader("Local AI Model (Primary)")
st.write("This app uses a local Machine Learning model trained on your study data to provide predictions. The API is only used as a backup.")
if st.button("Train Local Model Now", type="primary"):
    with st.spinner("Training local model..."):
        try:
            from ml_model import load_and_aggregate_data, train_and_save_model
            df = load_and_aggregate_data()
            res = train_and_save_model(df)
            st.success(f"Model trained successfully! RMSE: {res['metrics']['rmse']:.2f}, R2: {res['metrics']['r2']:.2f}")
        except Exception as e:
            st.error(f"Error training model: {e}")

st.divider()

# Profile & App Settings
st.subheader("Profile & Application")
with st.form("settings_form"):
    api_key = st.text_input("Google Gemini API Key (Backup fallback only)", value=get_setting(user_id, "gemini_api_key", ""), type="password")
    study_goal = st.number_input("Daily Study Goal (Hours)", min_value=1, max_value=12, value=int(get_setting(user_id, "daily_goal", 2)))
    
    st.write("Pomodoro Durations (minutes)")
    col1, col2, col3 = st.columns(3)
    with col1:
        p_work = st.number_input("Work", min_value=1, value=int(get_setting(user_id, "pomodoro_work", 25)))
    with col2:
        p_short = st.number_input("Short Break", min_value=1, value=int(get_setting(user_id, "pomodoro_short", 5)))
    with col3:
        p_long = st.number_input("Long Break", min_value=1, value=int(get_setting(user_id, "pomodoro_long", 15)))
        
    if st.form_submit_button("Save Settings"):
        set_setting(user_id, "gemini_api_key", api_key)
        set_setting(user_id, "daily_goal", study_goal)
        set_setting(user_id, "pomodoro_work", p_work)
        set_setting(user_id, "pomodoro_short", p_short)
        set_setting(user_id, "pomodoro_long", p_long)
        st.success("Settings saved successfully!")

st.divider()

# Data Management
st.subheader("Data Management")
st.write("Export your data or start fresh.")

colA, colB = st.columns(2)

with colA:
    if st.button("Generate Data Backup"):
        conn = get_db_connection()
        c = conn.cursor()
        
        # Fetch all tasks
        c.execute("SELECT * FROM tasks WHERE user_id=?", (user_id,))
        tasks = [dict(r) for r in c.fetchall()]
        
        # Fetch all logs
        c.execute("SELECT * FROM study_log WHERE user_id=?", (user_id,))
        logs = [dict(r) for r in c.fetchall()]
        
        backup = {
            "tasks": tasks,
            "study_log": logs
        }
        conn.close()
        
        st.download_button(
            label="Download JSON Backup",
            data=json.dumps(backup, indent=2),
            file_name="studyplanner_backup.json",
            mime="application/json",
            type="primary"
        )

with colB:
    if st.button("Reset All Data", type="primary"):
        st.warning("Are you sure? This will delete all tasks and logs. Click confirm below.")
        
    if st.checkbox("I understand, delete my data"):
        if st.button("Confirm Delete"):
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("DELETE FROM tasks WHERE user_id=?", (user_id,))
            c.execute("DELETE FROM study_log WHERE user_id=?", (user_id,))
            c.execute("DELETE FROM pomodoro_sessions WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()
            st.success("All data has been reset.")
            st.rerun()
