# VoiceGuard AI — Local Development

## Requirements

- Node.js 22.13 or newer (the server uses Node's built-in `node:sqlite` module)
- A current browser; the 3D scene uses Three.js from CDN and has a CSS fallback

## Start the application

From the project directory:

```powershell
npm start
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). Do not open `index.html` directly or use VS Code Live Server: authentication and protected application routing require the Node server.

Create an account from the landing page. Passwords are hashed with scrypt; account records and hashed session tokens are stored in `.data\voiceguard.sqlite`. The database is ignored by Git. `Remember me` creates a 30-day session; otherwise the session cookie lasts until the browser closes and the server expires the session within 12 hours.

## Pages

- Public landing page, sign in, and sign up
- Protected dashboard, voice analysis, speaker verification, live monitoring, threat intelligence, fraud-prevention workflows, reports, profile, and settings
- The overview has its own animated core; the remaining views reuse one low-power, page-specific 3D renderer that pauses when hidden or off-screen. Scenes are decorative, with CSS fallback and reduced-motion support.
- Existing preset results and sample incidents are labeled as demonstrations
- Uploaded and microphone audio can be played/visualized locally; it is not sent to an AI service

## Backend boundaries

This project originally contained no API server, database, authentication provider, or AI inference endpoint. The local server added here implements account registration, login/logout, profile editing, password changes, session-protected `/app` routes, and a health endpoint. It does **not** implement voice inference, biometric speaker verification, email/password recovery, OAuth, notification delivery, or real transaction/MFA actions.

To connect inference, provide the real service endpoint, authentication method, upload contract, and response schema. Do not treat preset results, sample charts, monitoring visuals, or workflow previews as production decisions.

## Configuration and deployment

- `PORT` changes the local HTTP port; `HOST` defaults to `127.0.0.1`.
- `VOICEGUARD_DATA_DIR` or `VOICEGUARD_DB_PATH` changes the local SQLite location.
- `VOICEGUARD_ALLOWED_HOSTS` is a comma-separated host-name allowlist. Add the exact deployment host if hosting the service.
- The default server is intentionally loopback-only and plain HTTP. Do **not** expose it to a network or deploy it as-is. A production deployment needs HTTPS termination that sets secure cookies, a reviewed privacy/terms policy, account recovery and email verification, operational rate limiting, database backup/migration procedures, and a managed security review.
- Google sign-in is omitted because OAuth credentials and callback configuration were not supplied.

## Checks

```powershell
npm run check
```

The check verifies JavaScript syntax. No AI integration tests are possible until an inference backend is configured.
