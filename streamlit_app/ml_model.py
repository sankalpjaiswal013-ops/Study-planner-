"""
ml_model.py

Student Performance Prediction module for StudyPlanner

Features:
- Load and aggregate data from SQLite (via existing database.py helpers)
- Build training features (study hours, completed tasks, difficulty, pomodoro sessions)
- Create a target `performance_score` (use DB label if present, else synthetic)
- Train a scikit-learn model (RandomForestRegressor or LinearRegression)
- Save / load model with joblib
- Provide prediction helpers for Streamlit integration
- Plotly visualizations for predictions and feature importances

This file is written to be beginner-friendly and production-ready with
clear comments and safe handling of missing data.
"""

import os
import sqlite3
import json
from typing import Tuple, List, Dict, Optional

import pandas as pd
import numpy as np
import joblib
import plotly.express as px
import plotly.graph_objects as go

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_squared_error, r2_score
from logger import logger

# Import the project's DB helper (assumes streamlit_app/database.py exists)
try:
    from database import get_db_connection, DB_NAME
except Exception:
    # Fallback in case imports differ; attempt to create a local connection helper
    DB_NAME = os.environ.get("DATABASE_PATH", "tasks.db")

    def get_db_connection():
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn


# Where trained models will be stored
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, "student_performance.joblib")
TIMETABLE_MODEL_PATH = os.path.join(MODEL_DIR, "timetable_model.joblib")


def _map_difficulty(val: Optional[str]) -> float:
    """Map textual difficulty to numeric scale.

    If val is already numeric (string digits), convert to float.
    Unknown values map to the median scale (2.0).
    """
    if val is None:
        return 2.0
    try:
        # handle numeric strings
        return float(val)
    except Exception:
        pass
    v = str(val).strip().lower()
    if v in ("easy", "e", "1"):
        return 1.0
    if v in ("medium", "med", "m", "2"):
        return 2.0
    if v in ("hard", "h", "3"):
        return 3.0
    return 2.0


def load_and_aggregate_data(min_rows=30) -> pd.DataFrame:
    """Load data from SQLite and aggregate per user to produce training rows.

    The function creates these features per `user_id`:
    - total_study_hours: sum of study_log.hours_studied
    - completed_tasks: count of tasks where completed=1
    - avg_task_difficulty: numeric mapping of task difficulty
    - pomodoro_count: count of pomodoro_sessions
    - avg_pomodoro_mins: average duration_mins of pomodoro sessions

    If the DB has fewer than `min_rows` users, synthetic samples are generated
    to allow model training. Returns a DataFrame ready for modeling.
    """
    conn = get_db_connection()

    # Read tables into pandas DataFrames (safe if tables are missing)
    try:
        tasks = pd.read_sql_query("SELECT * FROM tasks", conn)
    except Exception:
        tasks = pd.DataFrame()
    try:
        study_log = pd.read_sql_query("SELECT * FROM study_log", conn)
    except Exception:
        study_log = pd.DataFrame()
    try:
        pomodoro = pd.read_sql_query("SELECT * FROM pomodoro_sessions", conn)
    except Exception:
        pomodoro = pd.DataFrame()
    try:
        users = pd.read_sql_query("SELECT id as user_id FROM users", conn)
    except Exception:
        users = pd.DataFrame()

    conn.close()

    # Start building per-user aggregates
    users_list = users["user_id"].unique().tolist() if not users.empty else []

    rows = []
    for uid in users_list:
        row = {"user_id": int(uid)}

        # Study hours
        if not study_log.empty:
            sub = study_log[study_log["user_id"] == uid]
            row["total_study_hours"] = float(sub["hours_studied"].sum()) if not sub.empty else 0.0
        else:
            row["total_study_hours"] = 0.0

        # Tasks
        if not tasks.empty:
            tsub = tasks[tasks["user_id"] == uid]
            row["completed_tasks"] = int(tsub[tsub["completed"] == 1].shape[0]) if "completed" in tsub.columns else int(tsub.shape[0])
            if not tsub.empty and "difficulty" in tsub.columns:
                row["avg_task_difficulty"] = float(tsub["difficulty"].map(_map_difficulty).mean())
            else:
                row["avg_task_difficulty"] = 2.0
        else:
            row["completed_tasks"] = 0
            row["avg_task_difficulty"] = 2.0

        # Pomodoro
        if not pomodoro.empty:
            psub = pomodoro[pomodoro["user_id"] == uid]
            row["pomodoro_count"] = int(psub.shape[0])
            row["avg_pomodoro_mins"] = float(psub["duration_mins"].mean()) if not psub.empty and "duration_mins" in psub.columns else 0.0
        else:
            row["pomodoro_count"] = 0
            row["avg_pomodoro_mins"] = 0.0

        rows.append(row)

    df = pd.DataFrame(rows)

    # If there are no users in DB, create synthetic sample users
    if df.empty:
        df = _create_sample_data(n=50)

    # If too few rows, augment with synthetic samples
    if df.shape[0] < min_rows:
        extra = _create_sample_data(n=(min_rows - df.shape[0]))
        df = pd.concat([df, extra], ignore_index=True)

    # Ensure numeric types and handle missing
    numeric_cols = ["total_study_hours", "completed_tasks", "avg_task_difficulty", "pomodoro_count", "avg_pomodoro_mins"]
    for col in numeric_cols:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())

    # Create a performance target if none exists in the DB
    if "performance_score" not in df.columns:
        df["performance_score"] = df.apply(_create_synthetic_performance_score, axis=1)

    return df


