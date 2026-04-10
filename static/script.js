/**
 * AI COACH - CORE FRONTEND LOGIC
 * Manages: Firebase Sessions, Firestore History, Voice Recognition, AI Generation, and UI State
 */
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getAuth, onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";
import { 
    getFirestore, 
    collection, 
    addDoc, 
    serverTimestamp,
    query,
    where,
    getDocs
} from "https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js";

// --- 1. FIREBASE INITIALIZATION ---
const firebaseConfig = {
    apiKey: "AIzaSyBmzuqvzGqslOqb8tiO2a-Yvysqvgz6LAM",
    authDomain: "aicoach-bba0e.firebaseapp.com",
    projectId: "aicoach-bba0e",
    storageBucket: "aicoach-bba0e.firebasestorage.app",
    messagingSenderId: "644388512378",
    appId: "1:644388512378:web:5c6b6bb16f869e2f0751c3",
    measurementId: "G-GLTNZB8CKF"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

// --- 2. GLOBAL STATE & UI ELEMENTS ---
let currentUser = null;
const state = {
    interviewQuestions: [],
    codingChallenges: [],
    currentIdx: 0,
    transcript: [],
    voiceCompleted: false,
    isRecording: false,

    preferredVoice: null,
=======

    reportsById: {},
    activeCodingIdx: 0,
    activeLanguage: 'python',
    codeDrafts: {},
    codingResultsByChallenge: {},
    codingRoundComplete: false
};

const REPORT_STORAGE_KEY = 'aiCoachPerformanceReport';

const genForm = document.getElementById('genForm');
const resultDiv = document.getElementById('result');
const placeholder = document.getElementById('placeholder');
const loadingDiv = document.getElementById('loading');
const statusMsg = document.getElementById('status-message');
const codingContent = document.getElementById('coding-content');
const codingEmpty = document.getElementById('coding-empty');
const codingChallengePicker = document.getElementById('coding-challenge-picker');
const codingSelect = document.getElementById('coding-select');
const languageSelect = document.getElementById('language-select');
const codeEditor = document.getElementById('code-editor');

// --- 3. AUTHENTICATION MONITOR ---
// script.js - Inside your auth listener
onAuthStateChanged(auth, (user) => {
    if (user) {
        currentUser = user;
        state.user = user;
        loadSessionHistory(user.uid); 
    } else {
        window.location.href = "/auth";
    }
});

// --- 4. FIRESTORE OPERATIONS ---

async function saveToHistory(result) {
    if (!currentUser) return;
    try {
        await addDoc(collection(db, "interview_history"), {
            uid: currentUser.uid,
            timestamp: serverTimestamp(),
            transcript: state.transcript,
            practiceReport: result
        });
        console.log("Session saved to cloud.");
    } catch (e) {
        console.error("Error saving session: ", e);
    }
}

async function loadSessionHistory(uid) {
    const historyList = document.getElementById('history-list');
    if (!historyList) return;

    const q = query(
        collection(db, "interview_history"),
        where("uid", "==", uid)
    );

    try {
        const querySnapshot = await getDocs(q);
        historyList.innerHTML = ""; // Clear existing
        state.reportsById = {};
        const sessions = [];

        querySnapshot.forEach((doc) => {
            const data = doc.data();
            sessions.push({
                id: doc.id,
                ...data
            });
        });

        sessions
        .sort((a, b) => {
            const aTime = a.timestamp?.toMillis?.() || 0;
            const bTime = b.timestamp?.toMillis?.() || 0;
            return bTime - aTime;
        })
        .slice(0, 10)
        .forEach((session) => {
            const date = session.timestamp?.toDate?.().toLocaleDateString() || "Recent";
            state.reportsById[session.id] = session;

            const item = document.createElement('div');
            item.className = "history-item p-3 mb-2 rounded border-secondary";
            item.innerHTML = `
                <div class="small text-muted">${date}</div>
                <div class="fw-bold">Interview Session</div>
                <button class="btn btn-sm btn-link p-0" onclick="viewPastReport('${session.id}')">View Report</button>
            `;
            historyList.appendChild(item);
        });

        if (sessions.length === 0) {
            historyList.innerHTML = '<p class="small text-muted text-center py-2">No previous sessions found.</p>';
        }
    } catch (e) {
        console.error("History Load Error:", e);
        historyList.innerHTML = '<p class="small text-warning text-center py-2">Could not load past sessions.</p>';
    }
}

window.viewPastReport = function(docId) {
    const reportData = state.reportsById[docId];
    const practiceReport = reportData?.practiceReport;
    if (!practiceReport) {
        alert("Past report not available.");
        return;
    }

    sessionStorage.setItem(REPORT_STORAGE_KEY, JSON.stringify(practiceReport));
    window.location.href = '/performance-report?source=history';
}

// --- 5. UI UTILITIES ---

window.toggleLoading = function(isLoading, message = "Processing...") {
    if (isLoading) {
        loadingDiv.classList.remove('d-none');
        statusMsg.innerText = message;
        placeholder.classList.add('d-none');
        resultDiv.classList.add('d-none');
    } else {
        loadingDiv.classList.add('d-none');
    }
}

// --- 6. VOICE INTERVIEW ENGINE ---

function rankVoice(voice) {
    const name = `${voice.name || ''} ${(voice.lang || '')}`.toLowerCase();
    let score = 0;

    if (voice.localService) score += 4;
    if (voice.default) score += 2;
    if (name.includes('en-in')) score += 7;
    if (name.includes('en-gb')) score += 6;
    if (name.includes('en-us')) score += 5;
    if (name.includes('female')) score += 2;
    if (name.includes('natural')) score += 6;
    if (name.includes('neural')) score += 6;
    if (name.includes('enhanced')) score += 5;
    if (name.includes('premium')) score += 4;
    if (name.includes('microsoft')) score += 4;
    if (name.includes('google')) score += 3;
    if (name.includes('zira')) score += 4;
    if (name.includes('aria')) score += 5;
    if (name.includes('jenny')) score += 5;
    if (name.includes('samantha')) score += 4;
    if (name.includes('alloy')) score += 3;
    if (name.includes('robot')) score -= 8;
    if (name.includes('espeak')) score -= 10;
    if (name.includes('speech dispatcher')) score -= 8;

    return score;
}

function resolvePreferredVoice() {
    if (!('speechSynthesis' in window)) return null;

    const voices = window.speechSynthesis.getVoices();
    if (!voices.length) return null;

    const englishVoices = voices.filter((voice) => /^en([-_]|$)/i.test(voice.lang || ''));
    const candidates = englishVoices.length ? englishVoices : voices;
    const [bestVoice] = [...candidates].sort((a, b) => rankVoice(b) - rankVoice(a));
    state.preferredVoice = bestVoice || null;
    return state.preferredVoice;
}

function initializeSpeechVoices() {
    resolvePreferredVoice();

    if ('speechSynthesis' in window) {
        window.speechSynthesis.onvoiceschanged = () => {
            resolvePreferredVoice();
        };
    }
}

initializeSpeechVoices();

window.initiateInterview = function() {
    if (state.interviewQuestions.length === 0) {
        alert("Please generate questions first!");
        return;
    }
    state.currentIdx = 0;
    state.transcript = [];
    state.voiceCompleted = false;
    document.getElementById('start-voice-btn').classList.add('d-none');
    document.getElementById('stop-voice-btn').classList.remove('d-none');
    document.getElementById('user-answer-container').classList.remove('d-none');
    askQuestion();
}

function askQuestion() {
    const q = state.interviewQuestions[state.currentIdx].question;
    document.getElementById('current-question').innerText = `Q${state.currentIdx + 1}: ${q}`;
    speakText(q);
}

function speakText(text) {
    if (!('speechSynthesis' in window)) return;

    window.speechSynthesis.cancel();
    const msg = new SpeechSynthesisUtterance(text);
    const preferredVoice = state.preferredVoice || resolvePreferredVoice();

    if (preferredVoice) {
        msg.voice = preferredVoice;
        msg.lang = preferredVoice.lang || 'en-US';
    } else {
        msg.lang = 'en-US';
    }

    msg.rate = 0.94;
    msg.pitch = 1.02;
    msg.volume = 1;
    window.speechSynthesis.speak(msg);
}

window.startListening = function() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return alert("Browser not supported");

    const recognition = new SpeechRecognition();
    recognition.onstart = () => {
        document.getElementById('mic-btn').classList.add('btn-danger');
    };
    recognition.onresult = (event) => {
        const text = event.results[0][0].transcript;
        document.getElementById('user-text-answer').value = text;
    };
    recognition.onend = () => {
        document.getElementById('mic-btn').classList.remove('btn-danger');
    };
    recognition.start();
}

