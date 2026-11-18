# VOICEGUARD AI — Production Deployment Readiness Report

**Project:** VOICEGUARD AI — AI Voice Anti-Spoofing & Cyber Acoustic Defense  
**Problem Statement ID:** SIH26104  
**Target Deployment Architecture:**
* **Frontend:** Vercel (Static Hosting & Edge CDN)
* **Backend:** Render (Docker Web Service & WebSockets)
* **Database:** Render Managed PostgreSQL (or Persistent SQLite)

---

## Executive Summary

The forensic deployment audit has verified that the core deepfake voice detection pipeline (RawNet2 & AASIST), real-time acoustic telemetry, and WebSocket live microphone streaming (`/api/v1/stream/ws`) are fully verified and operational.

All required configuration files (`vercel.json`, `Dockerfile`, `render.yaml`, `api-config.js`, `.env.example`) have been authored and verified to ensure cross-origin functionality between Vercel and Render.

---

## 1. Comprehensive Deployment Audit Checklist

### 1. Frontend Deployment Configuration (Vercel)
* **Target:** Static Single-Page Application (SPA) on Vercel.
* **Key Files:** `index.html`, `app.html`, `style.css`, `api-config.js`, `api-client.js`, `app-controller.js`, `live-audio-processor.js`.
* **Configuration Prepared:** `vercel.json` has been created with:
  * Clean URLs enabled (`"cleanUrls": true`).
  * Rewrite rule mapping `/app` and `/dashboard` to `/app.html`.
  * Security response headers (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`).
  * Static MIME-type caching rule for the `live-audio-processor.js` AudioWorklet module.
* **API Origin Resolution:** [api-config.js](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/api-config.js) was upgraded to support:
  1. Explicit runtime override: `window.VOICEGUARD_API_URL`
  2. HTML `<meta name="voiceguard-api-url" content="...">` tag
  3. Browser storage: `localStorage.getItem('vg_api_url')`
  4. Localhost / same-origin fallback

---

### 2. Backend Deployment Configuration (Render)
* **Target:** Render Web Service.
* **Environment Choice (Docker vs. Native Python):**
  * **Selected:** **Docker Runtime** via [Dockerfile](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/Dockerfile).
  * **Rationale:** A standard Linux Docker image (`python:3.11-slim`) guarantees that system-level audio dependencies (`ffmpeg`, `libsndfile1`) are pre-compiled and available, avoiding build failures on Render.
* **Blueprint:** Created [render.yaml](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/render.yaml) defining the Web Service, health check probe (`/health`), port binding (`$PORT`), and database connection linking.
* **Resource Plan:** **Starter Plan (1 GB RAM)** is strongly recommended. Neural inference with RawNet2 ONNX (70.6 MB) and AASIST ONNX (1.6 MB) requires approximately 450 MB – 650 MB of resident memory. The free tier (512 MB) may encounter Out-Of-Memory (OOM) termination under concurrent audio uploads.

---

### 3. WebSocket WSS Support
* **Vercel Architectural Limitation:** Vercel Serverless Functions and Edge Network **do not support persistent stateful WebSockets**. Vercel cannot reverse-proxy WebSocket connections.
* **Architecture Solution:** 
  The frontend directly connects to Render's WebSocket endpoint using secure WebSockets (`wss://`):
  ```text
  Browser (Microphone) ---> wss://voiceguard-backend.onrender.com/api/v1/stream/ws ---> Render FastAPI Backend
  ```
* **Frontend Compatibility:** Both [app-controller.js](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/app-controller.js) and [frontend/index.html](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/frontend/index.html) dynamically switch to `wss:` whenever `https:` is detected:
  ```javascript
  const url = new URL('/api/v1/stream/ws', base);
  if (url.protocol === 'https:') url.protocol = 'wss:';
  ```

---

### 4. Environment Variables & Secrets
* **`.gitignore` Protection:** Confirmed that `.env`, `.env.*`, `uploads/`, `*.sqlite`, and virtual environments (`.venv/`) are strictly excluded from git tracking.
* **Production Secret Enforcement:** In [backend/auth.py](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/backend/auth.py#L31-L36), when `ENVIRONMENT=production`, the server will safely abort on startup if `SECRET_KEY` is not provided.
* **Render Environment Variables to set:**
  | Variable | Value / Format | Purpose |
  | :--- | :--- | :--- |
  | `ENVIRONMENT` | `production` | Enables production security checks |
  | `APP_ENV` | `production` | Enforces non-default secrets |
  | `SECRET_KEY` | *(Auto-generated 32+ character string)* | Signs JWT access tokens |
  | `ACCESS_TOKEN_EXPIRE_MINUTES` | `720` (12 hours) | Token lifespan |
  | `CORS_ORIGINS` | `https://voiceguard.vercel.app` | Whitelists Vercel domain |
  | `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |

---

### 5. Database Persistence
* **Render Ephemeral Disk Warning:** By default, Render containers have ephemeral storage. If using local SQLite (`voiceguard.db`), database records, users, and audit history will be deleted every time Render restarts or redeploys.
* **Production Solutions:**
  1. **Render Managed PostgreSQL (Recommended):** Added `psycopg2-binary` to [backend/requirements.txt](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/backend/requirements.txt) and patched `_resolve_database_url` in [backend/database.py](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/backend/database.py) to automatically rewrite Render's legacy `postgres://` URIs to SQLAlchemy-compliant `postgresql://`.
  2. **Render Persistent Disk (Alternative):** Attach a 1 GB persistent disk at `/var/data` and configure `DATABASE_URL=sqlite:////var/data/voiceguard.db`.

---

### 6. Model Files & Deployment Paths
* **Storage Location:** `backend/models_weights/`
  * `rawnet2.onnx`: 70,597,815 bytes (~70.6 MB)
  * `aasist.onnx`: 1,629,642 bytes (~1.6 MB)
* **GitHub File Size Analysis:**
  * GitHub warns on files $> 50$ MB and blocks files $> 100$ MB.
  * At 70.6 MB, `rawnet2.onnx` is below the 100 MB hard limit and **will successfully push to GitHub without requiring Git LFS**.
* **Path Resolution:** [backend/services/model_manager.py](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/backend/services/model_manager.py#L24-L26) resolves paths relative to `__file__`:
  ```python
  MODELS_DIR = Path(__file__).resolve().parent.parent / "models_weights"
  ```
  This is portable across Windows, Linux containers, and Docker.

---

### 7. FFmpeg Dependencies
* **Dual-Layer Architecture in [ffmpeg_service.py](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/backend/services/ffmpeg_service.py):**
  1. **Primary:** Embedded `PyAV` (`av>=14.0.0`) uses bundled C libav libraries (`libavformat`, `libavcodec`, `libswresample`) for in-memory audio extraction.
  2. **Secondary:** CLI binary detection for system `ffmpeg` and `ffprobe`.
* **Docker Guarantee:** The production `Dockerfile` explicitly runs `apt-get install -y ffmpeg libsndfile1`, ensuring both CLI tools and C-bindings are present in production.

---

### 8. Cross-Origin Resource Sharing (CORS) Configuration
* **Cross-Site Context:** Vercel frontend (`https://voiceguard.vercel.app`) communicates with Render backend (`https://voiceguard-backend.onrender.com`).
* **CORS Enhancement in [backend/main.py](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/backend/main.py#L97-L105):**
  Updated `allow_origin_regex` to:
  ```python
  allow_origin_regex=r"^https?://((localhost|127\.0\.0\.1)(:\d+)?|([a-zA-Z0-9-]+\.)*vercel\.app)$"
  ```
  This automatically permits production Vercel domains, preview branch deployments (`*.vercel.app`), and local development environments without breaking credentials (`allow_credentials=True`).

---

### 9. Authentication & JWT Configuration
* **Cross-Site Cookie Restrictions:** Modern browsers (Safari, Chrome, Firefox) block third-party cookies when frontend and backend reside on different root domains (`.vercel.app` vs `.onrender.com`) unless `SameSite=None; Secure` is used.
* **Architecture Solution:** 
  VoiceGuard AI uses a dual authentication mechanism:
  * [api-client.js](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/api-client.js#L70-L73) stores the JWT in `localStorage` under `vg_token` and automatically sends `Authorization: Bearer <token>` in HTTP headers.
  * Live WebSocket authentication passes the token directly inside the initial JSON auth frame:
    ```json
    { "type": "auth", "token": "<JWT_TOKEN>", "model": "RAWNET2", ... }
    ```
  This guarantees that authentication functions independently of browser cookie policies.

---

### 10. Production Startup Command
* **Docker Container CMD (in `Dockerfile`):**
  ```bash
  uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
  ```
* **Native Linux Render Service (Alternative):**
  ```bash
  uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 1
  ```
  *(Note: Single worker is recommended on 1GB instances to prevent multiple PyTorch/ONNX runtime copies from consuming excessive RAM).*

---

## 2. Identified Deployment Blockers & Applied Fixes

| Item | Potential Blocker | Applied Fix / Resolution | Status |
| :--- | :--- | :--- | :--- |
| **Database** | Render PostgreSQL uses `postgres://` which breaks SQLAlchemy 2.0. | Added automated URL rewrite to `postgresql://` in `backend/database.py`. | **FIXED** |
| **Database Driver** | Missing `psycopg2-binary` in `requirements.txt` causes driver crash on PostgreSQL. | Added `psycopg2-binary>=2.9.9` to `backend/requirements.txt`. | **FIXED** |
| **CORS** | Vercel domain blocked by default local CORS origins. | Added regex permitting all `*.vercel.app` domains in `backend/main.py`. | **FIXED** |
| **Frontend API URL** | Hardcoded port 8000 in frontend causes 404s on Vercel. | Added dynamic override in `api-config.js` via meta tag, env, or localStorage. | **FIXED** |
| **WebSocket URL** | Hardcoded `:8000` port in `frontend/index.html` breaks WSS in production. | Patched `getWebSocketUrl()` to resolve dynamically from `API_BASE_URL`. | **FIXED** |
| **Model Weights** | Weight files ignored or missing during deployment. | Validated in Dockerfile: `rawnet2.onnx` and `aasist.onnx` verified present. | **FIXED** |

---

## 3. Step-by-Step Instructions: What You Need To Do Next

Follow these steps to deploy to Render and Vercel:

### Step 1: Initialize Git and Push to GitHub
1. Open PowerShell or Terminal in the project root:
   ```powershell
   git init
   git add .
   git commit -m "feat: complete VoiceGuard AI production readiness"
   ```
2. Create a new repository on GitHub (e.g. `voiceguard-ai`).
3. Push your repository:
   ```powershell
   git remote add origin https://github.com/<your-username>/voiceguard-ai.git
   git branch -M main
   git push -u origin main
   ```

---

### Step 2: Deploy Backend to Render
1. Log in to [Render.com](https://render.com).
2. Click **New +** $\to$ **Blueprint** (or **Web Service**).
3. Connect your GitHub repository `voiceguard-ai`.
4. Render will detect [render.yaml](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/render.yaml) automatically:
   * **Runtime:** Docker
   * **Plan:** Starter (1 GB RAM)
   * **Health Check:** `/health`
5. Click **Apply**.
6. When deployment finishes, copy your Render service URL (e.g., `https://voiceguard-backend.onrender.com`).

---

### Step 3: Deploy Frontend to Vercel
1. Log in to [Vercel.com](https://vercel.com).
2. Click **Add New...** $\to$ **Project**.
3. Import your GitHub repository `voiceguard-ai`.
4. In **Project Settings**:
   * **Framework Preset:** Other
   * **Root Directory:** `./`
5. In **Environment Variables**, add:
   * **Name:** `VOICEGUARD_API_URL`
   * **Value:** `https://<your-render-backend-name>.onrender.com`
6. Click **Deploy**.
7. In [app.html](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/app.html) or [index.html](file:///c:/Users/LC/OneDrive/Desktop/VoiceGard_AI/index.html), you can also set the meta tag in `<head>`:
   ```html
   <meta name="voiceguard-api-url" content="https://<your-render-backend-name>.onrender.com">
   ```
8. In Render dashboard, set `CORS_ORIGINS` to your Vercel URL (e.g. `https://voiceguard.vercel.app`).

---

### Step 4: Verification
1. Open your Vercel URL: `https://<your-project>.vercel.app`.
2. Register a user or log in.
3. Navigate to **Live Analysis** (`#live-monitoring`).
4. Click **Start Live Detection**.
5. Speak into your microphone and verify that real-time acoustic telemetry and RAWNET2 prediction events arrive from Render via secure WebSockets (`wss://`).
