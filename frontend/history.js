document.addEventListener("DOMContentLoaded", function() {

    const historyList = document.getElementById("history-list");
    const searchInput = document.getElementById("search-input");
    const statusFilter = document.getElementById("status-filter");
    let allHistoryData = []; // Store all data to allow filtering without re-fetching

    // --- Constants for ratings ---
    const FALSE_RATINGS_JS = ['false', 'pants on fire', 'mostly false', 'scam', 'fake', 'misleading'];
    const TRUE_RATINGS_JS = ['true', 'mostly true', 'correct attribution'];

    // --- Helper functions ---
    function isFalseRating(rating) { return rating && FALSE_RATINGS_JS.includes(rating.toLowerCase()); }
    function isTrueRating(rating) { return rating && TRUE_RATINGS_JS.includes(rating.toLowerCase()); }

    // --- Function to render the history list based on filters ---
    function renderHistory(dataToRender) {
        historyList.innerHTML = ""; // Clear previous items

        if (dataToRender.length === 0) { historyList.innerHTML = "<p>No matching analysis history found.</p>"; return; }

        dataToRender.forEach(item => {
            const card = document.createElement('div'); card.className = 'history-card';
            const date = new Date(item.timestamp);
            const formattedDate = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();

            // Prefer server-side final_verdict for status
            const finalVerdict = item.final_verdict || '';
            let statusClass = 'not-found';
            let cardStatusClass = 'status-not-found';
            let statusText = 'Inconclusive';

            if (finalVerdict === 'VERIFIED_TRUE') {
                statusClass = 'verified'; cardStatusClass = 'status-verified'; statusText = 'Verified True';
            } else if (finalVerdict === 'FLAGGED_FALSE') {
                statusClass = 'false'; cardStatusClass = 'status-false'; statusText = 'Flagged False';
            } else {
                // Fallback to Fact Check rating buckets
                const actualRating = item.rating ? item.rating : 'N/A';
                const ratingLower = actualRating.toLowerCase();
                statusText = actualRating;
                if (statusText.length > 30) { statusText = statusText.substring(0, 27) + '...'; }
                if (isTrueRating(ratingLower)) { statusClass = 'verified'; cardStatusClass = 'status-verified'; statusText = 'Verified True'; }
                else if (isFalseRating(ratingLower)) { statusClass = 'false'; cardStatusClass = 'status-false'; statusText = 'Flagged False'; }
                else if (ratingLower === 'api error') { statusClass = 'not-found'; cardStatusClass = 'status-not-found'; statusText = 'API Error'; }
                else { statusClass = 'not-found'; cardStatusClass = 'status-not-found'; statusText = 'Inconclusive'; }
            }

            card.classList.add(cardStatusClass);
            const shortHash = item.merkle_root_hash ? item.merkle_root_hash.substring(0, 16) : 'N/A';
            
            // --- NEW GEMINI DISPLAY ---
            const geminiFlag = item.gemini_flag;
            const geminiConf = item.gemini_confidence;
            let aiFlagHtml = '';
            
            if (geminiConf !== null && geminiConf !== undefined) {
                const aiFlagText = (geminiFlag === 1 || geminiFlag === true)
                    ? 'AI: Misleading'
                    : (geminiFlag === 0 || geminiFlag === false)
                        ? 'AI: Credible'
                        : 'AI: Unsure';
                aiFlagHtml = `
                    <span class="status-badge" style="background-color: var(--card-color); color: var(--text-muted); border-color: var(--border-color);" title="AI Confidence: ${geminiConf}%">
                        ${aiFlagText} (${geminiConf}%)
                    </span>
                `;
            }
            // --- END NEW GEMINI DISPLAY ---
            
            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="status-badge ${statusClass}">${statusText}</span>
                    <div style="margin-left: 10px; flex-shrink: 0;">${aiFlagHtml}</div>
                </div>
                <h3>${item.query_text || 'N/A'}</h3>
                <p class="details">Publisher: ${item.publisher || 'N/A'} | Analyzed: ${formattedDate}</p>
                <p class="details">Domain: ${item.domain || 'N/A'} | URL: ${item.original_url ? `<a href="${item.original_url}" target="_blank" rel="noopener noreferrer">Link</a>` : 'N/A'}</p>
                <p class="hash">Merkle Hash: ${shortHash}${item.merkle_root_hash ? '...' : ''}</p>
            `;
            historyList.appendChild(card);
        });
    }

    function applyFilters() {
        // ... (applyFilters logic remains the same) ...
        const searchTerm = searchInput.value.toLowerCase();
        const statusValue = statusFilter.value;
        const filteredData = allHistoryData.filter(item => {
            const textMatch = (item.query_text || '').toLowerCase().includes(searchTerm);
            const verdict = item.final_verdict || '';
            const ratingLower = (item.rating || '').toLowerCase();
            let statusMatch = true;
            if (statusValue === 'true') {
                statusMatch = verdict === 'VERIFIED_TRUE' || isTrueRating(ratingLower);
            } else if (statusValue === 'false') {
                statusMatch = verdict === 'FLAGGED_FALSE' || isFalseRating(ratingLower);
            } else if (statusValue === 'not-found') {
                statusMatch = !(verdict === 'VERIFIED_TRUE' || verdict === 'FLAGGED_FALSE' || isTrueRating(ratingLower) || isFalseRating(ratingLower));
            }
            return textMatch && statusMatch;
        });
        renderHistory(filteredData);
    }

    function loadHistory() {
        // ... (loadHistory logic remains the same) ...
        console.log("Fetching history..."); historyList.innerHTML = "<p>Loading...</p>";
        fetch('/api/history')
            .then(response => response.ok ? response.json() : Promise.reject(`HTTP error ${response.status}`))
            .then(data => {
                if (!Array.isArray(data)) throw new Error("Invalid data format.");
                allHistoryData = data; applyFilters();
            })
            .catch(error => { console.error("Error loading history:", error); historyList.innerHTML = `<p>Error: ${error}.</p>`; });
    }

    // --- Event Listeners and Initial Load (Same as before) ---
    searchInput.addEventListener('input', applyFilters);
    statusFilter.addEventListener('change', applyFilters);
    // Export button listener (same as before)
    const exportButton = document.getElementById('export-button');
    if (exportButton) { exportButton.addEventListener('click', () => { /* ... export logic ... */ }); }

    // Clear history button
    const clearButton = document.getElementById('clear-button');
    if (clearButton) {
        clearButton.addEventListener('click', () => {
            if (!confirm('This will remove all saved analyses. Continue?')) return;
            fetch('/api/clear_history', { method: 'POST' })
                .then(resp => resp.ok ? resp.json() : resp.json().then(e => Promise.reject(e)))
                .then(() => { allHistoryData = []; historyList.innerHTML = '<p>History cleared.</p>'; })
                .catch(err => { console.error('Failed to clear history', err); alert('Failed to clear history'); });
        });
    }

    loadHistory();
});