window.submitAnswer = function() {
    const ans = document.getElementById('user-text-answer').value;
    if (!ans) return alert("Please provide an answer.");

    state.transcript.push({
        question: state.interviewQuestions[state.currentIdx].question,
        answer: ans
    });

    document.getElementById('user-text-answer').value = "";
    state.currentIdx++;

    if (state.currentIdx < state.interviewQuestions.length) {
        askQuestion();
    } else {
        finishInterview();
    }
}

window.skipVoiceQuestion = function() {
    if (state.currentIdx >= state.interviewQuestions.length) return;

    state.transcript.push({
        question: state.interviewQuestions[state.currentIdx].question,
        answer: "Skipped by candidate."
    });

    document.getElementById('user-text-answer').value = "";
    state.currentIdx++;

    if (state.currentIdx < state.interviewQuestions.length) {
        askQuestion();
    } else {
        finishInterview();
    }
}

async function finishInterview() {
    state.voiceCompleted = true;
    window.speechSynthesis.cancel();
    document.getElementById('voice-interface-card').classList.add('d-none');
    document.getElementById('stop-voice-btn').classList.add('d-none');
    document.getElementById('start-voice-btn').classList.remove('d-none');

    if (state.codingChallenges.length) {
        switchMode('coding');
        setCodingFeedback('Voice round complete. Finish the coding round to generate your full performance dashboard.', 'info');
        return;
    }

    await finalizePracticeFlow();
}

