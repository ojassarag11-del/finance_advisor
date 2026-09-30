# Personal Finance Advisor Bot
Flask + SQLAlchemy (SQLite) + Gemini + JavaScript.

## Run
    python -m venv venv
    source venv/bin/activate        # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env            # add GEMINI_API_KEY (optional; falls back to rule-based advice)
    python app.py
Open http://127.0.0.1:5000

## Antigravity
Open this folder in Google Antigravity, then ask the agent: "Run the Flask app and open it in the browser."
