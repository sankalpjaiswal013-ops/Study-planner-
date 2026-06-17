"""
ai_helper.py

AI response generator for StudyPlanner.

Features:
- ML-first response strategy (local `ml_model` predictions)
- Fallback to Google GenAI SDK (new `google.genai`) when available
- Final fallback to a mock response
- Structured logging via `logger.py` with masking of secrets
- Streamed token-by-token output compatible with `st.write_stream`

The code is defensive and supports both old and new GenAI SDKs for
backwards compatibility; logs contain `prompt_hash`, `backend`, `duration`,
and masked API key information.
"""
import time
import json
import os
import hashlib
from datetime import datetime

# GenAI SDK (strict requirement). We defer import inside the caller to
# provide a clearer error message when attempting to call the API.


# ML helpers (optional)
try:
    from ml_model import predict_student_performance, predict_weak_subjects
    _HAS_ML = True
except Exception:
    _HAS_ML = False

from database import get_db_connection, get_setting
from utils import get_weak_strong_subjects
from logger import logger, mask_secret


def get_context_for_ai(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT subject, topic, difficulty, due_date FROM tasks WHERE user_id=? AND completed=0", (user_id,))
    pending = c.fetchall()
    conn.close()

    pending_list = [{"subject": p["subject"], "topic": p["topic"], "difficulty": p["difficulty"], "due": p["due_date"]} for p in pending]
    scores, weak, average, strong = get_weak_strong_subjects(user_id)

    context = f"""
    Today's Date: {datetime.now().strftime('%Y-%m-%d')}
    Pending Tasks: {json.dumps(pending_list)}
    Weak Subjects (Score < 40): {[w['subject'] for w in weak]}
    Strong Subjects (Score > 70): {[s['subject'] for s in strong]}
    """
    return context


def _call_genai_stream(api_key: str, final_prompt: str):
    """Invoke the installed GenAI SDK and return an iterator of text chunks.
    This function requires the new `google.genai` SDK. It prefers streaming
    generation APIs if available; otherwise falls back to synchronous
    `generate`. If the SDK is not installed, a RuntimeError is raised with
    an actionable message.
    """
    try:
        from google import genai as genai
    except Exception:
        raise RuntimeError("google.genai SDK not installed. Install `google-genai` and try again.")

    # many GenAI installs provide a `Client` class
    if hasattr(genai, "Client"):
        client = genai.Client(api_key=api_key)
        
        # New official google-genai SDK methods
        if hasattr(client, "models") and hasattr(client.models, "generate_content_stream"):
            for chunk in client.models.generate_content_stream(model="gemini-2.5-flash", contents=final_prompt):
                if chunk.text:
                    yield chunk.text
            return
            
        if hasattr(client, "stream_generate"):
            for chunk in client.stream_generate(model="gemini-2.5-flash", input=final_prompt):
                yield chunk if isinstance(chunk, str) else getattr(chunk, "text", "")
            return
        if hasattr(client, "generate"):
            resp = client.generate(model="gemini-2.5-flash", input=final_prompt)
            yield getattr(resp, "text", str(resp))
            return

    # top-level generate
    if hasattr(genai, "generate"):
        resp = genai.generate(model="gemini-2.5-flash", input=final_prompt)
        yield getattr(resp, "text", str(resp))
        return

    raise RuntimeError("Installed google.genai SDK doesn't expose a supported generate API")


def generate_ai_response(user_id, prompt, chat_history):
    """Primary entry: yields strings for streaming display.

    Strategy:
    1. Try local ML (for student-centered prompts)
    2. If ML unavailable or fails, and `use_api` allows + key present -> call GenAI
    3. Otherwise fallback to mock reply
    """
    api_key = get_setting(user_id, "gemini_api_key", None)
    env_use_api = os.environ.get("USE_API", "1").lower()
    env_allow = not (env_use_api in ("0", "false", "no"))
    user_use_api = get_setting(user_id, "use_api", None)
    use_api = env_allow if user_use_api is None else bool(user_use_api)

    context = get_context_for_ai(user_id)
    start_ts = time.time()
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]

    system_prompt = f"""You are a highly motivating AI Study Assistant tailored specifically for Sankalp Jaiswal, a B.Tech student in CSE (AI-ML) at DBS Global University. He is active as a Student Liaison/Coordinator for Departmental Clubs and Technical Outreach Lead for IITR E-Summit & Robotics Initiatives.
Use the following student context to give personalized, supportive academic coaching:
{context}
Address him as Sankalp. Keep responses concise, encouraging, and align advice with his AI-ML, robotics, and leadership aspirations when appropriate."""

    lower = prompt.lower()
    ml_triggers = ("analyze", "weak", "plan", "study today", "motivate", "summary", "performance")

    # 1) Local ML path
    if _HAS_ML and any(t in lower for t in ml_triggers):
        try:
            perf = predict_student_performance(user_id)
            weak = predict_weak_subjects(user_id)

            backend = "Local ML Model"
            # log metadata
            try:
                logger.info(json.dumps({"event": "ml_prepare", "user": user_id, "prompt_hash": prompt_hash, "pred": perf.get('predicted_performance')}))
            except Exception:
                pass

            # indicate backend to UI
            yield f"[backend:local] "

            if "analyze" in lower or "weak" in lower:
                if weak:
                    subj_list = ", ".join([s for s, _ in weak])
                    reply = f"Sankalp, after analyzing your B.Tech CSE (AI-ML) metrics, your predicted performance is {perf['predicted_performance']}%. Your weakest subjects are: {subj_list}. Focus on these areas using 1-2 structured Pomodoro focus sessions!"
                else:
                    reply = f"Hi Sankalp, I analyzed your AI-ML study metrics: your predicted performance is outstanding at {perf['predicted_performance']}%. No clear weak subjects detected. Keep following your current stellar plan!"
            elif "study today" in lower or "plan" in lower:
                hours = perf.get("recommended_weekly_hours", 0)
                reply = f"Today, Sankalp, focus on your high-difficulty tasks. I recommend adding {hours} study hours this week to consolidate your AI-ML B.Tech work, splitting them into focused Pomodoro sessions."
            elif "motivate" in lower:
                reply = f"Keep pushing boundaries, Sankalp! Integrating 1st Year B.Tech CSE (AI-ML) studies with your coordinator leadership at DBS Global and robotics outreach is highly challenging. You're predicted at {perf['predicted_performance']}%. Small, consistent wins compound—you got this!"
            else:
                reply = f"Quick summary for Sankalp: predicted performance {perf['predicted_performance']}%. Recommended weekly study hours: {perf['recommended_weekly_hours']}. Weak subjects: {', '.join([s for s,_ in weak]) if weak else 'None'}"

            for token in reply.split(" "):
                yield token + " "
                time.sleep(0.03)

            try:
                duration = time.time() - start_ts
                logger.info(json.dumps({"event": "ml_complete", "user": user_id, "prompt_hash": prompt_hash, "duration": duration}))
            except Exception:
                pass

            return
        except Exception as e:
            # ML failed: log and continue to API/mock fallback
            try:
                logger.exception("ml_error")
                logger.info(json.dumps({"event": "ml_error", "user": user_id, "prompt_hash": prompt_hash}))
            except Exception:
                pass
            yield f"[ML model error: {str(e)}] "

    # 2) API path
    if use_api and api_key:
        try:
            try:
                logger.info(json.dumps({"event": "api_call_start", "user": user_id, "prompt_hash": prompt_hash}))
            except Exception:
                pass

            # prepare final prompt
            formatted_history = ""
            for msg in chat_history:
                if msg.get("role") == "system":
                    continue
                role = "AI" if msg.get("role") == "assistant" else "User"
                formatted_history += f"{role}: {msg.get('content')}\n\n"

            final_prompt = f"INSTRUCTIONS: {system_prompt}\n\nPREVIOUS CHAT HISTORY:\n{formatted_history}\n\nUSER MESSAGE: {prompt}"

            # attempt to call available SDK
            gen = _call_genai_stream(api_key, final_prompt)
            header_yielded = False
            for chunk in gen:
                if chunk:
                    if not header_yielded:
                        yield f"[backend:gemini] "
                        header_yielded = True
                    yield chunk

            try:
                duration = time.time() - start_ts
                logger.info(json.dumps({"event": "api_call_end", "user": user_id, "prompt_hash": prompt_hash, "duration": duration}))
            except Exception:
                pass

            return
        except Exception as e:
            try:
                logger.exception("api_error")
                logger.info(json.dumps({"event": "api_error", "user": user_id, "prompt_hash": prompt_hash}))
            except Exception:
                pass

    # 3) Mock fallback
    time.sleep(0.8)
    if "analyze" in lower or "weak" in lower:
        reply = "Sankalp, based on your AI-ML studies at DBS Global University, I analyzed your tasks. Focus on your weakest topics (like Robotics or complex math) using a 25-minute Pomodoro session."
    elif "study today" in lower:
        reply = "As a B.Tech AI-ML student and Coordinator, you should prioritize your overdue technical coursework today. Start with a 25-minute Pomodoro on your hardest subject!"
    elif "plan" in lower:
        reply = "Here is your plan, Sankalp: 1) 25-min focus on your weakest AI-ML/Robotics topic, 2) 5-min break, 3) 25-min task on student coordinator outreach prep."
    elif "motivate" in lower:
        reply = "Keep pushing forward, Sankalp! Fusing AI-ML B.Tech studies with your leadership in E-Summit and Robotics is challenging, but these consistent wins will build immense momentum. You've got this!"
    else:
        reply = "Hey Sankalp! The AI backup is currently in fallback mode. Go to Settings to add your Gemini API key, or enjoy the local ML-based insights!"

    try:
        logger.info(json.dumps({"event": "mock_used", "user": user_id, "prompt_hash": prompt_hash}))
    except Exception:
        pass

    yield f"[backend:mock] "
    for token in reply.split(" "):
        yield token + " "
        time.sleep(0.03)
