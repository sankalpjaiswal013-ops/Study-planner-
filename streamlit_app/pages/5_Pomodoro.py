import streamlit as st
import time
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from database import get_db_connection, get_setting

st.set_page_config(page_title="Pomodoro Timer", page_icon="⏱️", layout="wide")

if 'user_id' not in st.session_state or st.session_state.user_id is None:
    st.warning("Please log in from the main page.")
    st.stop()

user_id = st.session_state.user_id

st.title("⏱️ Pomodoro Timer")

# Get settings
work_duration = int(get_setting(user_id, "pomodoro_work", 25))
short_break = int(get_setting(user_id, "pomodoro_short", 5))
long_break = int(get_setting(user_id, "pomodoro_long", 15))

# State initialization
if "timer_running" not in st.session_state:
    st.session_state.timer_running = False
if "time_left" not in st.session_state:
    st.session_state.time_left = work_duration * 60
if "current_phase" not in st.session_state:
    st.session_state.current_phase = "Work"
if "pomodoros_completed" not in st.session_state:
    st.session_state.pomodoros_completed = 0

# Get distinct subjects for selection
conn = get_db_connection()
c = conn.cursor()
c.execute("SELECT DISTINCT subject FROM tasks WHERE user_id=?", (user_id,))
subjects = [row["subject"] for row in c.fetchall()]
conn.close()

if not subjects:
    subjects = ["General Study"]

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Timer Controls")
    selected_subject = st.selectbox("What are you studying?", subjects)
    
    st.markdown(f"**Current Phase:** `{st.session_state.current_phase}`")
    st.markdown(f"**Completed Today:** `{st.session_state.pomodoros_completed}`")
    
    # Display the timer
    timer_placeholder = st.empty()
    progress_placeholder = st.empty()
    
    mins, secs = divmod(st.session_state.time_left, 60)
    timer_placeholder.markdown(f"<h1 style='text-align:center; font-size: 5rem; color: #38BDF8;'>{mins:02d}:{secs:02d}</h1>", unsafe_allow_html=True)
    
    # Calculate progress max depending on phase
    if st.session_state.current_phase == "Work":
        max_time = work_duration * 60
    elif st.session_state.current_phase == "Short Break":
        max_time = short_break * 60
    else:
        max_time = long_break * 60
        
    progress_pct = max(0.0, min(1.0, 1.0 - (st.session_state.time_left / max_time)))
    progress_placeholder.progress(progress_pct)
    
    # Control Buttons
    b_col1, b_col2, b_col3 = st.columns(3)
    
    with b_col1:
        if st.button("▶️ Start" if not st.session_state.timer_running else "⏸️ Pause"):
            st.session_state.timer_running = not st.session_state.timer_running
            st.rerun()
            
    with b_col2:
        if st.button("⏹️ Reset"):
            st.session_state.timer_running = False
            st.session_state.time_left = work_duration * 60
            st.session_state.current_phase = "Work"
            st.rerun()
            
    with b_col3:
        if st.button("⏭️ Skip"):
            st.session_state.time_left = 0 # Force end of timer
            st.rerun()

# Timer Logic Execution
if st.session_state.timer_running:
    if st.session_state.time_left > 0:
        time.sleep(1)
        st.session_state.time_left -= 1
        st.rerun()
    else:
        # Timer finished!
        st.session_state.timer_running = False
        
        # Play sound (using html audio tag)
        st.markdown(f"""
            <audio autoplay class="hidden">
                <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
            </audio>
            """, unsafe_allow_html=True)
        
        st.success(f"{st.session_state.current_phase} session completed!")
        
        # Log to database if it was a work session
        if st.session_state.current_phase == "Work":
            st.session_state.pomodoros_completed += 1
            
            conn = get_db_connection()
            c = conn.cursor()
            now = datetime.now().isoformat()
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            # Log Pomodoro
            c.execute("INSERT INTO pomodoro_sessions (user_id, subject, duration_mins, completed_at, session_type) VALUES (?, ?, ?, ?, ?)",
                      (user_id, selected_subject, work_duration, now, "Work"))
                      
            # Add to daily study log
            c.execute("SELECT id, hours_studied FROM study_log WHERE user_id=? AND date=? AND subject=?", (user_id, today_str, selected_subject))
            log_entry = c.fetchone()
            
            hours_added = work_duration / 60.0
            
            if log_entry:
                new_hours = log_entry["hours_studied"] + hours_added
                c.execute("UPDATE study_log SET hours_studied=? WHERE id=?", (new_hours, log_entry["id"]))
            else:
                c.execute("INSERT INTO study_log (user_id, date, subject, hours_studied) VALUES (?, ?, ?, ?)", (user_id, today_str, selected_subject, hours_added))
                
            conn.commit()
            conn.close()

            # Switch to break
            if st.session_state.pomodoros_completed % 4 == 0:
                st.session_state.current_phase = "Long Break"
                st.session_state.time_left = long_break * 60
            else:
                st.session_state.current_phase = "Short Break"
                st.session_state.time_left = short_break * 60
        else:
            # Switch back to work
            st.session_state.current_phase = "Work"
            st.session_state.time_left = work_duration * 60
            
        time.sleep(2) # Give user a moment to see the message
        st.rerun()

with col2:
    st.subheader("Your Stats")
    conn = get_db_connection()
    c = conn.cursor()
    
    # Weekly Pomodoro Chart
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    c.execute("SELECT substr(completed_at, 1, 10) as date, COUNT(*) as sessions FROM pomodoro_sessions WHERE user_id=? AND completed_at >= ? GROUP BY date", (user_id, week_ago))
    data = c.fetchall()
    conn.close()
    
    if data:
        df = pd.DataFrame([dict(r) for r in data])
        fig = px.bar(df, x="date", y="sessions", title="Pomodoros (Last 7 Days)", color_discrete_sequence=["#F43F5E"])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No pomodoro sessions logged in the last 7 days. Start studying!")
