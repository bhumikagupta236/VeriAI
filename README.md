# VeriAI

AI-powered fact-checking and misinformation detection tool.

## Quick Start

Only 2 commands needed to run the project:

```powershell
# 1. First time setup (or after pulling updates)
.\run.ps1

# 2. That's it! The script handles everything:
#    - Creates virtual environment if needed
#    - Installs all dependencies
#    - Starts the application
```

The application will be available at `http://localhost:5001`

## What Gets Installed

- Flask (web framework)
- Requests (HTTP library)
- Google GenAI (Gemini API)

## Requirements

- Python 3.7+
- PowerShell (Windows)

## Configuration

Make sure to set up your API keys in `backend/config.py` or as environment variables:
- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`
- `NEWS_API_KEY` (optional)
- `GNEWS_API_KEY` (optional)
