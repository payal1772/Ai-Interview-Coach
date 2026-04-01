const REPORT_STORAGE_KEY = 'aiCoachPerformanceReport';

const colors = {
    orange: '#ff7a18',
    coral: '#ef4444',
    pink: '#ec4899',
    cyan: '#38bdf8',
    yellow: '#facc15',
    text: '#f7f4ef',
    muted: '#a7b1c2'
};

document.addEventListener('DOMContentLoaded', async () => {
    const report = await loadReport();
    if (!report) {
        renderEmptyState();
        return;
    }

    renderSummary(report);
    renderLists(report);
    renderCharts(report);
});

async function loadReport() {
    const storedReport = sessionStorage.getItem(REPORT_STORAGE_KEY);
    if (storedReport) {
        try {
            const parsed = JSON.parse(storedReport);
            sessionStorage.removeItem(REPORT_STORAGE_KEY);
            return parsed;
        } catch (error) {
            console.error('Stored report parse error:', error);
            sessionStorage.removeItem(REPORT_STORAGE_KEY);
        }
    }

    try {
        const response = await fetch('/performance-report-data');
        const data = await response.json();
        if (!response.ok || data.error) {
            return null;
        }
        return data;
    } catch (error) {
        console.error('Performance report fetch failed:', error);
        return null;
    }
}

function renderSummary(report) {
    document.getElementById('report-title').innerText = report.overview?.title || 'Performance Dashboard';
    document.getElementById('report-summary').innerText = report.overview?.summary || 'Combined performance review';
    document.getElementById('overall-score').innerText = formatScore(report.scores?.overall);
    document.getElementById('voice-summary').innerText = `${report.practice_summary?.voice_answered || 0} / ${report.practice_summary?.voice_questions || 0}`;
    document.getElementById('coding-summary').innerText = `${report.practice_summary?.coding_accepted || 0} / ${report.practice_summary?.coding_attempted || 0}`;
    document.getElementById('coding-pass-ratio').innerText = `${Number(report.practice_summary?.coding_pass_ratio || 0).toFixed(1)}%`;
}

function renderLists(report) {
    renderList('strength-list', report.strengths || []);
    renderList('improvement-list', report.improvements || []);

    const recommendations = document.getElementById('recommendation-list');
    recommendations.innerHTML = '';
    (report.recommendations || []).forEach((item) => {
        const card = document.createElement('div');
        card.className = 'recommendation-item';
        card.innerText = item;
        recommendations.appendChild(card);
    });
}

function renderList(id, items) {
    const target = document.getElementById(id);
    target.innerHTML = '';
    items.forEach((item) => {
        const li = document.createElement('li');
        li.innerText = item;
        target.appendChild(li);
    });
}

function renderCharts(report) {
    const labels = report.chart_series?.score_labels || ['Technical', 'Communication', 'Confidence', 'Problem Solving', 'Code Quality'];
    const values = report.chart_series?.score_values || [0, 0, 0, 0, 0];
    const practiceBreakdown = report.chart_series?.practice_breakdown || [];

    const commonLegend = {
        labels: {
            color: colors.muted,
            font: { family: 'Plus Jakarta Sans' }
        }
    };

    new Chart(document.getElementById('scoreBarChart'), {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Score',
                data: values,
                backgroundColor: [colors.orange, colors.coral, colors.pink, colors.cyan, colors.yellow],
                borderRadius: 12
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    ticks: { color: colors.muted },
                    grid: { color: 'rgba(255,255,255,0.06)' }
                },
                y: {
                    min: 0,
                    max: 10,
                    ticks: { color: colors.muted },
                    grid: { color: 'rgba(255,255,255,0.08)' }
                }
            }
        }
    });

    new Chart(document.getElementById('practicePieChart'), {
        type: 'doughnut',
        data: {
            labels: practiceBreakdown.map((item) => item.label),
            datasets: [{
                data: practiceBreakdown.map((item) => item.value),
                backgroundColor: [colors.orange, '#334155', colors.cyan, '#1f2937'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: commonLegend }
        }
    });

    new Chart(document.getElementById('scoreRadarChart'), {
        type: 'radar',
        data: {
            labels,
            datasets: [{
                label: 'Capability',
                data: values,
                backgroundColor: 'rgba(255, 122, 24, 0.2)',
                borderColor: colors.orange,
                pointBackgroundColor: colors.pink,
                pointBorderColor: colors.text
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: commonLegend },
            scales: {
                r: {
                    min: 0,
                    max: 10,
                    angleLines: { color: 'rgba(255,255,255,0.08)' },
                    grid: { color: 'rgba(255,255,255,0.08)' },
                    pointLabels: { color: colors.muted },
                    ticks: { color: colors.muted, backdropColor: 'transparent' }
                }
            }
        }
    });

    new Chart(document.getElementById('scorePolarChart'), {
        type: 'polarArea',
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: [
                    'rgba(255, 122, 24, 0.72)',
                    'rgba(239, 68, 68, 0.68)',
                    'rgba(236, 72, 153, 0.66)',
                    'rgba(56, 189, 248, 0.66)',
                    'rgba(250, 204, 21, 0.66)'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: commonLegend },
            scales: {
                r: {
                    min: 0,
                    max: 10,
                    ticks: { color: colors.muted, backdropColor: 'transparent' },
                    grid: { color: 'rgba(255,255,255,0.08)' }
                }
            }
        }
    });
}

function renderEmptyState() {
    document.getElementById('report-title').innerText = 'No Report Available';
    document.getElementById('report-summary').innerText = 'Complete a practice flow first to generate the combined performance dashboard.';
    document.querySelectorAll('.report-panel canvas').forEach((canvas) => {
        canvas.parentElement.innerHTML += '<p class="empty-report-state">No chart data available yet.</p>';
        canvas.remove();
    });
}

function formatScore(value) {
    return Number(value || 0).toFixed(1);
}
