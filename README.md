# HirePrep AI

HirePrep AI is a Flask-based interview preparation platform that helps candidates practice for real job interviews using resume-aware AI generation, a guided voice interview, a coding round, and a final performance dashboard.

The app combines:

- AI-generated interview questions tailored to a job role, job description, and resume
- A voice-practice round for spoken interview answers
- A coding round with local code execution and automated test validation
- A combined performance report with scores, charts, strengths, and recommendations

## Features

- Resume-aware interview generation from a PDF resume and job description
- Interview categories for technical, behavioral, situational, and system design practice
- Voice-friendly questions designed for spoken answers
- Coding challenges with support for locally available runtimes
- Code execution for Python, JavaScript, and Java
- Automated coding evaluation with test-case checks
- Lightweight code-quality feedback
- Combined performance dashboard after the practice flow
- Firebase-based authentication and Firestore-backed interview history

## Tech Stack

- Backend: Python, Flask, PyPDF2, python-dotenv
- Frontend: HTML, CSS, Vanilla JavaScript, Bootstrap 5, Chart.js
- AI: Google Gemini
- Auth and history: Firebase Authentication and Firestore
- Browser APIs: Web Speech API for speech synthesis and speech recognition

## Project Structure

```text
HirePrep_AI/
├── main.py
├── requirements.txt
├── README.md
├── tempCodeRunnerFile.py
├── static/
│   ├── performance_report.css
│   ├── performance_report.js
│   ├── script.js
│   └── style.css
└── templates/
    ├── auth.html
    ├── index.html
    └── performance_report.html
```

## Application Flow

1. The user signs in or creates an account through Firebase Authentication.
2. Flask stores the logged-in user details in the session.
3. The user uploads a PDF resume and pastes a job description.
4. The backend extracts resume text and sends a structured prompt to Gemini.
5. Gemini returns voice interview questions and, for technical rounds, coding challenges.
6. The user completes the voice round.
7. The user attempts the coding round in the browser editor.
8. The backend executes the code locally and checks it against test cases.
9. The app evaluates the full practice session and builds a performance report.
10. The final report is shown on the dashboard and stored in Firestore history.

## Key Files

- `main.py`: Flask app, Gemini integration, PDF parsing, route handlers, and code execution logic
- `templates/auth.html`: login, signup, and password reset screen
- `templates/index.html`: main interview workspace
- `templates/performance_report.html`: performance report page
- `static/script.js`: frontend interview flow, coding round logic, Firebase integration, and history loading
- `static/performance_report.js`: report rendering and charts
- `static/style.css`: main styling
- `static/performance_report.css`: report page styling

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd HirePrep_AI
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Git Bash:

```bash
python -m venv .venv
source .venv/Scripts/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a `.env` file

Example:

```env
GOOGLE_API_KEY=your_gemini_api_key
SECRET_KEY=your_flask_secret_key
FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}
# Optional alternative:
# FIREBASE_SERVICE_ACCOUNT_BASE64=base64_encoded_service_account_json
ALLOW_UNVERIFIED_FIREBASE_SESSION=false
SESSION_COOKIE_SECURE=true
GEMINI_TIMEOUT_SECONDS=90
GEMINI_MAX_RETRIES=2
```

## Environment Variables

- `GOOGLE_API_KEY`: required for Gemini API requests
- `SECRET_KEY`: Flask session secret
- `FIREBASE_SERVICE_ACCOUNT_JSON`: Firebase Admin service-account JSON used by Flask to verify login ID tokens and block unverified users
- `FIREBASE_SERVICE_ACCOUNT_BASE64`: optional base64-encoded Firebase service-account JSON; useful if a host has trouble with raw multiline JSON
- `FIREBASE_SERVICE_ACCOUNT`: optional local path to a Firebase service-account JSON file; use this instead of `FIREBASE_SERVICE_ACCOUNT_JSON` for local development if preferred
- `ALLOW_UNVERIFIED_FIREBASE_SESSION`: set to `false` on Render so users cannot bypass Firebase Admin verification
- `SESSION_COOKIE_SECURE`: set to `true` on Render so session cookies are sent only over HTTPS
- `GEMINI_TIMEOUT_SECONDS`: optional request timeout
- `GEMINI_MAX_RETRIES`: optional retry count for Gemini requests

## Render Deployment Notes

Set these environment variables in Render:

- `GOOGLE_API_KEY`
- `SECRET_KEY`
- `FIREBASE_SERVICE_ACCOUNT_JSON`
- `ALLOW_UNVERIFIED_FIREBASE_SESSION=false`
- `SESSION_COOKIE_SECURE=true`

To create `FIREBASE_SERVICE_ACCOUNT_JSON`, open Firebase Console, go to Project settings, Service accounts, generate a new private key, then paste the entire JSON content into Render as one environment variable. The app also accepts escaped `\n` characters in the private key. Do not add extra quotes around the value in Render; the app trims accidental wrapping quotes, but the cleanest value starts with `{` and ends with `}`.

If Render still fails to parse the raw JSON, use `FIREBASE_SERVICE_ACCOUNT_BASE64` instead:

```powershell
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Content .\serviceAccountKey.json -Raw)))
```

Set the output as `FIREBASE_SERVICE_ACCOUNT_BASE64` in Render, remove `FIREBASE_SERVICE_ACCOUNT_JSON`, then redeploy the service.

After deployment, check the Render logs for one of these lines:

```text
Firebase service account loaded from FIREBASE_SERVICE_ACCOUNT_JSON: project_id=..., client_email=...
Firebase service account loaded from FIREBASE_SERVICE_ACCOUNT_BASE64: project_id=..., client_email=...
Firebase admin initialized.
```

If those lines do not appear, Render is not passing the Firebase credential to the running service.

The production auth flow is:

1. A new user signs up with email and password.
2. Firebase sends an email verification link.
3. The app signs the user out immediately after signup.
4. Login is blocked until Firebase reports `emailVerified=true`.
5. Flask verifies the fresh Firebase ID token with Firebase Admin.
6. Verified users are redirected to `/dashboard`, which renders `index.html`.

## Optional Runtime Support

The coding round supports whichever runtimes are available on the machine:

- Python
- Node.js for JavaScript
- Java and `javac` for Java

If Node.js or Java are not installed, those language options are automatically hidden from the coding round.

## Running The App

Start the server with:

```bash
python main.py
```

Open the app at:

```text
http://127.0.0.1:5000
```

## Main Routes

- `GET /`: auth page
- `GET /auth`: auth alias
- `POST /set_session`: sync Firebase user info into Flask session
- `GET /dashboard`: main app dashboard
- `POST /generate`: generate interview questions and coding challenges
- `POST /run_code`: run coding submissions
- `POST /evaluate_practice`: build the combined practice report
- `GET /performance-report`: performance dashboard page
- `GET /performance-report-data`: returns report JSON
- `GET /logout`: log out and clear session
- `GET /switch-account`: return to auth flow

## Firebase Notes

Firebase configuration is currently defined in the frontend code:

- `templates/auth.html`
- `static/script.js`

If you want to use your own Firebase project, update the config objects in those files and enable:

- Email/Password Authentication
- Firestore

## Resume And Upload Rules

- Resume upload is required for generation
- Resume must be a PDF
- Maximum upload size is 5 MB

## Development Notes

- The app currently runs with `debug=True` in `main.py`
- The latest report is stored in the Flask session as `last_practice_report`
- Firestore stores previous interview sessions in the `interview_history` collection
- Voice functionality depends on browser support for speech APIs

## Known Limitations

- No automated test suite is included yet
- Firebase config is embedded in frontend files
- The app depends on external Gemini and Firebase services
- Generated content quality depends on the input resume, job description, and AI response quality

## Future Improvements

- Add automated backend tests
- Move Firebase config to a safer environment-driven setup
- Split `main.py` into smaller modules
- Add Docker support
- Add export options for performance reports

## License

Add your preferred license here, such as MIT.
