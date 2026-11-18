'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { promisify } = require('node:util');
const { DatabaseSync } = require('node:sqlite');

const scrypt = promisify(crypto.scrypt);
const ROOT = __dirname;
const DATA_DIR = process.env.VOICEGUARD_DATA_DIR || path.join(ROOT, '.data');
const DATABASE_PATH = process.env.VOICEGUARD_DB_PATH || path.join(DATA_DIR, 'voiceguard.sqlite');
const PORT = Number(process.env.PORT || 3000);
const HOST = process.env.HOST || '127.0.0.1';
if (!Number.isInteger(PORT) || PORT < 1 || PORT > 65535) {
    throw new Error('PORT must be an integer between 1 and 65535.');
}
const SESSION_COOKIE = 'vg_session';
const SESSION_TTL_MS = 12 * 60 * 60 * 1000;
const REMEMBERED_SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000;
const PASSWORD_KEY_LENGTH = 64;
const PASSWORD_SCRYPT_OPTIONS = { N: 32768, r: 8, p: 1, maxmem: 128 * 1024 * 1024 };
const allowedHosts = new Set(
    (process.env.VOICEGUARD_ALLOWED_HOSTS || 'localhost,127.0.0.1,::1,[::1]')
        .split(',')
        .map(host => host.trim().toLowerCase())
        .filter(Boolean)
);

fs.mkdirSync(path.dirname(DATABASE_PATH), { recursive: true });
const database = new DatabaseSync(DATABASE_PATH);
database.exec(`
    PRAGMA foreign_keys = ON;
    PRAGMA journal_mode = WAL;
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at INTEGER NOT NULL,
        created_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
`);

const rateLimits = new Map();
const sessionCleanup = setInterval(() => {
    database.prepare('DELETE FROM sessions WHERE expires_at <= ?').run(Date.now());
    for (const [key, entry] of rateLimits) {
        if (entry.resetAt <= Date.now()) rateLimits.delete(key);
    }
}, 5 * 60 * 1000);
sessionCleanup.unref();
const dummySalt = crypto.randomBytes(16);
const staticFiles = new Map([
    ['/index.html', ['index.html', 'text/html; charset=utf-8']],
    ['/app.html', ['app.html', 'text/html; charset=utf-8']],
    ['/style.css', ['style.css', 'text/css; charset=utf-8']],
    ['/script.js', ['script.js', 'text/javascript; charset=utf-8']],
    ['/auth-client.js', ['auth-client.js', 'text/javascript; charset=utf-8']],
    ['/app-auth.js', ['app-auth.js', 'text/javascript; charset=utf-8']],
    ['/workspace.js', ['workspace.js', 'text/javascript; charset=utf-8']],
    ['/landing.js', ['landing.js', 'text/javascript; charset=utf-8']],
    ['/workspace-scenes.js', ['workspace-scenes.js', 'text/javascript; charset=utf-8']],
    ['/animations-3d.js', ['animations-3d.js', 'text/javascript; charset=utf-8']],
    ['/animations-integration.js', ['animations-integration.js', 'text/javascript; charset=utf-8']]
]);

function sendJson(response, status, value, headers = {}) {
    response.writeHead(status, {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
        ...headers
    });
    response.end(JSON.stringify(value));
}

