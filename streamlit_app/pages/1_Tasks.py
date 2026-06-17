import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_db_connection
from utils import calculate_subject_score

st.set_page_config(page_title="Task & Subject Manager", page_icon="📝", layout="wide")

if 'user_id' not in st.session_state or st.session_state.user_id is None:
    st.warning("Please log in from the main page.")
    st.stop()

user_id = st.session_state.user_id

st.title("📝 Task & Subject Manager")

# Add Task Form
with st.expander("➕ Add New Task", expanded=False):
    with st.form("new_task_form"):
        col1, col2 = st.columns(2)
        with col1:
            subject = st.text_input("Subject Name", placeholder="e.g. Math, Physics")
            topic = st.text_input("Topic", placeholder="e.g. Algebra")
            difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"])
        with col2:
            est_mins = st.number_input("Estimated Time (mins)", min_value=5, value=30, step=5)
            due_date = st.date_input("Due Date")
            completed = st.checkbox("Already Completed?")
            
        if st.form_submit_button("Add Task"):
            if not subject or not topic:
                st.error("Subject and Topic are required.")
            else:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute('''
                    INSERT INTO tasks (user_id, subject, topic, difficulty, estimated_mins, due_date, completed, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, subject, topic, difficulty, est_mins, str(due_date), 1 if completed else 0, datetime.now().isoformat()))
                conn.commit()
                conn.close()
                st.success("Task added successfully!")
                st.rerun()

st.divider()

# View Tasks
st.subheader("Your Tasks")

conn = get_db_connection()
c = conn.cursor()
c.execute("SELECT id, subject, topic, difficulty, estimated_mins, due_date, completed FROM tasks WHERE user_id=?", (user_id,))
tasks = c.fetchall()

subjects = list(set([t["subject"] for t in tasks])) if tasks else []

if not tasks:
    st.info("No tasks found. Add some above!")
else:
    # Filter controls
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        f_subj = st.selectbox("Filter by Subject", ["All"] + subjects)
    with f_col2:
        f_status = st.selectbox("Filter by Status", ["All", "Pending", "Completed"])
    
    # Process rows
    display_data = []
    for t in tasks:
        if f_subj != "All" and t["subject"] != f_subj:
            continue
        if f_status == "Pending" and t["completed"] == 1:
            continue
        if f_status == "Completed" and t["completed"] == 0:
            continue
            
        display_data.append({
            "ID": t["id"],
            "Subject": t["subject"],
            "Topic": t["topic"],
            "Difficulty": t["difficulty"],
            "Est. Mins": t["estimated_mins"],
            "Due Date": t["due_date"],
            "Status": "✅ Done" if t["completed"] else "⏳ Pending"
        })
    
    if display_data:
        df = pd.DataFrame(display_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Action controls for Mark Complete or Delete
        st.write("### Actions")
        a_col1, a_col2 = st.columns(2)
        task_ids = [str(d["ID"]) for d in display_data]
        
        with a_col1:
            sel_id_complete = st.selectbox("Select Task ID to toggle completion", task_ids)
            if st.button("Toggle Complete Status"):
                c.execute("UPDATE tasks SET completed = 1 - completed WHERE id=? AND user_id=?", (sel_id_complete, user_id))
                conn.commit()
                st.success("Status updated!")
                st.rerun()
                
        with a_col2:
            sel_id_del = st.selectbox("Select Task ID to delete", task_ids)
            if st.button("🗑️ Delete Task", type="primary"):
                c.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (sel_id_del, user_id))
                conn.commit()
                st.success("Task deleted!")
                st.rerun()
    else:
        st.write("No tasks match the filters.")

st.divider()

# Subject Tracking Summary
st.subheader("Subject Summary")
summary_data = []
for sub in subjects:
    c.execute("SELECT COUNT(*) as total, SUM(completed) as done FROM tasks WHERE user_id=? AND subject=?", (user_id, sub))
    row = c.fetchone()
    total = row["total"] or 0
    done = row["done"] or 0
    pending = total - done
    score = calculate_subject_score(user_id, sub)
    
    summary_data.append({
        "Subject": sub,
        "Total Tasks": total,
        "Completed": done,
        "Pending": pending,
        "Subject Score": f"{score}/100"
    })

if summary_data:
    st.table(pd.DataFrame(summary_data))

conn.close()
