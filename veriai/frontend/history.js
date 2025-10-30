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

            let statusClass = 'not-found'; let cardStatusClass = 'status-not-found';
            let actualRating = item.rating ? item.rating : 'N/A';
            const ratingLower = actualRating.toLowerCase();

            // Truncate long ratings for the badge
            let statusText = actualRating;
            if (statusText.length > 30) { statusText = statusText.substring(0, 27) + "..."; }

            // Determine badge/border color based on Fact Check API result
            if (isTrueRating(ratingLower)) { statusClass = 'verified'; cardStatusClass = 'status-verified'; }
            else if (isFalseRating(ratingLower)) { statusClass = 'false'; cardStatusClass = 'status-false'; }
            else if (ratingLower === 'api error'){ statusClass = 'not-found'; cardStatusClass = 'status-error'; statusText = 'API Error'; }
            
            card.classList.add(cardStatusClass);
            const shortHash = item.merkle_root_hash ? item.merkle_root_hash.substring(0, 16) : 'N/A';
            
            // --- NEW GEMINI DISPLAY ---
            const geminiFlag = item.gemini_flag;
            const geminiConf = item.gemini_confidence;
            let aiFlagHtml = '';
            
            if (geminiConf !== null) {
                let aiFlagText = '';
                let aiFlagColor = '';
                if (geminiFlag === 1) { // SQLite stores true as 1
                    aiFlagText = 'Misleading';
                    aiFlagColor = 'red';
                } else if (geminiFlag === 0) { // SQLite stores false as 0
                    aiFlagText = 'Verified by AI';
                    aiFlagColor = 'green';
                } else {
                    aiFlagText = 'AI Unsure';
                    aiFlagColor = 'muted';
                }
                
                aiFlagHtml = `
                    <span class="status-badge" style="background-color: var(--card-color); color: var(--text-muted); border-color: var(--border-color);" title="AI Confidence: ${geminiConf}%">
                        ${aiFlagText} (${geminiConf}%)
                    </span>
                `;
            }
            // --- END NEW GEMINI DISPLAY ---
            
            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="status-badge ${statusClass}" title="${actualRating}">${statusText}</span>
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
            const textMatch = item.query_text && item.query_text.toLowerCase().includes(searchTerm);
            let statusMatch = true;
            const ratingLower = item.rating ? item.rating.toLowerCase() : '';
            if (statusValue === 'true') statusMatch = isTrueRating(ratingLower);
            else if (statusValue === 'false') statusMatch = isFalseRating(ratingLower);
            else if (statusValue === 'not-found') statusMatch = !isTrueRating(ratingLower) && !isFalseRating(ratingLower);
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

    loadHistory();
});