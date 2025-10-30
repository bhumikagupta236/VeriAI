🧠 VerAI — The Misinformation Detector

VerAI (Verify + AI) is a beginner-friendly web project that detects fake or misleading news on the internet and social media.
It combines the power of Python, APIs, and Data Structures (like Hash Trees and Queues) to make the web a more truthful place.

🌍 Overview

VerAI is a web-based misinformation detection system that helps users identify fake news or unreliable posts.
The project demonstrates how core DSA concepts can be applied in real-world software with simple, beginner-friendly logic.

It:

Fetches news or posts from social media using APIs

Uses Hash Trees to ensure data integrity

Uses Queue structures to handle multiple fact-checks

Compares results with trusted fact-checking APIs to display credibility

🧩 Tech Stack
Layer	Technology
Frontend	HTML, CSS, JavaScript
Backend	Python (Flask or FastAPI)
APIs	Google Fact Check API, News API, Fakebox API
Database (optional)	Firebase / SQLite
DSA Concepts Used	Hash Tree, Queue, Hash Map
Version Control	Git & GitHub
⚙️ Key Features

✅ Detects fake or misleading news
✅ Shows credibility score and fact-checked summary
✅ Uses Hash Trees for verifying data consistency
✅ Processes multiple fact-checks via Queue
✅ Integrates fact-checking APIs for real results
✅ Clean, responsive web interface
✅ Beginner-friendly code and structure

🧭 Roadmap (Beginner-Friendly Phases)
Phase 1 — Setup & Planning

Install Python, Git, and VS Code

Create a new folder and initialize Git (git init)

Plan features and API endpoints

Create HTML skeleton for UI

Phase 2 — Frontend Development

Build index.html with an input box for news/posts

Add CSS for layout and styling

Write JavaScript to send user input to backend (via Fetch API or Axios)

Phase 3 — Backend Development

Create a Flask app (app.py)

Build routes like /check_news and /verify_source

Implement Queue for multiple requests

Implement Hash Tree for trusted source storage

Phase 4 — API Integration

Connect to:

Google Fact Check API (for real-world news verification)

News API (for trending topics comparison)

Parse and return verification results

Phase 5 — Result Analysis

Show results in frontend:

✅ Real News (green)

⚠️ Unverified (yellow)

❌ Fake News (red)

Add confidence score and verified sources

Phase 6 — Final Touches

Add logos, animations, or background theme

Test the workflow

Push to GitHub (git add ., git commit -m "Initial VerAI build", git push)

🧠 DSA Integration Explained
Concept	Use in Project
Hash Tree	Store and verify integrity of trusted sources. Each new article is hashed and checked against source nodes.
Queue	Manage incoming verification requests in order.
Hash Map	Quickly match URLs or post IDs to existing verified data.
🔑 APIs You Can Use

Google Fact Check Tools API

News API

Fakebox API

Mediastack API

These help fetch real-time articles and credibility scores.

🧰 Installation
# Clone this repository
git clone https://github.com/yourusername/verai.git

# Move into folder
cd verai

# Install dependencies
pip install flask requests

# Run the app
python app.py


Then open http://localhost:5000 in your browser 🎉

💡 Future Enhancements

Add browser extension to auto-check fake news

Integrate AI/NLP models (like BERT or DistilBERT) later

Build user dashboard and history tracker

Real-time Twitter/X feed analysis

🤝 Contributing

Want to improve VerAI?

Fork the repo

Create a new branch (feature/add-new-api)

Commit your changes

Open a pull request

🪪 License

This project is licensed under the MIT License — free to use, modify, and learn from.

✨ Made With

💻 Python | 🧮 DSA | 🌐 HTML, CSS, JS | 🔍 APIs