function setSecurityHeaders(response) {
    response.setHeader('X-Content-Type-Options', 'nosniff');
    response.setHeader('X-Frame-Options', 'DENY');
    response.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
    response.setHeader('Permissions-Policy', 'camera=(), geolocation=(), payment=()');
    response.setHeader(
        'Content-Security-Policy',
        "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    );
}

function requestHostAllowed(request) {
    const header = request.headers.host;
    if (!header) return false;
    try {
        return allowedHosts.has(new URL(`http://${header}`).hostname.toLowerCase());
    } catch {
        return false;
    }
}

function isSameOrigin(request) {
    const origin = request.headers.origin;
    if (typeof origin !== 'string' || !request.headers.host) return false;
    try {
        const parsed = new URL(origin);
        return (parsed.protocol === 'http:' || parsed.protocol === 'https:') &&
            parsed.host.toLowerCase() === request.headers.host.toLowerCase();
    } catch {
        return false;
    }
}

function parseCookies(header = '') {
    const result = new Map();
    for (const part of header.split(';')) {
        const separator = part.indexOf('=');
        if (separator <= 0) continue;
        result.set(part.slice(0, separator).trim(), part.slice(separator + 1).trim());
    }
    return result;
}

function cookieHeader(request, token, maxAgeSeconds) {
    const secure = request.socket.encrypted ? '; Secure' : '';
    const age = Number.isFinite(maxAgeSeconds) ? `; Max-Age=${maxAgeSeconds}` : '';
    return `${SESSION_COOKIE}=${token}; Path=/; HttpOnly; SameSite=Lax${age}${secure}`;
}

function hashToken(token) {
    return crypto.createHash('sha256').update(token).digest('hex');
}

function getSession(request) {
    const token = parseCookies(request.headers.cookie).get(SESSION_COOKIE);
    if (!token || !/^[A-Za-z0-9_-]{40,60}$/.test(token)) return null;
    const tokenHash = hashToken(token);
    const row = database.prepare(`
        SELECT users.id, users.full_name, users.email, sessions.expires_at
        FROM sessions JOIN users ON users.id = sessions.user_id
        WHERE sessions.token_hash = ? AND sessions.expires_at > ?
    `).get(tokenHash, Date.now());
    if (!row) return null;
    return { ...row, tokenHash };
}

function createSession(request, response, userId, remembered = false) {
    const token = crypto.randomBytes(32).toString('base64url');
    const now = Date.now();
    const ttl = remembered ? REMEMBERED_SESSION_TTL_MS : SESSION_TTL_MS;
    database.prepare('INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)')
        .run(hashToken(token), userId, now + ttl, now);
    response.setHeader('Set-Cookie', cookieHeader(request, token, remembered ? Math.floor(ttl / 1000) : undefined));
}

function normalizeEmail(value) {
    return typeof value === 'string' ? value.trim().toLowerCase() : '';
}

function validEmail(value) {
    return value.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function readJson(request) {
    return new Promise((resolve, reject) => {
        let body = '';
        let tooLarge = false;
        request.setEncoding('utf8');
        request.on('data', chunk => {
            if (tooLarge) return;
            body += chunk;
            if (Buffer.byteLength(body) > 16 * 1024) {
                tooLarge = true;
                body = '';
            }
        });
        request.on('end', () => {
            if (tooLarge) {
                reject(Object.assign(new Error('Request body is too large.'), { status: 413 }));
                return;
            }
            try {
                resolve(body ? JSON.parse(body) : {});
            } catch {
                reject(Object.assign(new Error('Request must contain valid JSON.'), { status: 400 }));
            }
        });
        request.on('error', reject);
    });
}

function consumeRateLimit(request, bucket, limit, windowMs) {
    const key = `${bucket}:${request.socket.remoteAddress || 'unknown'}`;
    const now = Date.now();
    const entry = rateLimits.get(key);
    if (!entry || entry.resetAt <= now) {
        rateLimits.set(key, { count: 1, resetAt: now + windowMs });
        return true;
    }
    entry.count += 1;
    return entry.count <= limit;
}

async function hashPassword(password) {
    const salt = crypto.randomBytes(16);
    const derived = await scrypt(password, salt, PASSWORD_KEY_LENGTH, PASSWORD_SCRYPT_OPTIONS);
    return `scrypt$32768$8$1$${salt.toString('hex')}$${derived.toString('hex')}`;
}

async function verifyPassword(password, storedHash) {
    const parts = storedHash.split('$');
    if (parts.length !== 6 || parts[0] !== 'scrypt' || parts[1] !== '32768' || parts[2] !== '8' || parts[3] !== '1') {
        return false;
    }
    const salt = Buffer.from(parts[4], 'hex');
    const expected = Buffer.from(parts[5], 'hex');
    if (salt.length !== 16 || expected.length !== PASSWORD_KEY_LENGTH) return false;
    const actual = await scrypt(password, salt, expected.length, PASSWORD_SCRYPT_OPTIONS);
    return crypto.timingSafeEqual(actual, expected);
}

function redirect(response, location, status = 302) {
    response.writeHead(status, { Location: location, 'Cache-Control': 'no-store' });
    response.end();
}

function serveFile(response, route) {
    const item = staticFiles.get(route);
    if (!item) {
        response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        response.end('Not found');
        return;
    }
    const [fileName, contentType] = item;
    const content = fs.readFileSync(path.join(ROOT, fileName));
    response.writeHead(200, {
        'Content-Type': contentType,
        'Cache-Control': contentType.startsWith('text/html') ? 'no-store' : 'no-cache',
        'X-Content-Type-Options': 'nosniff'
    });
    response.end(content);
}

async function handleApi(request, response, pathname) {
    if (request.method === 'GET' && pathname === '/api/health') {
        return sendJson(response, 200, { ok: true, inference: 'unavailable' });
    }

    if (request.method === 'GET' && pathname === '/api/auth/status') {
        return sendJson(response, 200, { authenticated: Boolean(getSession(request)) });
    }

    if (request.method === 'GET' && pathname === '/api/auth/me') {
        const session = getSession(request);
        if (!session) return sendJson(response, 401, { error: 'Authentication required.' });
        return sendJson(response, 200, {
            user: { id: session.id, fullName: session.full_name, email: session.email }
        });
    }

    if (!['POST', 'PATCH'].includes(request.method)) {
        return sendJson(response, 405, { error: 'Method not allowed.' }, { Allow: 'GET, POST, PATCH' });
    }
    if (!isSameOrigin(request)) return sendJson(response, 403, { error: 'Request origin could not be verified.' });

    if (request.method === 'POST' && pathname === '/api/auth/register') {
        if (!consumeRateLimit(request, 'register', 5, 60 * 60 * 1000)) {
            return sendJson(response, 429, { error: 'Too many registration attempts. Try again later.' });
        }
        const body = await readJson(request);
        const fullName = typeof body.fullName === 'string' ? body.fullName.trim() : '';
        const email = normalizeEmail(body.email);
        const password = typeof body.password === 'string' ? body.password : '';
        if (fullName.length < 2 || fullName.length > 100) {
            return sendJson(response, 400, { error: 'Enter a name between 2 and 100 characters.' });
        }
        if (!validEmail(email)) return sendJson(response, 400, { error: 'Enter a valid email address.' });
        if (password.length < 12 || password.length > 128) {
            return sendJson(response, 400, { error: 'Use a password between 12 and 128 characters.' });
        }
        if (body.termsAccepted !== true) {
            return sendJson(response, 400, { error: 'Accept the Terms and Privacy Notice to create an account.' });
        }
        if (database.prepare('SELECT 1 FROM users WHERE email = ?').get(email)) {
            return sendJson(response, 409, { error: 'An account could not be created with those details.' });
        }
        const passwordHash = await hashPassword(password);
        const now = Date.now();
        const userId = crypto.randomUUID();
        try {
            database.prepare('INSERT INTO users (id, full_name, email, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)')
                .run(userId, fullName, email, passwordHash, now, now);
        } catch (error) {
            if (error.code === 'ERR_SQLITE_CONSTRAINT_UNIQUE') {
                return sendJson(response, 409, { error: 'An account could not be created with those details.' });
            }
            throw error;
        }
        createSession(request, response, userId, body.remember === true);
        return sendJson(response, 201, { user: { id: userId, fullName, email } });
    }

    if (request.method === 'POST' && pathname === '/api/auth/login') {
        if (!consumeRateLimit(request, 'login', 10, 15 * 60 * 1000)) {
            return sendJson(response, 429, { error: 'Too many sign-in attempts. Try again later.' });
        }
        const body = await readJson(request);
        const email = normalizeEmail(body.email);
        const password = typeof body.password === 'string' ? body.password : '';
        if (!validEmail(email) || password.length > 128 || password.length === 0) {
            return sendJson(response, 400, { error: 'Enter a valid email and password.' });
        }
        const user = database.prepare('SELECT id, full_name, email, password_hash FROM users WHERE email = ?').get(email);
        const valid = user
            ? await verifyPassword(password, user.password_hash)
            : (await scrypt(password, dummySalt, PASSWORD_KEY_LENGTH, PASSWORD_SCRYPT_OPTIONS), false);
        if (!valid) return sendJson(response, 401, { error: 'Email or password is incorrect.' });
        createSession(request, response, user.id, body.remember === true);
        return sendJson(response, 200, { user: { id: user.id, fullName: user.full_name, email: user.email } });
    }

    if (request.method === 'POST' && pathname === '/api/auth/logout') {
        const session = getSession(request);
        if (session) database.prepare('DELETE FROM sessions WHERE token_hash = ?').run(session.tokenHash);
        response.setHeader('Set-Cookie', cookieHeader(request, '', 0));
        return sendJson(response, 200, { ok: true });
    }

    const session = getSession(request);
    if (!session) return sendJson(response, 401, { error: 'Authentication required.' });

    if (request.method === 'PATCH' && pathname === '/api/auth/profile') {
        const body = await readJson(request);
        const fullName = typeof body.fullName === 'string' ? body.fullName.trim() : '';
        if (fullName.length < 2 || fullName.length > 100) {
            return sendJson(response, 400, { error: 'Enter a name between 2 and 100 characters.' });
        }
        database.prepare('UPDATE users SET full_name = ?, updated_at = ? WHERE id = ?')
            .run(fullName, Date.now(), session.id);
        return sendJson(response, 200, { user: { id: session.id, fullName, email: session.email } });
    }

    if (request.method === 'PATCH' && pathname === '/api/auth/password') {
        const body = await readJson(request);
        const currentPassword = typeof body.currentPassword === 'string' ? body.currentPassword : '';
        const newPassword = typeof body.newPassword === 'string' ? body.newPassword : '';
        const user = database.prepare('SELECT password_hash FROM users WHERE id = ?').get(session.id);
        if (!user || !(await verifyPassword(currentPassword, user.password_hash))) {
            return sendJson(response, 400, { error: 'Current password is incorrect.' });
        }
        if (newPassword.length < 12 || newPassword.length > 128) {
            return sendJson(response, 400, { error: 'Use a new password between 12 and 128 characters.' });
        }
        const passwordHash = await hashPassword(newPassword);
        const now = Date.now();
        database.prepare('UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?')
            .run(passwordHash, now, session.id);
        database.prepare('DELETE FROM sessions WHERE user_id = ?').run(session.id);
        createSession(request, response, session.id, false);
        return sendJson(response, 200, { ok: true, message: 'Password updated. Other sessions were signed out.' });
    }

    return sendJson(response, 404, { error: 'API route not found.' });
}

const server = http.createServer(async (request, response) => {
    setSecurityHeaders(response);
    if (!requestHostAllowed(request)) return sendJson(response, 421, { error: 'Unrecognized host.' });
    let url;
    try {
        url = new URL(request.url, `http://${request.headers.host}`);
    } catch {
        return sendJson(response, 400, { error: 'Invalid request URL.' });
    }

    try {
        if (url.pathname.startsWith('/api/')) return await handleApi(request, response, url.pathname);
        if (request.method !== 'GET' && request.method !== 'HEAD') {
            return sendJson(response, 405, { error: 'Method not allowed.' }, { Allow: 'GET, HEAD' });
        }
        if (url.pathname === '/app' || url.pathname === '/app.html') {
            if (!getSession(request)) return redirect(response, '/login');
            return serveFile(response, '/app.html');
        }
        if (url.pathname === '/login' || url.pathname === '/signup') return serveFile(response, '/index.html');
        if (url.pathname === '/') return serveFile(response, '/index.html');
        return serveFile(response, url.pathname);
    } catch (error) {
        if (response.headersSent || response.destroyed) {
            console.error('Request failed after response began:', error);
            return;
        }
        if (error.status) return sendJson(response, error.status, { error: error.message });
        console.error('Request failed:', error);
        return sendJson(response, 500, { error: 'The request could not be completed.' });
    }
});

server.listen(PORT, HOST, () => {
    console.log(`VOICEGUARD AI available at http://${HOST}:${PORT}`);
    console.log('Authentication: local SQLite + scrypt + HttpOnly sessions; inference: not configured.');
});

function shutdown() {
    server.close(() => {
        clearInterval(sessionCleanup);
        database.close();
        process.exit(0);
    });
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