// --- 7. GENERATOR FORM HANDLING ---

if (genForm) {
    genForm.onsubmit = async (e) => {
        e.preventDefault();
        await loadGeneratedContent({ showGeneratorResults: true, targetMode: 'generator' });
    };
}

async function loadGeneratedContent({ showGeneratorResults = true, targetMode = 'generator' } = {}) {
    const formData = new FormData(genForm);
    const resumeFile = formData.get('resume');
    const jobDescription = String(formData.get('job_description') || '').trim();

    if (!(resumeFile instanceof File) || !resumeFile.name || !jobDescription) {
        alert("Please upload your resume and fill in the job description before generating questions or coding tests.");
        return false;
    }

    toggleLoading(true, "Creating your interview...");

    try {
        const response = await fetch('/generate', { method: 'POST', body: formData });
        const data = await response.json();

        if (!(data.interview_questions || data.coding_challenges)) {
            alert("Error: " + (data.error || "Failed to generate"));
            return false;
        }

        prepareInterviewData(data);
        renderCodingRound();

        if (showGeneratorResults) {
            renderGeneratedContent(data);
            resultDiv.classList.remove('d-none');
        }

        if (targetMode === 'voice' && !state.interviewQuestions.length) {
            alert("No voice-friendly interview questions were generated. Try changing the category or job description.");
            return false;
        }

        if (targetMode === 'coding' && !state.codingChallenges.length) {
            alert("No coding challenge was generated for the current setup. Choose Technical and try again.");
            return false;
        }

        return true;
    } catch (error) {
        console.error("Generation Error:", error);
        alert(error?.message || "Could not generate content right now.");
        return false;
    } finally {
        toggleLoading(false);
    }
}

