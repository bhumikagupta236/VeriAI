// Global variable to track the current input mode ('text' or 'url')
let currentInputMode = 'text';
let lastAnalyzedText = null; // Store the text/title that was just submitted

// --- Function to switch tabs (No Change) ---
function switchTab(mode) {
    const textTab = document.getElementById('tab-text');
    const urlTab = document.getElementById('tab-url');
    const textArea = document.getElementById('article-textarea');
    const urlInput = document.getElementById('article-url-input');
    const analyzeButton = document.getElementById('analyze-button');
    currentInputMode = mode;
    if (mode === 'text') {
        textTab.classList.add('active'); urlTab.classList.remove('active');
        textArea.style.display = 'block'; urlInput.style.display = 'none';
        analyzeButton.textContent = 'Analyze Text';
    } else {
        textTab.classList.remove('active'); urlTab.classList.add('active');
        textArea.style.display = 'none'; urlInput.style.display = 'block';
        analyzeButton.textContent = 'Analyze URL';
    }
}

// --- URL helpers ---
function isProbablyUrl(s) {
    if (!s) return false;
    s = s.trim();
    if (s.length > 2048) return false;
    const re = /^(?:https?:\/\/)?(?:[\w-]+\.)+[a-z]{2,}(?::\d+)?(?:\/[\S]*)?$/i;
    return re.test(s);
}
function normalizeUrl(u) {
    if (!u) return u;
    u = u.trim();
    if (!/^https?:\/\//i.test(u)) {
        u = 'https://' + u;
    }
    return u;
}

