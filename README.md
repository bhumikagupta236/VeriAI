🧠 VerAI — Intelligent Misinformation Detector

VerAI is an AI-powered web application designed to detect fake news and misinformation across online and social-media platforms.
Built using Python, HTML/CSS/JavaScript, and Data Structures & Algorithms (DSA) concepts such as Hash Trees and Queues, it integrates multiple news-verification APIs to ensure accuracy and reliability.

🚀 Features

🔍 Real-Time Misinformation Detection
Analyze any article, news headline, or social-media post instantly for authenticity.

🌐 API-Based Fact Verification
Uses trusted third-party APIs to validate news and flag suspicious content.

🧩 DSA-Powered Logic
Implements hash trees for quick data matching and queues for managing multiple verification requests efficiently.

💬 Social-Media Integration
Can analyze posts or shared links from major social networks.

📊 Result Classification
Displays results as True, Fake, or Unverified with probability or confidence score.

💾 Database Support (optional)
Store and retrieve previous analyses for reference.

⚙️ Tech Stack
Layer	Technology
Frontend	HTML5, CSS3, JavaScript
Backend	Python (Flask or Django)
Data Structures	Hash Tree, Queue
APIs	News Verification APIs (e.g., NewsAPI, Google Fact Check API, etc.)
Version Control	Git & GitHub
📂 Project Structure
VerAI/
│
├── static/                # CSS, JS, and image files
├── templates/             # HTML frontend templates
├── app.py                 # Flask backend application
├── verifier.py            # Core logic using DSA (hash tree, queue)
├── api_handler.py         # API integration module
├── requirements.txt       # Python dependencies
└── README.md              # Documentation

🧩 How It Works

User inputs a news headline, article, or social-media link.

The queue system manages incoming verification requests.

A hash tree compares the content against verified news databases.

APIs cross-check the information with credible news sources.

The result is displayed as True, Fake, or Unverified with explanation and sources.

🧠 Algorithms & Data Structures
Component	Description
Hash Tree	Used to hash and verify articles efficiently by comparing content fingerprints.
Queue	Handles multiple user requests concurrently in FIFO order.
String Matching	Detects similarity between user input and known verified articles.
💻 Installation & Setup
1. Clone the repository
git clone https://github.com/<your-username>/VerAI.git
cd VerAI

2. Create a virtual environment (optional)
python -m venv venv
source venv/bin/activate     # macOS/Linux
venv\Scripts\activate        # Windows

3. Install dependencies
pip install -r requirements.txt

4. Add your API keys

Create a .env file or config section in api_handler.py:

NEWS_API_KEY = "your_api_key_here"
FACT_CHECK_API_KEY = "your_api_key_here"

5. Run the app
python app.py


Then open http://localhost:5000
 in your browser.

🌈 Example Use
Input: "Government bans use of plastic nationwide starting tomorrow"
→ Checking sources...
→ Cross-verifying facts using APIs...
✅ Result: TRUE (Confirmed by Hindustan Times, Times of India)

Input: "Aliens spotted over Delhi"
→ Checking sources...
❌ Result: FAKE (No credible source found)

🔮 Future Enhancements

AI/ML model for deep-fake text and image detection

Multi-language support

Chrome extension for instant verification

Social-media API integration (Twitter/X, Reddit, etc.)

Visualization dashboard for misinformation trends