def _create_synthetic_performance_score(row: pd.Series) -> float:
    """Create a synthetic performance score (0-100) from features.

    This heuristic is used only when the DB doesn't contain labeled targets.
    It combines normalized features with simple weights.
    """
    # normalize components
    study = row.get("total_study_hours", 0.0)
    completed = row.get("completed_tasks", 0.0)
    difficulty = row.get("avg_task_difficulty", 2.0)
    pomos = row.get("pomodoro_count", 0.0)

    # Basic heuristic: more study hours and completed tasks increases score,
    # higher difficulty slightly reduces raw score (harder courses).
    score = (study * 4.0) + (completed * 6.0) + (pomos * 1.5) - (difficulty * 3.0)

    # scale roughly into 0-100 and bound
    score = max(0.0, score)
    score = min(100.0, score)
    return round(score, 2)


def _create_sample_data(n=50) -> pd.DataFrame:
    """Generate synthetic users for training when DB data is insufficient.

    Returns DataFrame with same columns as production aggregate.
    """
    rng = np.random.default_rng(seed=42)
    data = {
        "user_id": [1000 + i for i in range(n)],
        "total_study_hours": rng.normal(loc=20, scale=10, size=n).clip(0, None),
        "completed_tasks": rng.integers(0, 50, size=n),
        "avg_task_difficulty": rng.integers(1, 4, size=n),
        "pomodoro_count": rng.integers(0, 100, size=n),
        "avg_pomodoro_mins": rng.normal(loc=25, scale=5, size=n).clip(5, 60),
    }
    df = pd.DataFrame(data)
    df["performance_score"] = df.apply(_create_synthetic_performance_score, axis=1)
    return df


def train_and_save_model(df: Optional[pd.DataFrame] = None, model_type: str = "rf", save_path: str = MODEL_PATH) -> Dict:
    """Train a model and save it to disk.

    Parameters:
    - df: DataFrame with feature columns and `performance_score` target. If None, data will be loaded.
    - model_type: "rf" for RandomForestRegressor or "lin" for LinearRegression
    - save_path: where to save the joblib file

    Returns a dict with model path and evaluation metrics.
    """
    if df is None:
        df = load_and_aggregate_data()

    features = ["total_study_hours", "completed_tasks", "avg_task_difficulty", "pomodoro_count", "avg_pomodoro_mins"]
    X = df[features].values
    # Ensure target has no NaNs: fill any missing performance_score with synthetic values
    if df["performance_score"].isnull().any():
        df.loc[df["performance_score"].isnull(), "performance_score"] = df.loc[df["performance_score"].isnull()].apply(_create_synthetic_performance_score, axis=1)
    y = df["performance_score"].values

    # Simple pipeline: impute missing values and scale
    pipeline_steps = [
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ]

    if model_type == "rf":
        model = RandomForestRegressor(n_estimators=100, random_state=42)
    else:
        model = LinearRegression()

    pipeline_steps.append(("model", model))
    pipe = Pipeline(pipeline_steps)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    logger.info(f"Training model type={model_type} rows={len(X_train)}")
    pipe.fit(X_train, y_train)
    preds = pipe.predict(X_test)

    mse = mean_squared_error(y_test, preds)
    rmse = float(np.sqrt(mse))
    metrics = {
        "rmse": rmse,
        "r2": float(r2_score(y_test, preds)),
    }

    # Save pipeline (includes preprocessing and model)
    joblib.dump(pipe, save_path)
    logger.info(json.dumps({"event": "model_trained", "model_path": save_path, "metrics": metrics}))

    return {"model_path": save_path, "metrics": metrics}


