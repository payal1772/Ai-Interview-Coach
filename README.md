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

AI Interview Coach is a Flask-based interview practice platform that helps candidates prepare with AI-generated mock interviews tailored to their resume and a target job description. It combines three core experiences in one workflow:

- AI-generated interview questions with sample ideal answers
- A voice-style mock interview round
- A coding round with local code execution and automated evaluation

After the practice flow is complete, the app generates a combined performance dashboard covering communication, technical ability, confidence, problem solving, and code quality.

## What The App Does

The application uses:

- Flask for backend routes, sessions, and template rendering
- Gemini API for interview and report generation
- Firebase Authentication for sign-up, sign-in, and password reset
- Firestore for storing past interview session history
- PyPDF2 for extracting resume content from uploaded PDF files
- Browser speech APIs for spoken interview practice
- Local runtimes for executing coding submissions in Python, JavaScript, and Java

## Main Features

- Resume-aware interview generation using a PDF resume and job description
- Multiple interview categories:
  - Technical
  - Behavioral
  - Situational
  - System Design
- Voice-friendly questions designed for spoken answers instead of live coding prompts
- Coding challenge generation for technical rounds
- Multi-language coding support:
  - Python
  - JavaScript
  - Java
- Local code execution with test-case validation
- Lightweight code quality feedback
- Combined performance report with:
  - Score cards
  - Charts
  - Strengths
  - Improvement areas
  - Next-step recommendations
- Session history stored in Firestore for previously completed interview attempts


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
=======
HirePrep_AI/
├── main.py
├── requirements.txt
├── README.md
├── static/
│   ├── style.css
│   ├── script.js
│   ├── performance_report.css
│   └── performance_report.js
└── templates/
    ├── auth.html
    ├── index.html
    └── performance_report.html
```

## How The Flow Works

1. The user signs in or creates an account using Firebase Authentication.
2. Flask stores basic session information for the logged-in user.
3. The user uploads a PDF resume and pastes a job description.
4. The backend extracts resume text and sends the resume + job description + role context to Gemini.
5. Gemini returns:
   - interview questions
   - ideal answers
   - coding challenges for technical rounds
6. The user completes the voice interview round.
7. The user solves coding challenges in the browser editor.
8. The backend executes the submitted code locally and checks it against test cases.
9. The app evaluates the complete practice session and builds a performance report.
10. The report is displayed on a dedicated dashboard and also saved to Firestore history.

## Tech Stack

### Backend

- Python
- Flask
- python-dotenv
- PyPDF2

### Frontend

- HTML
- CSS
- Vanilla JavaScript
- Bootstrap 5
- Chart.js
- Web Speech API

### Cloud / AI Services

- Google Gemini API
- Firebase Authentication
- Firebase Firestore

## Requirements

Before running the project, make sure you have:

- Python 3.10+ recommended
- `pip`
- A Google Gemini API key
- Internet access for Gemini and Firebase services
- A modern browser with speech features for the voice round

Optional but recommended for full coding-round support:

- Node.js for JavaScript execution
- Java JDK for Java execution

If Node.js or Java are not installed, the app will automatically limit available coding languages to the runtimes found on the machine.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd HirePrep_AI
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the project root.

Example:

```env
GOOGLE_API_KEY=your_gemini_api_key_here
SECRET_KEY=your_flask_secret_here
>>>>>>> 1f33386 (Update README and performance report)
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
=======
### Variable reference

- `GOOGLE_API_KEY`
  Used for Gemini API requests. This is required.

- `SECRET_KEY`
  Used by Flask for session security. If omitted, the app falls back to a development default. For real deployments, always set your own secure value.

- `GEMINI_TIMEOUT_SECONDS`
  Timeout for Gemini API calls. Optional.

- `GEMINI_MAX_RETRIES`
  Retry count for Gemini API calls. Optional.

## Firebase Setup

The frontend currently includes Firebase configuration directly in the client-side code in:

- `templates/auth.html`
- `static/script.js`

That Firebase project is used for:

- Authentication
- Firestore session history

If you want to use your own Firebase project:

1. Create a Firebase project.
2. Enable Email/Password Authentication.
3. Create a Firestore database.
4. Replace the Firebase config objects in:
   - `templates/auth.html`
   - `static/script.js`
5. Update Firestore security rules appropriately before production use.

## Running The App

Start the Flask server:
>>>>>>> 1f33386 (Update README and performance report)

```bash
python main.py
```


Then open:

The app will run locally at:


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

## Supported Routes

- `/`
  Authentication page

- `/auth`
  Alias for the authentication page

- `/dashboard`
  Main interview workspace

- `/generate`
  Generates interview questions and coding challenges

- `/run_code`
  Executes coding submissions and validates results

- `/evaluate_practice`
  Produces the combined practice performance report

- `/performance-report`
  Displays the report dashboard

- `/performance-report-data`
  Returns report JSON for the dashboard

- `/logout`
  Clears the session and logs the user out

- `/switch-account`
  Clears the session and returns to authentication

## Coding Round Details

The coding round is designed to run submissions locally on the server machine.

### Python

- Uses the current Python interpreter
- Executes code in a temporary file

### JavaScript

- Requires `node` to be installed and available in PATH

### Java

- Requires both `java` and `javac` to be installed and available in PATH

The backend automatically detects which runtimes are available and exposes only supported languages to the generated challenge flow.

## Resume Upload Rules

- Resume upload is required for generation
- Resume must be a PDF file
- Maximum upload size is 5 MB

## Session And Security Notes

Current backend configuration includes:

- non-permanent Flask sessions
- 30-minute session lifetime
- HTTP-only cookies
- `SameSite=Lax`
- upload size limit of 5 MB

Important notes:

- The app currently runs with `debug=True` in `main.py`
- A fallback development `SECRET_KEY` is present in code
- Firebase configuration is embedded in frontend files

These are acceptable for local development, but should be tightened for production deployment.

## Known Limitations

- No automated test suite is included yet
- Firebase config is hardcoded in client files instead of environment-based frontend config
- The app depends on external services for Gemini generation and Firebase auth/history
- Voice input depends on browser support for speech recognition
- Generated interview and coding quality may vary based on resume quality, job description quality, and AI output consistency

## Future Improvements

- Add automated tests for Flask routes and coding execution helpers
- Move Firebase configuration to a safer environment-driven setup
- Add Docker support
- Add persistent backend storage for reports beyond session memory
- Add admin or recruiter-facing review workflows
- Add export options for reports
- Add richer analytics for repeated practice sessions

## Dependencies

Current Python dependencies:

- `flask`
- `PyPDF2`
- `python-dotenv`

Install them with:

```bash
pip install -r requirements.txt
```

## Troubleshooting

### Gemini API error

Check that:

- `GOOGLE_API_KEY` is set correctly in `.env`
- your key has access to the Gemini API
- your network allows outgoing API requests

### Resume upload fails

Check that:

- the file is a valid PDF
- the file is under 5 MB

### JavaScript or Java is missing from coding languages

Check that:

- `node` is installed for JavaScript
- `java` and `javac` are installed for Java
- those commands are available in your system PATH

### Voice input does not work

Check that:

- you are using a supported browser
- microphone permissions are enabled
- your browser supports the Web Speech API

## Development Notes

The backend stores the latest generated practice report in the Flask session under `last_practice_report`. Past reports are also saved in Firestore under the `interview_history` collection.

The performance report page can load report data from either:

- session storage for freshly completed sessions
- Flask session-backed `/performance-report-data` for current-session data
- Firestore-backed history selection from the dashboard

## License

Add your preferred license here, for example MIT.