function prepareInterviewData(payload) {
    state.interviewQuestions = payload.interview_questions || [];
    state.codingChallenges = payload.coding_challenges || [];
    state.activeCodingIdx = 0;
    state.activeLanguage = 'python';
    state.codeDrafts = {};
    state.codingResultsByChallenge = {};
    state.codingRoundComplete = false;
    state.voiceCompleted = false;
    state.transcript = [];
}

function renderGeneratedContent(payload) {
    const interviewQuestions = payload.interview_questions || [];

    const interviewMarkup = interviewQuestions.length
        ? interviewQuestions.map((item, idx) => `
            <article class="result-card">
                <div class="result-card-label">Interview Question ${idx + 1}</div>
                <h4>${escapeHtml(item.question)}</h4>
                <p class="result-card-answer-label">Ideal Answer</p>
                <p>${escapeHtml(item.ideal_answer)}</p>
            </article>
        `).join('')
        : '<p class="text-muted m-0">No interview questions were returned.</p>';

    resultDiv.innerHTML = `
        <section class="result-section-panel">
            <div class="result-section-header">
                <p class="section-kicker">Interview Questions</p>
                <h3>Questions for speaking or typing</h3>
            </div>
            ${interviewMarkup}
        </section>
    `;
}

function renderCodingRound() {
    if (!codingContent || !codingEmpty || !codingChallengePicker || !codingSelect) return;

    if (!state.codingChallenges.length) {
        codingEmpty.classList.remove('d-none');
        codingContent.classList.add('d-none');
        codingChallengePicker.classList.add('d-none');
        return;
    }

    codingEmpty.classList.add('d-none');
    codingContent.classList.remove('d-none');

    if (state.codingChallenges.length > 1) {
        codingChallengePicker.classList.remove('d-none');
    } else {
        codingChallengePicker.classList.add('d-none');
    }

    codingSelect.innerHTML = state.codingChallenges.map((challenge, idx) => `
        <option value="${idx}">${escapeHtml(challenge.title || `Challenge ${idx + 1}`)}</option>
    `).join('');
    codingSelect.value = String(state.activeCodingIdx);
    populateCodingChallenge(state.activeCodingIdx);
}

function populateCodingChallenge(index) {
    const challenge = state.codingChallenges[index];
    if (!challenge) return;

    persistCurrentCodeDraft();
    state.activeCodingIdx = index;
    document.getElementById('coding-progress').innerText = `Challenge ${index + 1} of ${state.codingChallenges.length}`;
    document.getElementById('coding-title').innerText = challenge.title;
    document.getElementById('coding-prompt').innerText = challenge.prompt;
    document.getElementById('coding-example-input').innerText = challenge.example_input || 'No sample input provided.';
    document.getElementById('coding-example-output').innerText = challenge.example_output || 'No sample output provided.';
    document.getElementById('code-output').innerText = 'Run your solution to see stdout and stderr here.';
    setCodeStatus('Idle');
    setCodingFeedback('', '');
    hideCodingCompletion();

    const requirements = (challenge.requirements || [])
        .map(item => `<li>${escapeHtml(item)}</li>`)
        .join('');

    document.getElementById('coding-requirements').innerHTML = requirements
        ? `<h5 class="text-light mt-4 mb-2">Requirements</h5><ul>${requirements}</ul>`
        : '';

    const supportedLanguages = challenge.supported_languages || Object.keys(challenge.starter_code_by_language || {});
    languageSelect.innerHTML = supportedLanguages.map((languageId) => `
        <option value="${languageId}">${formatLanguageLabel(languageId)}</option>
    `).join('');

    const preferredLanguage = supportedLanguages.includes(state.activeLanguage)
        ? state.activeLanguage
        : supportedLanguages[0];
    state.activeLanguage = preferredLanguage;
    languageSelect.value = preferredLanguage;
    document.getElementById('code-editor-label').innerText = `${formatLanguageLabel(preferredLanguage)} Solution`;
    document.getElementById('code-editor').value = getCodeForCurrentSelection();
    autoResizeEditor();
}

if (codingSelect) {
    codingSelect.addEventListener('change', (event) => {
        populateCodingChallenge(Number(event.target.value));
    });
}