def load_model(path: Optional[str] = None):
    """Load a saved model pipeline from disk."""
    path = path or MODEL_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model not found at {path}. Train the model first.")
    return joblib.load(path)


def _user_feature_row(user_id: int) -> pd.DataFrame:
    """Compute feature row for a single user_id from DB (same schema as training).

    Returns a single-row DataFrame.
    """
    conn = get_db_connection()
    try:
        tasks = pd.read_sql_query("SELECT * FROM tasks WHERE user_id=?", conn, params=(user_id,))
    except Exception:
        tasks = pd.DataFrame()
    try:
        study_log = pd.read_sql_query("SELECT * FROM study_log WHERE user_id=?", conn, params=(user_id,))
    except Exception:
        study_log = pd.DataFrame()
    try:
        pomodoro = pd.read_sql_query("SELECT * FROM pomodoro_sessions WHERE user_id=?", conn, params=(user_id,))
    except Exception:
        pomodoro = pd.DataFrame()
    conn.close()

    total_study_hours = float(study_log["hours_studied"].sum()) if not study_log.empty else 0.0
    completed_tasks = int(tasks[tasks.get("completed", 0) == 1].shape[0]) if not tasks.empty else 0
    avg_task_difficulty = float(tasks["difficulty"].map(_map_difficulty).mean()) if (not tasks.empty and "difficulty" in tasks.columns) else 2.0
    pomodoro_count = int(pomodoro.shape[0]) if not pomodoro.empty else 0
    avg_pomodoro_mins = float(pomodoro["duration_mins"].mean()) if (not pomodoro.empty and "duration_mins" in pomodoro.columns) else 0.0

    row = pd.DataFrame([
        {
            "user_id": int(user_id),
            "total_study_hours": total_study_hours,
            "completed_tasks": completed_tasks,
            "avg_task_difficulty": avg_task_difficulty,
            "pomodoro_count": pomodoro_count,
            "avg_pomodoro_mins": avg_pomodoro_mins,
        }
    ])
    return row


def predict_student_performance(user_id: int, model_path: Optional[str] = None) -> Dict:
    """Predict the student's performance percentage and recommended study hours.

    Returns a dict with keys:
    - predicted_performance: float (0-100)
    - recommended_weekly_hours: float (suggested additional hours)
    - features: dict of the student's current features
    """
    model = load_model(model_path) if model_path else load_model()

    row = _user_feature_row(user_id)
    features = ["total_study_hours", "completed_tasks", "avg_task_difficulty", "pomodoro_count", "avg_pomodoro_mins"]
    X = row[features].values
    pred = model.predict(X)[0]

    # Bound prediction
    pred = float(max(0.0, min(100.0, pred)))

    # Simple recommendation: gap to a target score (e.g., 75) translated to hours
    target = 75.0
    gap = max(0.0, target - pred)
    # heuristic: each additional study hour increases score by ~1.5 points (tunable)
    recommended_hours = round(gap / 1.5, 1)

    return {
        "predicted_performance": round(pred, 2),
        "recommended_weekly_hours": recommended_hours,
        "features": row.iloc[0].to_dict(),
    }


def predict_weak_subjects(user_id: int, top_n: int = 3) -> List[Tuple[str, float]]:
    """Return a ranked list of weak subjects for the student.

    The function computes a simple risk score per subject based on:
    - low study hours for the subject
    - high average task difficulty in that subject
    - number of incomplete tasks for the subject

    Returns a list of tuples: (subject, risk_score) ordered descending by risk.
    """
    conn = get_db_connection()
    try:
        study_log = pd.read_sql_query("SELECT subject, hours_studied FROM study_log WHERE user_id=?", conn, params=(user_id,))
    except Exception:
        study_log = pd.DataFrame()
    try:
        tasks = pd.read_sql_query("SELECT subject, difficulty, completed FROM tasks WHERE user_id=?", conn, params=(user_id,))
    except Exception:
        tasks = pd.DataFrame()
    conn.close()

    subjects = set()
    if not study_log.empty:
        subjects.update(study_log["subject"].dropna().unique().tolist())
    if not tasks.empty:
        subjects.update(tasks["subject"].dropna().unique().tolist())

    if not subjects:
        return []

    risks = []
    for subj in subjects:
        hours = float(study_log[study_log["subject"] == subj]["hours_studied"].sum()) if not study_log.empty else 0.0
        tsub = tasks[tasks["subject"] == subj] if not tasks.empty else pd.DataFrame()
        avg_diff = float(tsub["difficulty"].map(_map_difficulty).mean()) if not tsub.empty and "difficulty" in tsub.columns else 2.0
        incomplete = int(tsub[tsub.get("completed", 0) == 0].shape[0]) if not tsub.empty else 0

        # risk increases with difficulty & incomplete tasks, decreases with hours
        risk = (avg_diff * 2.0) + (incomplete * 1.5) - (hours * 0.5)
        risk = max(0.0, risk)
        risks.append((subj, round(risk, 2)))

    risks.sort(key=lambda x: x[1], reverse=True)
    return risks[:top_n]


