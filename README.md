# AI Interview Coach

AI Interview Coach is a Flask web app for practicing mock interviews end to end. It combines resume-aware question generation, a voice interview flow, a coding round with local execution, and a final performance report in one dashboard.

The current architecture uses:

- `Flask` for routing, server-side sessions, PDF parsing, prompt orchestration, and code execution
- `Gemini 2.5 Flash` over direct HTTP calls for interview generation and practice evaluation
- `Firebase Auth + Firestore` on the frontend for sign-in, account creation, and interview history
- Browser Web Speech APIs for question playback and speech recognition in the voice round

## Features

- Resume + job description based interview generation
- Voice-safe interview questions for spoken practice
- Built-in voice interview flow with browser text-to-speech
- Coding round with local execution for `Python`, `JavaScript`, and `Java` when runtimes are installed
- Combined practice report covering voice and coding performance
- Session history stored in Firestore
- Email/password authentication with password reset

## Project Structure

```text
.
|-- main.py
|-- requirements.txt
|-- uploads/
|-- instance/
|   `-- users.db
|-- static/
|   |-- script.js
|   |-- style.css
|   |-- performance_report.js
|   `-- performance_report.css
`-- templates/
    |-- auth.html
    |-- index.html
    `-- performance_report.html
```

## Architecture Overview

### 1. Authentication and session flow

- `templates/auth.html` handles login, signup, and password reset with Firebase Authentication.
- After login, the frontend posts the Firebase user identity to `POST /set_session`.
- Flask stores `user_id`, `user_name`, and `role` in the session and protects the dashboard/report routes.

### 2. Interview generation flow

- `templates/index.html` provides the main dashboard UI.
- `static/script.js` submits resume PDF + job description to `POST /generate`.
- `main.py` extracts PDF text with `PyPDF2`, infers likely programming languages from the resume/JD, and sends a structured prompt to Gemini.
- The backend normalizes the model response into:
  - `interview_questions`
  - `coding_challenges`

### 3. Voice interview flow

- The voice round is frontend-driven in `static/script.js`.
- Questions are spoken using `window.speechSynthesis`.
- Candidate answers can be typed or captured with browser speech recognition.
- The transcript is kept in client state until the full practice flow is evaluated.

### 4. Coding round flow

- Technical interviews may include one coding challenge.
- The challenge supports the locally available runtimes detected by the server.
- `POST /run_code` executes submissions in temporary files/processes and returns:
  - `stdout` / `stderr`
  - pass/fail against hidden test cases
  - acceptance result
  - lightweight code-quality feedback

### 5. Practice evaluation flow

- After the voice round and coding round, `static/script.js` sends the transcript and coding results to `POST /evaluate_practice`.
- `main.py` asks Gemini for a structured performance review.
- If model evaluation fails, the backend builds a deterministic fallback report.
- The final report is shown in `templates/performance_report.html` and can also be loaded from Firestore history.

## Backend Routes

- `GET /` and `GET /auth`: auth screen
- `POST /set_session`: sync Firebase identity to Flask session
- `GET /logout`: clear Flask session
- `GET /switch-account`: clear session and return to auth
- `GET /dashboard`: main application UI
- `POST /generate`: create interview questions and coding challenges
- `POST /run_code`: run candidate code against test cases
- `POST /evaluate_practice`: generate combined performance report
- `GET /performance-report`: report page
- `GET /performance-report-data`: fetch latest session report JSON

## Tech Stack

- Python
- Flask
- PyPDF2
- python-dotenv
- Firebase Authentication
- Firebase Firestore
- Gemini API
- Bootstrap 5
- Vanilla JavaScript

## Local Setup

### 1. Clone and install dependencies

```bash
git clone <your-repo-url>
cd Ai-Interview-Coach
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create `.env`

Add the following variables:

```env
GOOGLE_API_KEY=your_gemini_api_key
SECRET_KEY=your_flask_secret
GEMINI_TIMEOUT_SECONDS=90
GEMINI_MAX_RETRIES=2
```

### 3. Optional local runtimes for coding questions

Install any runtime you want the coding round to support:

- `Python`
- `Node.js`
- `Java JDK`

The backend automatically exposes only the languages available on the machine.

### 4. Run the app

```bash
python main.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Notes

- Resume upload currently requires a PDF file.
- Browser support matters for the voice round because speech playback and speech recognition depend on Web Speech APIs.
- Firebase client configuration is currently defined in the frontend templates/scripts.
- The repository includes a local `.venv/` in the working tree right now, but that folder is not part of the app architecture itself.

## Future Improvements

- Move Firebase config to environment-driven frontend config
- Add automated tests for prompt normalization and code runner behavior
- Split `main.py` into blueprints/services for easier maintenance
- Add Docker support and production deployment instructions