if (languageSelect) {
    languageSelect.addEventListener('change', (event) => {
        persistCurrentCodeDraft();
        state.activeLanguage = event.target.value;
        document.getElementById('code-editor-label').innerText = `${formatLanguageLabel(state.activeLanguage)} Solution`;
        document.getElementById('code-editor').value = getCodeForCurrentSelection();
        autoResizeEditor();
        setCodingFeedback('', '');
        setCodeStatus('Idle');
        document.getElementById('code-output').innerText = 'Run your solution to see stdout and stderr here.';
    });
}

if (codeEditor) {
    codeEditor.addEventListener('input', autoResizeEditor);
}

window.runCodingChallenge = async function() {
    const code = document.getElementById('code-editor').value;
    const stdin = document.getElementById('code-stdin').value;
    const outputEl = document.getElementById('code-output');
    const runBtn = document.getElementById('run-code-btn');
    const challenge = state.codingChallenges[state.activeCodingIdx];

    if (!code.trim()) {
        alert("Please write some code first.");
        return;
    }

    runBtn.disabled = true;
    setCodeStatus('Running...');
    outputEl.innerText = `Executing ${formatLanguageLabel(state.activeLanguage)} code...`;

    try {
        const response = await fetch('/run_code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code,
                stdin,
                language: state.activeLanguage,
                example_output: state.codingChallenges[state.activeCodingIdx]?.example_output || '',
                test_cases: state.codingChallenges[state.activeCodingIdx]?.test_cases || []
            })
        });
        const data = await response.json();

        if (!response.ok || data.error) {
            setCodeStatus('Run Failed');
            outputEl.innerText = data.error || 'Execution failed.';
            setCodingFeedback('Please fix the issue and try again.', 'warning');
            return;
        }

        const stdout = data.stdout?.trim() ? `STDOUT\n${data.stdout}` : 'STDOUT\n<empty>';
        const stderr = data.stderr?.trim() ? `\nSTDERR\n${data.stderr}` : '';
        setCodeStatus(data.returncode === 0 ? 'Success' : `Exit ${data.returncode}`);
        outputEl.innerText = `${stdout}${stderr}`;

        const totalTests = Number(data.total_tests || 0);
        const passedCount = Number(data.passed_count || 0);
        const passedAll = Boolean(data.passed_all_tests);
        const accepted = Boolean(data.accepted);
        const visibleMatch = Boolean(data.visible_match);
        const qualityFeedback = data.quality_feedback || '';

        state.codingResultsByChallenge[state.activeCodingIdx] = {
            title: challenge?.title || `Challenge ${state.activeCodingIdx + 1}`,
            language: state.activeLanguage,
            accepted,
            passed_tests: passedCount,
            total_tests: totalTests,
            quality_feedback: qualityFeedback,
            status: data.returncode === 0 ? 'completed' : `exit_${data.returncode}`
        };

        if (accepted) {
            const successMessage = passedAll
                ? `Correct answer. Great job, you passed all ${totalTests} test cases. ${qualityFeedback}`
                : visibleMatch
                    ? `Correct answer. Your output matches the expected result. ${qualityFeedback}`
                    : `Correct answer. ${qualityFeedback}`;
            setCodingFeedback(successMessage, 'success');
        } else {
            const failedCase = data.failed_case;
            const failureHint = failedCase
                ? `First failing test expected "${failedCase.expected_output}" but got "${failedCase.actual_output || '<empty>'}".`
                : 'Your solution did not pass all backend checks yet.';
            const prefix = totalTests ? `Passed ${passedCount}/${totalTests} tests.` : 'The answer does not match the expected result yet.';
            setCodingFeedback(`${prefix} ${failureHint} ${qualityFeedback}`.trim(), 'warning');
        }
    } catch (error) {
        setCodeStatus('Run Failed');
        outputEl.innerText = 'Could not execute code right now.';
        setCodingFeedback('Execution did not complete. Please try again.', 'warning');
        console.error("Code execution error:", error);
    } finally {
        runBtn.disabled = false;
    }
}

