Deployment notes — Render and Docker

Render (recommended for persistent disk):

- Connect your GitHub repo to Render and create a new **Web Service**.
- Set the build command:
  pip install -r streamlit_app/requirements.txt
- Set the start command:
  streamlit run streamlit_app/app.py --server.port $PORT --server.address 0.0.0.0
- Add a Persistent Disk in Render and mount it at `/data`.
- Add environment variable in Render:
  - `DATABASE_PATH` = `/data/tasks.db`
- (Optional) Add other env vars such as `OPENAI_API_KEY`.

Docker (local / other providers):

Build and run locally:

```bash
docker build -t studyplanner:latest -f streamlit_app/Dockerfile .
docker run -p 8501:8501 -e PORT=8501 -e DATABASE_PATH=/data/tasks.db -v $(pwd)/data:/data studyplanner:latest
```

Notes:
- The app reads `DATABASE_PATH` env var (defaults to `tasks.db`).
- For production, use a managed Postgres/Cloud SQL and update code to use that instead of SQLite for scaling.
# 🧠 AI-Powered Study Planner

[![CI](https://github.com/<your-org>/<your-repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<your-org>/<your-repo>/actions/workflows/ci.yml)

## Quick start

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the app:

```powershell
py -3 -m streamlit run app.py
```

## Fast local build (Docker)

If you have Docker and BuildKit available, use the provided optimized Dockerfile and build script to build faster with cached wheels:

PowerShell (recommended on Windows):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\build_image.ps1 -Tag studyplanner:latest -UseBuildKit
# then run:
docker run -p 8501:8501 -e PORT=8501 studyplanner:latest
```

The script uses `streamlit_app/Dockerfile.prod`, which builds wheels in a separate stage so subsequent rebuilds are much faster.

## Makefile (quick commands)

A small `Makefile` is included with convenient targets for Windows PowerShell users. From the `streamlit_app` folder run:

```powershell
make install      # create venv and install requirements
make run          # run the app locally
make build-image  # build optimized Docker image (uses build_image.ps1)
make docker-run   # run the built docker image
make test         # run pytest
```

On Windows, `make` can be provided by Chocolatey (`choco install make`) or by installing GNU Make via MSYS2. Alternatively run the commands directly from PowerShell as shown earlier.


A comprehensive, full-featured Study Planner web application built completely in Python using **Streamlit**, **SQLite**, and **Google Gemini AI**.

This application acts as a personal tutor and organization hub, helping students track tasks, identify weak subjects, generate automated study timetables, and maintain focus using a built-in Pomodoro timer.

## 🚀 Features

* **Smart Dashboard**: Visualizes your 14-day study streak, weekly hours, and subject distribution using interactive Plotly charts.
* **Task & Subject Manager**: Add homework, exams, and general study tasks. The app automatically calculates a "Subject Score" (0-100) based on your completion rate and the difficulty of the tasks.
* **Weakness Analysis**: Automatically identifies your top 3 weak subjects and top 3 strong subjects, displaying them in a color-coded bar chart.
* **AI Chatbot Tutor**: Powered by Google Gemini 2.5 Flash. The chatbot reads your local database context (weak subjects, pending tasks) to give you hyper-personalized study advice and motivation.
* **Auto Timetable Generator**: Input your available hours, and the app generates a weekly study grid that automatically prioritizes your weakest subjects.
* **Pomodoro Timer**: A fully built-in ticking timer (Work, Short Break, Long Break) that logs your completed focus sessions directly into your daily study analytics.
* **Secure Local Database**: All data is stored locally in an SQLite database (`tasks.db`), ensuring privacy and speed.

## 🛠️ Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/study-planner.git
   cd study-planner
   ```

2. **Install the required packages:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Get a free Google Gemini API Key:**
   * Go to [Google AI Studio](https://aistudio.google.com/app/apikey) and generate a free key.

4. **Run the application:**
   ```bash
   streamlit run app.py
   ```

5. **Configure the App:**
   * Open the app in your browser (usually `http://localhost:8501`).
   * Sign up for an account.
   * Go to the **Settings** page and paste your Google Gemini API key to activate the chatbot!

## 📦 Tech Stack
* **Frontend/Backend:** Streamlit (Python)
* **Database:** SQLite3
* **Charts:** Plotly Express
* **AI Integration:** Google Generative AI (Gemini)
* **Security:** bcrypt (Password Hashing)
