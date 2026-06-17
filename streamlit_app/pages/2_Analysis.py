import streamlit as st
import pandas as pd
import plotly.express as px
from database import get_db_connection
from utils import get_weak_strong_subjects

st.set_page_config(page_title="Subject Analysis", page_icon="📊", layout="wide")

if 'user_id' not in st.session_state or st.session_state.user_id is None:
    st.warning("Please log in from the main page.")
    st.stop()

user_id = st.session_state.user_id

st.title("📊 Subject Performance Analysis")

scores, weak, average, strong = get_weak_strong_subjects(user_id)

if not scores:
    st.info("No subjects found. Please add some tasks first.")
    st.stop()

# Build DataFrame for Plotly
df = pd.DataFrame(scores)

# Add color column based on score
def get_color(score):
    if score < 40:
        return 'red'
    elif score <= 70:
        return 'gold'
    else:
        return 'green'

df['color'] = df['score'].apply(get_color)

# Bar Chart
fig = px.bar(
    df, x='score', y='subject', orientation='h',
    title="Subject Strength (Score 0-100)",
    labels={'score': 'Performance Score', 'subject': 'Subject'},
    color='color',
    color_discrete_map={'red': '#EF4444', 'gold': '#EAB308', 'green': '#22C55E'}
)
fig.update_layout(showlegend=False)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# Top 3 / Bottom 3 Analysis
col1, col2 = st.columns(2)
with col1:
    st.error("📉 **Top 3 Weak Subjects** (Need Attention)")
    for s in weak[:3]:
        st.write(f"- **{s['subject']}**: {s['score']}/100")
    if not weak:
        st.write("None! You're doing great.")
        
with col2:
    st.success("📈 **Top 3 Strong Subjects** (Keep it up)")
    # strong list is already sorted by score (ascending), we want highest first
    for s in reversed(strong[-3:]):
        st.write(f"- **{s['subject']}**: {s['score']}/100")
    if not strong:
        st.write("None yet. Keep studying!")

st.divider()

# Summary Cards
st.subheader("Detailed Subject Breakdown")

conn = get_db_connection()
c = conn.cursor()

# We can display them in rows of 3
cols = st.columns(3)
for i, s in enumerate(scores):
    sub = s["subject"]
    score = s["score"]
    
    # Get pending hard tasks
    c.execute("SELECT COUNT(*) as cnt FROM tasks WHERE user_id=? AND subject=? AND completed=0 AND difficulty='Hard'", (user_id, sub))
    pending_hard = c.fetchone()["cnt"]
    
    status = "Weak 🔴" if score < 40 else "Average 🟡" if score <= 70 else "Strong 🟢"
    
    with cols[i % 3]:
        st.markdown(f"""
        <div style="background-color:#1E293B; padding:15px; border-radius:8px; margin-bottom:15px;">
            <h4>{sub}</h4>
            <p style="color:#94A3B8; margin:0;">Status: <b>{status}</b></p>
            <p style="color:#94A3B8; margin:0;">Score: <b>{score}/100</b></p>
            <p style="color:#EF4444; margin-top:5px; font-size:0.9em;">Pending Hard Tasks: {pending_hard}</p>
        </div>
        """, unsafe_allow_html=True)

conn.close()