window.nextCodingChallenge = function() {
    if (!state.codingChallenges.length) return;

    const nextIndex = state.activeCodingIdx + 1;
    if (nextIndex < state.codingChallenges.length) {
        codingSelect.value = String(nextIndex);
        populateCodingChallenge(nextIndex);
    } else {
        showCodingCompletion(
            state.codingChallenges[state.activeCodingIdx],
            'You have reached the end of the coding round. Review the guidance below and open your full performance dashboard.'
        );
    }
}

window.skipCodingChallenge = function() {
    if (!state.codingChallenges.length) return;

    const nextIndex = state.activeCodingIdx + 1;
    if (nextIndex < state.codingChallenges.length) {
        state.codingResultsByChallenge[state.activeCodingIdx] = {
            title: state.codingChallenges[state.activeCodingIdx]?.title || `Challenge ${state.activeCodingIdx + 1}`,
            language: state.activeLanguage,
            accepted: false,
            passed_tests: 0,
            total_tests: Number(state.codingChallenges[state.activeCodingIdx]?.test_cases?.length || 0),
            quality_feedback: 'Challenge skipped by candidate.',
            status: 'skipped'
        };
        codingSelect.value = String(nextIndex);
        populateCodingChallenge(nextIndex);
        setCodingFeedback('Challenge skipped. Moving to the next one.', 'info');
    } else {
        state.codingResultsByChallenge[state.activeCodingIdx] = {
            title: state.codingChallenges[state.activeCodingIdx]?.title || `Challenge ${state.activeCodingIdx + 1}`,
            language: state.activeLanguage,
            accepted: false,
            passed_tests: 0,
            total_tests: Number(state.codingChallenges[state.activeCodingIdx]?.test_cases?.length || 0),
            quality_feedback: 'Challenge skipped by candidate.',
            status: 'skipped'
        };
        showCodingCompletion(
            state.codingChallenges[state.activeCodingIdx],
            'The final coding challenge was skipped. Review the suggestion below and open your full performance dashboard.'
        );
    }
}

window.completePracticeFlow = async function() {
    if (!state.voiceCompleted) {
        alert("Finish the voice mock interview first so the full practice report includes both sections.");
        return;
    }
    await finalizePracticeFlow();
}

async function finalizePracticeFlow() {
    toggleLoading(true, "Building your full practice performance dashboard...");

    try {
        const response = await fetch('/evaluate_practice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                voice_transcript: state.transcript,
                coding_results: getCodingResultsForEvaluation()
            })
        });
        const data = await response.json();

        if (!response.ok || data.error || !data.report) {
            alert(data.error || 'Could not build the performance dashboard right now.');
            return;
        }

        sessionStorage.setItem(REPORT_STORAGE_KEY, JSON.stringify(data.report));
        await saveToHistory(data.report);
        await loadSessionHistory(state.user.uid);
        window.location.href = data.redirect_url || '/performance-report';
    } catch (error) {
        console.error("Practice evaluation failed", error);
        alert("Could not build the performance dashboard right now.");
    } finally {
        toggleLoading(false);
    }
}

function getCodingResultsForEvaluation() {
    return Object.keys(state.codingResultsByChallenge)
        .sort((a, b) => Number(a) - Number(b))
        .map((key) => state.codingResultsByChallenge[key]);
}

function setCodeStatus(text) {
    const badge = document.getElementById('code-status-badge');
    if (badge) {
        badge.innerText = text;
    }
}

function setCodingFeedback(message, kind) {
    const banner = document.getElementById('coding-feedback');
    if (!banner) return;

    if (!message) {
        banner.className = 'coding-feedback-banner d-none mt-4';
        banner.innerText = '';
        return;
    }

    banner.className = `coding-feedback-banner coding-feedback-${kind} mt-4`;
    banner.innerText = message;
}

