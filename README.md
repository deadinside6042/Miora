# Miora — Android wellness companion

Miora is an original Omna-inspired Android wellness app starter with a working AI chat backend, mood check-ins, and a private on-device journal.

## Included
- Native Android app built with Kotlin + Jetpack Compose
- Home dashboard and bottom navigation
- Mood check-in (saved locally)
- Journal (saved locally; journal text is not sent to the AI)
- AI companion connected to a FastAPI backend
- AI safety boundaries in the backend prompt
- No API key embedded in the Android app

## Requirements
- Android Studio (recent stable release)
- JDK 17
- Android SDK 35
- Python 3.10+ for the backend
- An OpenAI API key for AI chat

## Run the backend
```bash
cd backend
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
# Edit backend/.env and set OPENAI_API_KEY
uvicorn main:app --host 0.0.0.0 --port 8000
```

The backend health check is `http://localhost:8000/health`.

## Run the Android app
1. Open this project folder in Android Studio.
2. Let Gradle sync.
3. Start the backend.
4. Run the `app` configuration on an Android emulator.

The default `AI_BASE_URL` is `http://10.0.2.2:8000/`, which reaches your development computer from the standard Android emulator.

For a physical Android phone, change `AI_BASE_URL` in `app/build.gradle.kts` to your computer's LAN IP, for example `http://192.168.1.20:8000/`, and ensure the phone and computer are on the same network. This cleartext HTTP setup is for local development only.

## Production checklist — required before release
- Deploy the API behind HTTPS.
- Restrict CORS and add authentication, per-user rate limits, abuse controls, and request logging that excludes sensitive message content.
- Store secrets in a server-side secret manager; never put an OpenAI key in the APK.
- Add a privacy policy, consent and data-retention controls, account deletion if accounts are introduced, and an appropriate age rating.
- Review crisis-support wording and local resources for every launch market.
- Add automated tests, accessibility checks, crash reporting with privacy safeguards, and Play Console disclosures.
- Consider encrypted local storage and an optional app lock before storing sensitive journal entries on real user devices.

## Important
Miora is a wellness reflection tool, not a medical device, therapist, or emergency service. AI responses can be wrong. This starter is not yet a production-audited mental-health product.
