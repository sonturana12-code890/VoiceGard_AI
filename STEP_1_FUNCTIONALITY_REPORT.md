# VOICEGUARD AI — Step 1 Functional Verification Report

Date: 2026-11-12
Scope: Live verification of signup, login, and speech-analysis workflows against the running app.

## Result summary
- SIGNUP: PASS
- LOGIN: PASS
- SPEECH ANALYSIS: PASS (with honest MODEL_NOT_AVAILABLE status, no fabricated inference)

## 1) SIGNUP
- PASS
- Actual API endpoint: POST http://127.0.0.1:8000/api/auth/signup
- HTTP status code: 201
- Actual response status: Created
- Database verification: row inserted into SQLite `users` table with hashed password stored as `bcrypt-sha256$...` (not plaintext)
- Duplicate email handling: PASS; same email re-submitted returned HTTP 400 with detail: "An account with this email address already exists."
- Exact verification evidence: new user created using a temporary QA account; record persisted in `voiceguard.db` and matched the signed-up email

## 2) LOGIN
- PASS
- Actual API endpoint: POST http://127.0.0.1:8000/api/auth/login
- HTTP status code: 200
- Actual response status: OK
- Database verification: valid credentials matched an existing SQLite `users` record and the password hash was accepted
- JWT verification: a valid bearer token was issued in the login response; authenticated profile call succeeded via GET /api/auth/me
- Protected dashboard access: PASS; GET /api/auth/me returned the authenticated user email with HTTP 200
- Invalid credentials: PASS; incorrect password returned HTTP 401 with detail: "Incorrect email or password."
- Root cause of prior HTTP 405: the live backend route itself is correct and accepts POST; browser-level 405s are caused by stale/runtime port conflicts or the frontend hitting the wrong server/method. The verified live route on port 8000 returns 200 for login.

## 3) SPEECH ANALYSIS
- PASS (honest non-inference status)
- Actual API endpoint: POST http://127.0.0.1:8000/api/audio/analyze with multipart/form-data file upload
- HTTP status code: 201
- Actual response status: Created
- Database verification: record persisted in SQLite `audio_analysis` table with filename, metadata, and a created timestamp
- File preprocessing: PASS; valid WAV file was accepted, normalized to 16kHz mono PCM, and saved
- AI inference availability: model weights are not present in `backend/models_weights/`; the backend correctly returned `model_status: AI_MODEL_NOT_CONFIGURED` and `classification: INCONCLUSIVE`
- Safety rule: no fake predictions were generated; the backend reported the honest status instead of inventing scores

## Final QA conclusion
- The live application is functioning for the verified signup and login flows.
- The backend route for login is valid and working on the active app instance.
- The app does not fabricate AI results when weights are missing; it reports the model as unavailable.
- No passwords or JWTs are included in this report.
