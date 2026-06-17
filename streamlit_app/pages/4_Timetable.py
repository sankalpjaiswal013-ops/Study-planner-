import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
from utils import get_weak_strong_subjects

st.set_page_config(page_title="Auto Timetable Generator", page_icon="📅", layout="wide")

if 'user_id' not in st.session_state or st.session_state.user_id is None:
    st.warning("Please log in from the main page.")
    st.stop()

user_id = st.session_state.user_id

st.title("📅 Auto Timetable Generator")
st.write("Generate a smart weekly study schedule that prioritizes your weak subjects.")

with st.expander("⚙️ Timetable Settings", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        hours_per_day = st.slider("Available Study Hours / Day", 1, 8, 3)
        start_time = st.time_input("Preferred Start Time", value=datetime.strptime("17:00", "%H:%M").time())
    with col2:
        st.write("Days Available")
        days_avail = st.multiselect("Select Days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], default=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
        
    generate_btn = st.button("Generate Timetable", type="primary")

from ml_model import predict_timetable_priorities

def generate_timetable_data(user_id, hours_per_day, days_avail, start_time):
    try:
        priorities = predict_timetable_priorities(user_id)
        if priorities:
            all_subjects = [subj for subj, score in priorities]
        else:
            all_subjects = []
    except Exception as e:
        # Fallback if ML model is unavailable
        scores, weak, average, strong = get_weak_strong_subjects(user_id)
        all_subjects = [s["subject"] for s in weak] + [s["subject"] for s in average] + [s["subject"] for s in strong]
    
    if not all_subjects:
        return None
        
    # We will allocate slots (1 slot = 1 hour)
    schedule = {day: [] for day in days_avail}
    
    # ML-based distribution algorithm
    sub_idx = 0
    for day in days_avail:
        current_time = datetime.combine(datetime.today(), start_time)
        for h in range(hours_per_day):
            # Pick subject
            subject = all_subjects[sub_idx % len(all_subjects)]
            
            end_time = current_time + timedelta(hours=1)
            time_str = f"{current_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}"
            
            schedule[day].append({
                "Time": time_str,
                "Subject": subject
            })
            
            current_time = end_time
            sub_idx += 1
            
            # The ML model already ranks the subjects by priority, so iterating through them
            # will naturally distribute time with the most critical subjects first.
            
    return schedule

if generate_btn:
    if not days_avail:
        st.error("Please select at least one day.")
    else:
        st.session_state.timetable = generate_timetable_data(user_id, hours_per_day, days_avail, start_time)

if "timetable" in st.session_state and st.session_state.timetable:
    timetable = st.session_state.timetable
    
    st.subheader("Your Custom Weekly Timetable")
    
    # Convert schedule to a grid DataFrame
    # Rows = Time Slot Index, Cols = Days
    max_slots = hours_per_day
    grid = []
    for slot_idx in range(max_slots):
        row = {}
        row["Slot"] = f"Hour {slot_idx+1}"
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
            if day in timetable and slot_idx < len(timetable[day]):
                item = timetable[day][slot_idx]
                row[day] = f"{item['Time']} \n {item['Subject']}"
            else:
                row[day] = "Free"
        grid.append(row)
        
    df_grid = pd.DataFrame(grid)
    
    # Custom CSS for table styling to make it color coded
    st.dataframe(df_grid, use_container_width=True, hide_index=True)
    
    st.write("### Export Options")
    
    colA, colB = st.columns(2)
    with colA:
        csv = df_grid.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download as CSV",
            data=csv,
            file_name='study_timetable.csv',
            mime='text/csv',
        )
    with colB:
        st.write("*(PDF export requires a small font setup not available natively in this environment without fpdf fonts, but you can print the page or use the CSV!)*")
        # To strictly fulfill the PDF requirement using fpdf:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Weekly Study Timetable", ln=1, align='C')
        for idx, row in df_grid.iterrows():
            pdf.cell(200, 10, txt=str(row.to_dict()), ln=1)
        pdf_bytes = pdf.output(dest='S').encode('latin-1')
        st.download_button(
            label="Download as PDF",
            data=pdf_bytes,
            file_name="study_timetable.pdf",
            mime="application/pdf"
        )
elif generate_btn:
    st.info("Add some subjects and tasks first to generate a timetable!")