def plot_feature_importances(model_path: Optional[str] = None) -> go.Figure:
    """Return a Plotly bar chart of feature importances (works for tree models)."""
    model = load_model(model_path)
    # try to extract feature importances
    try:
        importances = model.named_steps["model"].feature_importances_
    except Exception:
        # Not available for linear models; fall back to coefficients
        try:
            coef = model.named_steps["model"].coef_
            importances = np.abs(coef)
        except Exception:
            raise RuntimeError("Model does not expose importances or coefficients")

    feature_names = ["total_study_hours", "completed_tasks", "avg_task_difficulty", "pomodoro_count", "avg_pomodoro_mins"]
    df = pd.DataFrame({"feature": feature_names, "importance": importances})
    df = df.sort_values("importance", ascending=False)
    fig = px.bar(df, x="feature", y="importance", title="Feature Importances")
    return fig


def plot_student_history(user_id: int) -> go.Figure:
    """Plot study hours over time for a student using Plotly."""
    conn = get_db_connection()
    try:
        study_log = pd.read_sql_query("SELECT date, hours_studied FROM study_log WHERE user_id=? ORDER BY date", conn, params=(user_id,))
    except Exception:
        study_log = pd.DataFrame()
    conn.close()

    if study_log.empty:
        # return an empty figure with a message
        fig = px.line(title="No study history available")
        return fig

    study_log["date"] = pd.to_datetime(study_log["date"])
    fig = px.line(study_log, x="date", y="hours_studied", title="Study Hours Over Time")
    return fig


# --- TIMETABLE ML MODEL ---

def _create_synthetic_timetable_target(row: pd.Series) -> float:
    """Create a target priority score for the timetable model."""
    difficulty = row.get("avg_difficulty", 2.0)
    incomplete = row.get("incomplete_tasks", 0.0)
    hours = row.get("hours_studied", 0.0)
    pomodoros = row.get("pomodoros", 0.0)
    
    # High difficulty and lots of incomplete tasks increase priority.
    # More hours studied and pomodoros completed decrease priority.
    score = (difficulty * 10) + (incomplete * 5) - (hours * 2.5) - (pomodoros * 1.5)
    return max(0.0, score)

def train_timetable_model(save_path: str = TIMETABLE_MODEL_PATH) -> Dict:
    """Train a model to predict subject priority for timetables based on study activity."""
    conn = get_db_connection()
    try:
        tasks = pd.read_sql_query("SELECT user_id, subject, difficulty, completed FROM tasks", conn)
        study_log = pd.read_sql_query("SELECT user_id, subject, hours_studied FROM study_log", conn)
        pomodoro = pd.read_sql_query("SELECT user_id, subject FROM pomodoro_sessions", conn)
    except Exception:
        tasks = pd.DataFrame()
        study_log = pd.DataFrame()
        pomodoro = pd.DataFrame()
    finally:
        conn.close()

    # If no data at all, generate synthetic data to bootstrap the model
    rows = []
    if not tasks.empty:
        # Group by user and subject
        for (uid, subj), t_group in tasks.groupby(["user_id", "subject"]):
            diff_mean = t_group["difficulty"].map(_map_difficulty).mean()
            incomplete = t_group[t_group.get("completed", 0) == 0].shape[0]
            
            hours = 0.0
            if not study_log.empty:
                s_group = study_log[(study_log["user_id"] == uid) & (study_log["subject"] == subj)]
                hours = float(s_group["hours_studied"].sum()) if not s_group.empty else 0.0
                
            pomos = 0
            if not pomodoro.empty:
                p_group = pomodoro[(pomodoro["user_id"] == uid) & (pomodoro["subject"] == subj)]
                pomos = int(p_group.shape[0]) if not p_group.empty else 0
                
            rows.append({
                "avg_difficulty": float(diff_mean),
                "incomplete_tasks": float(incomplete),
                "hours_studied": hours,
                "pomodoros": float(pomos)
            })

    df = pd.DataFrame(rows)
    
    # Bootstrap with synthetic data if sparse
    if df.shape[0] < 30:
        rng = np.random.default_rng(seed=42)
        n_extra = 50
        extra_data = {
            "avg_difficulty": rng.uniform(1.0, 3.0, size=n_extra),
            "incomplete_tasks": rng.integers(0, 10, size=n_extra).astype(float),
            "hours_studied": rng.exponential(scale=5.0, size=n_extra),
            "pomodoros": rng.integers(0, 20, size=n_extra).astype(float)
        }
        df = pd.concat([df, pd.DataFrame(extra_data)], ignore_index=True)

    df["priority_score"] = df.apply(_create_synthetic_timetable_target, axis=1)

    features = ["avg_difficulty", "incomplete_tasks", "hours_studied", "pomodoros"]
    X = df[features].values
    y = df["priority_score"].values

    pipeline_steps = [
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", RandomForestRegressor(n_estimators=50, random_state=42))
    ]
    pipe = Pipeline(pipeline_steps)
    pipe.fit(X, y)

    joblib.dump(pipe, save_path)
    logger.info(f"Timetable ML model trained and saved to {save_path}")
    return {"model_path": save_path, "status": "success", "samples": len(df)}

