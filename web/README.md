# Miora iPhone web client

A responsive, installable static web client for the existing Miora API.

## API
- Login: POST /auth/login
- Refresh: POST /auth/refresh
- Profile: GET /profile
- History: GET /conversations/{id}/messages
- Chat: POST /chat

The client does not expose Supabase or OpenRouter credentials. It uses the existing authenticated API and stores only the user's session tokens and active conversation ID in that browser's local storage. It does not store conversation content offline.

## Render Static Site
- Repository: deadinside6042/Miora
- Branch: feature/iphone-web-client (for preview), then main after merge
- Root directory: web
- Build command: echo "Static Miora web client"
- Publish directory: .
- URL: public HTTPS Render static-site URL

On iPhone, open the URL in Safari, sign in with the invited account, then Share > Add to Home Screen.
