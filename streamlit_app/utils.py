import datetime
from database import get_db_connection

def get_streak(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT date FROM study_log WHERE user_id=? ORDER BY date DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        return 0
    
    streak = 0
    current_date = datetime.date.today()
    
    for row in rows:
        log_date = datetime.datetime.strptime(row["date"], "%Y-%m-%d").date()
        if log_date == current_date:
            streak += 1
            current_date -= datetime.timedelta(days=1)
        elif log_date == current_date - datetime.timedelta(days=1):
            # missed today, but studied yesterday (streak still active but not incremented yet)
            streak += 1
            current_date = log_date - datetime.timedelta(days=1)
        else:
            break
            
    return streak

def calculate_subject_score(user_id, subject):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT difficulty, completed FROM tasks WHERE user_id=? AND subject=?", (user_id, subject))
    tasks = c.fetchall()
    conn.close()
    
    if not tasks:
        return 0
        
    total_weight = 0
    completed_weight = 0
    
    weight_map = {"Easy": 1, "Medium": 2, "Hard": 3}
    
    for t in tasks:
        w = weight_map.get(t["difficulty"], 1)
        total_weight += w
        if t["completed"]:
            completed_weight += w
            
    if total_weight == 0:
        return 0
    
    return round((completed_weight / total_weight) * 100)

def get_weak_strong_subjects(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT subject FROM tasks WHERE user_id=?", (user_id,))
    subjects = [r["subject"] for r in c.fetchall()]
    conn.close()
    
    scores = []
    for s in subjects:
        score = calculate_subject_score(user_id, s)
        scores.append({"subject": s, "score": score})
        
    scores.sort(key=lambda x: x["score"])
    
    # Classify
    weak = [s for s in scores if s["score"] < 40]
    average = [s for s in scores if 40 <= s["score"] <= 70]
    strong = [s for s in scores if s["score"] > 70]
    
    return scores, weak, average, strong

def get_today_study_hours(user_id):
    today = datetime.date.today().strftime("%Y-%m-%d")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT SUM(hours_studied) as total FROM study_log WHERE user_id=? AND date=?", (user_id, today))
    row = c.fetchone()
    conn.close()
    return row["total"] if row and row["total"] else 0.0