// --- Small UI helper: animate number changes (e.g., 0% -> 72%) ---
function animateNumber(el, to, duration = 500) {
    const text = (el.textContent || '0').replace(/[^0-9]/g, '');
    const from = parseInt(text || '0', 10);
    const start = performance.now();
    const step = (now) => {
        const t = Math.min(1, (now - start) / duration);
        const val = Math.round(from + (to - from) * t);
        el.textContent = `${val}%`;
        if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
}

// --- NEW/UPDATED Function to display analysis results ---
function displayAnalysisResult(resultData) {
    const resultsSection = document.getElementById('analysis-results-section');
    if (!resultData || resultData.status === 'empty') {
        resultsSection.style.display = 'none'; return;
    }
    resultsSection.style.display = 'block'; // Make sure it's visible

    // Get elements
    const banner = document.getElementById('result-banner');
    const icon = document.getElementById('result-icon');
    const statusText = document.getElementById('result-status-text');
    const subtext = document.getElementById('result-subtext');
    const confidenceBar = document.getElementById('confidence-bar');
    const confidencePercent = document.getElementById('confidence-percent');
    const headlineEl = document.getElementById('result-headline');
    const sourceEl = document.getElementById('result-source');
    const domainEl = document.getElementById('result-domain');
    const dateEl = document.getElementById('result-date');
    const urlEl = document.getElementById('result-url');
    const urlItemEl = urlEl.parentElement;
    const merkleHashEl = document.getElementById('result-merkle-hash');
    
    // Fetching the Gemini data
    const geminiFlag = resultData.gemini_flag; // True/False/null
    const geminiConf = resultData.gemini_confidence; // 0-100
    const geminiReason = resultData.gemini_reasoning;

    // --- Determine Status and Confidence ---
    let statusClass = 'status-not-found';
    let statusIcon = '❓';
    let bannerTitle = 'Rating Unavailable';
    let confidence = geminiConf !== null ? geminiConf : 20; // Use Gemini conf if available
    
    const actualRating = resultData.rating || 'N/A';
    const actualPublisher = resultData.publisher || 'N/A';
    const ratingLower = actualRating.toLowerCase();
const TRUE_RATINGS_JS = ['true', 'mostly true', 'correct attribution', 'accurate', 'correct', 'verified'];
const FALSE_RATINGS_JS = ['false', 'pants on fire', 'mostly false', 'scam', 'fake', 'incorrect', 'not true', 'debunked'];

    confidenceBar.className = 'progress-bar'; // Reset bar color class

    // Prefer server's final_verdict when available.
    if (resultData.final_verdict === 'VERIFIED_TRUE') {
        statusClass = 'status-verified'; statusIcon = '✅'; bannerTitle = 'Verified as Truthful';
    } else if (resultData.final_verdict === 'FLAGGED_FALSE') {
        statusClass = 'status-false'; statusIcon = '❌'; bannerTitle = 'Flagged as Potentially Misleading';
        confidenceBar.classList.add('low-confidence');
    } else {
        // Fallback to Fact Check rating if no clear final verdict.
        if (TRUE_RATINGS_JS.includes(ratingLower)) {
            statusClass = 'status-verified'; statusIcon = '✅'; bannerTitle = 'Verified as Truthful';
        } else if (FALSE_RATINGS_JS.includes(ratingLower)) {
            statusClass = 'status-false'; statusIcon = '❌'; bannerTitle = 'Flagged as Potentially Misleading';
            confidenceBar.classList.add('low-confidence');
        } else if (ratingLower === 'not found' || ratingLower === 'api error') {
            statusClass = 'status-not-found'; statusIcon = '❓';
            bannerTitle = ratingLower === 'api error' ? 'Analysis Error' : 'No Fact-Checks Found';
            confidenceBar.classList.add('medium-confidence');
        } else {
            statusClass = 'status-not-found'; statusIcon = '⚠️'; bannerTitle = 'Rating: Check Details';
            confidenceBar.classList.add('medium-confidence');
        }
    }
    
    // For simplicity, use the Gemini confidence score as the primary one for the display bar.

    // --- Update Banner ---
    banner.className = `result-banner ${statusClass}`;
    icon.textContent = statusIcon;
    statusText.textContent = bannerTitle;
    
    // Detailed subtext includes both Fact Check and Gemini Reason
    subtext.innerHTML = `
        FC Rating: <strong>${actualRating}</strong> by ${actualPublisher}. 
        <br>AI Reason: <em>${geminiReason || 'N/A (AI analysis unavailable)'}</em>
    `;

    // --- Update Confidence Score ---
    confidenceBar.style.width = `${confidence}%`;
    animateNumber(confidencePercent, Math.max(0, Math.min(100, parseInt(confidence || 0, 10))))

    // --- Update Details ---
    headlineEl.textContent = resultData.query_text || 'N/A';
    sourceEl.textContent = actualPublisher;
    domainEl.textContent = resultData.domain || 'N/A';
    try { const date = new Date(resultData.timestamp); dateEl.textContent = date.toLocaleString() || 'N/A'; }
    catch { dateEl.textContent = 'Invalid Date'; }

    if (resultData.original_url) { urlEl.textContent = resultData.original_url; urlEl.href = resultData.original_url; urlItemEl.style.display = 'block'; }
    else { urlItemEl.style.display = 'none'; }
    
    merkleHashEl.textContent = resultData.merkle_root_hash || 'N/A';
}


// --- Main script logic ---
document.addEventListener("DOMContentLoaded", function() {

    // --- Part 1: Button Click (no functional change) ---
    const analyzeButton = document.getElementById("analyze-button");
    const articleTextarea = document.getElementById("article-textarea");
    const articleUrlInput = document.getElementById("article-url-input");
    const resultsSection = document.getElementById('analysis-results-section');

    analyzeButton.addEventListener("click", function() {
        let payload = {}; let inputSource = ''; lastAnalyzedText = null;
        analyzeButton.disabled = true; analyzeButton.textContent = 'Analyzing...';
        resultsSection.style.display = 'none';

        if (currentInputMode === 'text') { /* ... handles text input ... */ } else { /* ... handles URL input ... */ }
        
        // Build payload with URL auto-detection
        let textToAnalyze; 
        if (currentInputMode === 'text') { 
            const val = (articleTextarea.value || '').trim();
            if (isProbablyUrl(val)) {
                const norm = normalizeUrl(val);
                payload = { article_url: norm };
                inputSource = norm;
                lastAnalyzedText = null; // server will return the analyzed_text
            } else {
                textToAnalyze = val;
                payload = { article_text: textToAnalyze };
                inputSource = `"${(textToAnalyze || '').substring(0, 30)}..."`;
                lastAnalyzedText = textToAnalyze;
            }
        } else { 
            const val = (articleUrlInput.value || '').trim();
            const norm = normalizeUrl(val);
            textToAnalyze = norm;
            payload = { article_url: norm };
            inputSource = norm;
        }
        
        fetch('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
        .then(response => response.ok ? response.json() : response.json().then(err => Promise.reject(err)))
        .then(data => {
            const analyzedTextFromServer = data.analyzed_text;
            const snippet = analyzedTextFromServer ? `"${analyzedTextFromServer.substring(0, 50)}..."` : inputSource;
            if (analyzedTextFromServer) lastAnalyzedText = analyzedTextFromServer; 

            if (data.status === 'queued') {
                alert(`Analysis for ${snippet} queued! Result will appear below.`);
                if (currentInputMode === 'text') articleTextarea.value = ""; else articleUrlInput.value = "";
                pollForResult(lastAnalyzedText); // Start polling
            } else if (data.status === 'duplicate') {
                alert(`${snippet} already analyzed. Result shown below.`);
                fetchAndDisplayLatestResult(lastAnalyzedText); // Show existing result
            } else if (data.status === 'error') {
                 alert("Error: " + data.message); lastAnalyzedText = null;
            }
        })
        .catch(error => { console.error("Error during analysis request:", error); alert(`Analysis request failed: ${error.message || 'Check console'}`); lastAnalyzedText = null; })
        .finally(() => { 
            analyzeButton.disabled = false;
            analyzeButton.textContent = currentInputMode === 'text' ? 'Analyze Text' : 'Analyze URL';
        });
    });

    // --- Part 2: Live Dashboard Stats (No change) ---
    function updateDashboardStats() {
        console.log("Fetching new stats...");
        fetch('/api/stats').then(response => response.json()).then(stats => {
            const totalEl = document.getElementById("total-analyzed");
            const trueEl = document.getElementById("verified-true");
            const falseEl = document.getElementById("flagged-false");
            totalEl.textContent = stats.total_analyzed !== undefined ? stats.total_analyzed : 'N/A';
            trueEl.textContent = stats.verified_true !== undefined ? stats.verified_true : 'N/A';
            falseEl.textContent = stats.flagged_false !== undefined ? stats.flagged_false : 'N/A';
            const total = stats.total_analyzed;
            if (total > 0) {
                const truePercent = ((stats.verified_true / total) * 100).toFixed(0);
                const falsePercent = ((stats.flagged_false / total) * 100).toFixed(0);
                document.querySelector('.stat-card .percentage.green').textContent = `${truePercent}% of total`;
                document.querySelector('.stat-card .percentage.red').textContent = `${falsePercent}% of total`;
            } else {
                document.querySelector('.stat-card .percentage.green').textContent = `0% of total`;
                document.querySelector('.stat-card .percentage.red').textContent = `0% of total`;
            }
        }).catch(error => console.error("Error fetching stats:", error));
    }
    updateDashboardStats();
    setInterval(updateDashboardStats, 5000);

    // --- Fetch and Display Latest Result (No change) ---
    function fetchAndDisplayLatestResult(textToMatch = null) {
        const targetText = textToMatch || lastAnalyzedText;
        if (!targetText) { console.log("No analysis text specified for result display."); return; }
        console.log(`Fetching latest result details, looking for: "${targetText.substring(0,50)}..."`);
        fetch('/api/latest_result')
        .then(response => response.ok ? response.json() : Promise.reject('Failed to fetch'))
        .then(latestResultData => {
            if (latestResultData && latestResultData.query_text === targetText) {
                 console.log("Latest result matches submitted text:", latestResultData);
                 displayAnalysisResult(latestResultData);
            } else if (latestResultData && latestResultData.status !== 'empty') {
                 console.log("Latest result in DB doesn't match submitted text. Worker might be delayed.");
                 resultsSection.style.display = 'none';
            } else {
                 console.log("No latest result found yet or DB empty.");
                 resultsSection.style.display = 'none';
            }
        })
        .catch(error => { console.error("Error fetching latest result:", error); resultsSection.style.display = 'none'; });
    }
    
    // --- Polling function for new results (No change) ---
    function pollForResult(textToMatch, attempts = 0) {
        if (!textToMatch) return;
        const maxAttempts = 5;
        const delay = 3000;
        if (attempts >= maxAttempts) {
            console.log("Polling timed out.");
            alert("Analysis is taking longer than expected. Check the History page later.");
            resultsSection.style.display = 'none';
            return;
        }

        console.log(`Polling for result attempt ${attempts + 1}...`);
        fetch('/api/latest_result')
        .then(response => response.ok ? response.json() : Promise.reject('Failed to fetch'))
        .then(latestResultData => {
            if (latestResultData && latestResultData.query_text === textToMatch) {
                console.log("Polling successful! Result found:", latestResultData);
                displayAnalysisResult(latestResultData); // Found it! Display.
            } else {
                console.log("Result not ready yet, polling again...");
                setTimeout(() => pollForResult(textToMatch, attempts + 1), delay);
            }
        })
        .catch(error => { console.error("Error during polling:", error); });
    }


    // --- Initialize UI ---
    switchTab('text');
});