def predict_timetable_priorities(user_id: int, model_path: Optional[str] = None) -> List[Tuple[str, float]]:
    """Use the ML model to predict subject priority scores for the user."""
    path = model_path or TIMETABLE_MODEL_PATH
    if not os.path.exists(path):
        # Auto-train if not found
        train_timetable_model(path)
    
    model = joblib.load(path)
    
    # Gather user's current subject stats
    conn = get_db_connection()
    try:
        tasks = pd.read_sql_query("SELECT subject, difficulty, completed FROM tasks WHERE user_id=?", conn, params=(user_id,))
        study_log = pd.read_sql_query("SELECT subject, hours_studied FROM study_log WHERE user_id=?", conn, params=(user_id,))
        pomodoro = pd.read_sql_query("SELECT subject FROM pomodoro_sessions WHERE user_id=?", conn, params=(user_id,))
    except Exception:
        tasks = pd.DataFrame()
        study_log = pd.DataFrame()
        pomodoro = pd.DataFrame()
    finally:
        conn.close()

    subjects = set()
    if not tasks.empty: subjects.update(tasks["subject"].dropna().unique().tolist())
    if not study_log.empty: subjects.update(study_log["subject"].dropna().unique().tolist())
    
    if not subjects:
        return []

    rows = []
    subject_list = list(subjects)
    for subj in subject_list:
        diff_mean = 2.0
        incomplete = 0.0
        hours = 0.0
        pomos = 0.0
        
        if not tasks.empty:
            tsub = tasks[tasks["subject"] == subj]
            if not tsub.empty:
                diff_mean = float(tsub["difficulty"].map(_map_difficulty).mean())
                incomplete = float(tsub[tsub.get("completed", 0) == 0].shape[0])
                
        if not study_log.empty:
            ssub = study_log[study_log["subject"] == subj]
            if not ssub.empty:
                hours = float(ssub["hours_studied"].sum())
                
        if not pomodoro.empty:
            psub = pomodoro[pomodoro["subject"] == subj]
            pomos = float(psub.shape[0])
            
        rows.append({
            "avg_difficulty": diff_mean,
            "incomplete_tasks": incomplete,
            "hours_studied": hours,
            "pomodoros": pomos
        })
        
    df = pd.DataFrame(rows)
    features = ["avg_difficulty", "incomplete_tasks", "hours_studied", "pomodoros"]
    
    # Predict priorities
    preds = model.predict(df[features].values)
    
    # Combine with subjects and sort descending
    results = list(zip(subject_list, preds))
    results.sort(key=lambda x: x[1], reverse=True)
    return results


if __name__ == "__main__":
    # When run as a script, train and save a model and print metrics
    print("Loading data and training main performance model...")
    df = load_and_aggregate_data()
    result = train_and_save_model(df, model_type="rf")
    print("Trained performance model saved to:", result["model_path"]) 
    print("Metrics:", result["metrics"])
    
    print("\nTraining ML timetable model...")
    tt_result = train_timetable_model()
    print("Trained timetable model saved to:", tt_result["model_path"])
    print("Samples used:", tt_result["samples"])
