/**
 * AI COACH - CORE FRONTEND LOGIC
 * Manages: Firebase Sessions, Firestore History, Voice Recognition, AI Generation, and UI State
 */
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";
import { 
    getFirestore, 
    collection, 
    addDoc, 
    serverTimestamp,
    query,
    where,
    orderBy,
    limit,
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
    questions: [],
    currentIdx: 0,
    transcript: [],
    isRecording: false
};

const genForm = document.getElementById('genForm');
const resultDiv = document.getElementById('result');
const placeholder = document.getElementById('placeholder');
const loadingDiv = document.getElementById('loading');
const statusMsg = document.getElementById('status-message');

// --- 3. AUTHENTICATION MONITOR ---
// script.js - Inside your auth listener
onAuthStateChanged(auth, (user) => {
    if (user) {
        state.user = user;
        // This is the critical line to populate the sidebar
        loadSessionHistory(user.uid); 
    } else {
        window.location.href = "/auth";
    }
});

// --- 4. FIRESTORE OPERATIONS ---

async function saveToHistory(feedbackReport) {
    if (!currentUser) return;
    try {
        await addDoc(collection(db, "interview_history"), {
            uid: currentUser.uid,
            timestamp: serverTimestamp(),
            transcript: state.transcript,
            feedback: feedbackReport
        });
        console.log("Session saved to cloud.");
    } catch (e) {
        console.error("Error saving session: ", e);
    }
}

async function loadSessionHistory(uid) {
    const historyList = document.getElementById('history-list');
    if (!historyList) return;

    // 1. Get reference to your collection
    const q = query(
        collection(db, "interview_history"),
        where("uid", "==", uid),
        orderBy("timestamp", "desc"),
        limit(10)
    );

    try {
        const querySnapshot = await getDocs(q);
        historyList.innerHTML = ""; // Clear existing

        querySnapshot.forEach((doc) => {
            const data = doc.data();
            const date = data.timestamp?.toDate().toLocaleDateString() || "Recent";
            
            // Create the history item button
            const item = document.createElement('div');
            item.className = "history-item p-3 mb-2 rounded border-secondary";
            item.innerHTML = `
                <div class="small text-muted">${date}</div>
                <div class="fw-bold">Interview Session</div>
                <button class="btn btn-sm btn-link p-0" onclick="viewPastReport('${doc.id}')">View Report</button>
            `;
            historyList.appendChild(item);
        });
    } catch (e) {
        console.error("History Load Error:", e);
    }
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

window.initiateInterview = function() {
    if (state.questions.length === 0) {
        alert("Please generate questions first!");
        return;
    }
    state.currentIdx = 0;
    state.transcript = [];
    document.getElementById('start-voice-btn').classList.add('d-none');
    document.getElementById('stop-voice-btn').classList.remove('d-none');
    document.getElementById('user-answer-container').classList.remove('d-none');
    askQuestion();
}

function askQuestion() {
    const q = state.questions[state.currentIdx];
    document.getElementById('current-question').innerText = `Q${state.currentIdx + 1}: ${q}`;
    speakText(q);
}

function speakText(text) {
    window.speechSynthesis.cancel();
    const msg = new SpeechSynthesisUtterance(text);
    msg.rate = 0.9;
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
        question: state.questions[state.currentIdx],
        answer: ans
    });

    document.getElementById('user-text-answer').value = "";
    state.currentIdx++;

    if (state.currentIdx < state.questions.length) {
        askQuestion();
    } else {
        finishInterview();
    }
}

async function finishInterview() {
    toggleLoading(true, "AI is analyzing your performance...");
    
    // Hide the interview interface to make room for the dashboard
    document.getElementById('voice-interface-card').classList.add('d-none');

    try {
        const response = await fetch('/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ data: state.transcript })
        });
        const evalData = await response.json();

        if (evalData.scores) {
            // 1. Update the Progress Bars and Text Scores
            updateStat('tech', evalData.scores.tech);
            updateStat('comm', evalData.scores.comm);
            updateStat('conf', evalData.scores.conf);

            // 2. Split and render the Markdown report
            const parts = evalData.report.split('###'); 
            document.getElementById('excel-content').innerHTML = marked.parse(parts[1] || "Points will appear here.");
            document.getElementById('improve-content').innerHTML = marked.parse(parts[2] || "Points will appear here.");

            // 3. Show the dashboard
            document.getElementById('performance-dashboard').classList.remove('d-none');
            
            // 4. Save to Firebase
            await saveToHistory(evalData.report);
            await loadSessionHistory(state.user.uid);
        }
    } catch (error) {
        console.error("Evaluation failed", error);
    } finally {
        toggleLoading(false);
    }
}

// Helper function to update the dashboard UI
function updateStat(key, score) {
    const bar = document.getElementById(`bar-${key}`);
    const txt = document.getElementById(`txt-${key}`);
    if (bar && txt) {
        const percent = (score / 10) * 100;
        bar.style.width = percent + "%";
        txt.innerText = score + "/10";
    }
}

// --- 7. GENERATOR FORM HANDLING ---

if (genForm) {
    genForm.onsubmit = async (e) => {
        e.preventDefault();
        toggleLoading(true, "Creating your interview...");

        const formData = new FormData(genForm);
        try {
            const response = await fetch('/generate', { method: 'POST', body: formData });
            const data = await response.json();

            if (data.questions) {
                // Render markdown to the result div
                resultDiv.innerHTML = marked.parse(data.questions);
                resultDiv.classList.remove('d-none');
                
                // Prepare the internal state for the interview mode
                prepareInterview(data.questions);
            } else {
                alert("Error: " + (data.error || "Failed to generate"));
            }
        } catch (error) {
            console.error("Generation Error:", error);
        } finally {
            toggleLoading(false);
        }
    };
}

function prepareInterview(markdownText) {
    // Splits by the numbered list (1., 2., etc.)
    // We filter to ensure we only get valid question blocks
    state.questions = markdownText
        .split(/\n\d+\.\s+/) 
        .filter(q => q.trim().length > 5)
        .map(q => q.trim());
    
    console.log("Questions & Answers Loaded into State:", state.questions);
}

// Sidebar/Navigation logic
window.switchMode = function(mode) {
    if (mode === 'generator') {
        document.getElementById('section-generator').classList.remove('d-none');
        document.getElementById('section-voice').classList.add('d-none');
    } else {
        document.getElementById('section-generator').classList.add('d-none');
        document.getElementById('section-voice').classList.remove('d-none');
    }
}

window.exitModes = function() {
    window.location.reload();
}