function showCodingCompletion(challenge, message) {
    const panel = document.getElementById('coding-complete');
    if (!panel || !challenge) return;
    state.codingRoundComplete = true;

    const answer = challenge.reference_answer_by_language?.[state.activeLanguage]
        || challenge.reference_answer_by_language?.python
        || 'Reference answer not available for this language.';

    document.getElementById('coding-complete-message').innerText = message;
    document.getElementById('coding-complete-suggestion').innerText =
        challenge.suggestion || 'Review the problem carefully, identify the core transformation, and validate edge cases.';
    document.getElementById('coding-complete-answer').innerText = answer;
    panel.classList.remove('d-none');
    setCodingFeedback('Coding round complete. Your final report will combine voice interview and coding performance.', 'info');
}

function hideCodingCompletion() {
    const panel = document.getElementById('coding-complete');
    if (panel) {
        panel.classList.add('d-none');
    }
    state.codingRoundComplete = false;
}

function persistCurrentCodeDraft() {
    const editor = document.getElementById('code-editor');
    if (!editor || state.activeCodingIdx == null) return;

    const challenge = state.codingChallenges[state.activeCodingIdx];
    if (!challenge || !state.activeLanguage) return;

    const draftKey = `${state.activeCodingIdx}:${state.activeLanguage}`;
    state.codeDrafts[draftKey] = editor.value;
}

function getCodeForCurrentSelection() {
    const challenge = state.codingChallenges[state.activeCodingIdx];
    if (!challenge) return '';

    const draftKey = `${state.activeCodingIdx}:${state.activeLanguage}`;
    if (draftKey in state.codeDrafts) {
        return state.codeDrafts[draftKey];
    }

    return challenge.starter_code_by_language?.[state.activeLanguage] || '';
}

function formatLanguageLabel(languageId) {
    const labels = {
        python: 'Python',
        javascript: 'JavaScript',
        java: 'Java',
    };
    return labels[languageId] || languageId;
}

function autoResizeEditor() {
    if (!codeEditor) return;
    codeEditor.style.height = 'auto';
    codeEditor.style.height = `${Math.max(420, codeEditor.scrollHeight)}px`;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Sidebar/Navigation logic
window.switchMode = async function(mode) {
    document.querySelectorAll('.mode-nav-link').forEach((link) => {
        link.classList.toggle('active', link.dataset.mode === mode);
    });

    if (typeof window.collapseSidebar === 'function') {
        window.collapseSidebar();
    }

    if (mode === 'generator') {
        document.getElementById('section-generator').classList.remove('d-none');
        document.getElementById('section-voice').classList.add('d-none');
        document.getElementById('section-coding').classList.add('d-none');
    } else {
        if (mode === 'voice' && !state.interviewQuestions.length) {
            const ok = await loadGeneratedContent({ showGeneratorResults: false, targetMode: 'voice' });
            if (!ok) {
                switchMode('generator');
                return;
            }
        }

        if (mode === 'coding' && !state.codingChallenges.length) {
            const ok = await loadGeneratedContent({ showGeneratorResults: false, targetMode: 'coding' });
            if (!ok) {
                switchMode('generator');
                return;
            }
        }

        document.getElementById('section-generator').classList.add('d-none');
        if (mode === 'voice') {
            document.getElementById('section-voice').classList.remove('d-none');
            document.getElementById('section-coding').classList.add('d-none');
        } else {
            document.getElementById('section-voice').classList.add('d-none');
            document.getElementById('section-coding').classList.remove('d-none');
        }
    }
}

window.exitModes = function() {
    window.location.reload();
}

window.stopInterview = function() {
    window.speechSynthesis.cancel();
    state.currentIdx = 0;
    state.transcript = [];
    state.voiceCompleted = false;
    document.getElementById('current-question').innerText = 'Click "Start Interview" to begin';
    document.getElementById('user-text-answer').value = '';
    document.getElementById('user-answer-container').classList.add('d-none');
    document.getElementById('stop-voice-btn').classList.add('d-none');
    document.getElementById('start-voice-btn').classList.remove('d-none');
    document.getElementById('voice-interface-card').classList.remove('d-none');
}

window.logoutUser = async function(path = '/logout') {
    try {
        await signOut(auth);
    } catch (error) {
        console.error("Firebase sign-out error:", error);
    } finally {
        window.location.href = path;
    }
}
