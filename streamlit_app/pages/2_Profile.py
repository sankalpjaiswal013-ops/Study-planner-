import streamlit as st
import bcrypt
import sqlite3
from database import get_db_connection

st.set_page_config(page_title="Profile", page_icon="👤", layout="centered")

if 'user_id' not in st.session_state or st.session_state.user_id is None:
    st.warning("Please log in from the main page to access your profile.")
    st.stop()

user_id = st.session_state.user_id

st.title("User Profile 👤")

# Load current user details from tasks.db
conn = get_db_connection()
c = conn.cursor()
c.execute("SELECT name, email FROM users WHERE id=?", (user_id,))
user_row = c.fetchone()

if user_row:
    st.markdown("""
    <style>
        .profile-card {
            background-color: #1E293B;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-top: 5px solid #7c3aed;
            color: white;
        }
        .profile-info {
            font-size: 1.1rem;
            margin-bottom: 12px;
            color: #E2E8F0;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="profile-card">', unsafe_allow_html=True)
    
    st.markdown(f'<div class="profile-info">👤 <b>Name:</b> {user_row["name"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="profile-info">📧 <b>Email:</b> {user_row["email"]}</div>', unsafe_allow_html=True)
    
    st.divider()
    
    st.subheader("📝 Edit Profile Details")
    with st.form("edit_profile"):
        new_name = st.text_input("Full Name", value=user_row["name"])
        new_password = st.text_input("New Password", type="password", help="Leave blank to keep current password")
        
        if st.form_submit_button("Save Changes", type="primary"):
            if not new_name or not new_name.strip():
                st.error("Name cannot be empty!")
            else:
                try:
                    name_stripped = new_name.strip()
                    if new_password:
                        # Hash new password
                        salt = bcrypt.gensalt()
                        pwd_hash = bcrypt.hashpw(new_password.encode("utf-8"), salt).decode("utf-8")
                        c.execute("UPDATE users SET name=?, password_hash=? WHERE id=?", (name_stripped, pwd_hash, user_id))
                    else:
                        c.execute("UPDATE users SET name=? WHERE id=?", (name_stripped, user_id))
                    
                    conn.commit()
                    st.session_state.user_name = name_stripped
                    st.success("Profile updated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving profile: {e}")
                finally:
                    conn.close()
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.error("User not found.")
    conn.close()
