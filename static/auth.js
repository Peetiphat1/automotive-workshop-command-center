// ── Shop login — load before any other app script ──
// Stores the shop password in this browser and adds it as X-API-Key to every /api/ request.
// A 401 from the server clears it and shows the login box again.
(function () {
    const STORAGE_KEY = 'shop_api_key';
    const PUBLIC_API = ['/api/v1/tickets/track/', '/api/v1/line/webhook', '/api/v1/public/'];

    function readKey() {
        try { return localStorage.getItem(STORAGE_KEY) || ''; } catch { return ''; }
    }
    function writeKey(v) {
        try { v ? localStorage.setItem(STORAGE_KEY, v) : localStorage.removeItem(STORAGE_KEY); } catch {}
    }

    function isApiUrl(url) {
        try {
            const u = new URL(url, window.location.href);
            return u.origin === window.location.origin && u.pathname.startsWith('/api/')
                && !PUBLIC_API.some(p => u.pathname.startsWith(p));
        } catch { return false; }
    }

    const nativeFetch = window.fetch.bind(window);
    let loginPromise = null;

    window.fetch = async function (input, init = {}) {
        const url = typeof input === 'string' ? input : (input && input.url) || '';
        if (!isApiUrl(url)) return nativeFetch(input, init);

        // No login up front: the box only appears if the server asks for a password (REQUIRE_PASSWORD=true)
        const send = () => {
            const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
            if (readKey()) headers.set('X-API-Key', readKey());
            return nativeFetch(input, { ...init, headers });
        };
        let res = await send();
        if (res.status === 401) {
            writeKey('');
            await requireLogin('รหัสผ่านไม่ถูกต้อง หรือหมดอายุ — กรุณาเข้าสู่ระบบอีกครั้ง');
            res = await send();
        }
        return res;
    };

    function requireLogin(message) {
        if (!loginPromise) {
            loginPromise = showLogin(message).finally(() => { loginPromise = null; });
        }
        return loginPromise;
    }

    function showLogin(message) {
        return new Promise(resolve => {
            const build = () => {
                const wrap = document.createElement('div');
                wrap.id = 'shop-login-overlay';
                wrap.style.cssText = 'position:fixed;inset:0;z-index:100000;display:flex;align-items:center;justify-content:center;background:rgba(2,6,23,0.92);backdrop-filter:blur(6px);padding:16px;font-family:inherit;';
                wrap.innerHTML = `
                    <form style="width:100%;max-width:360px;background:#1e293b;border:1px solid rgba(255,255,255,0.12);border-radius:16px;padding:28px 24px;box-shadow:0 20px 50px rgba(0,0,0,0.5);color:#e2e8f0;">
                        <div style="font-size:2rem;text-align:center;margin-bottom:6px;">🔐</div>
                        <div style="font-size:1.15rem;font-weight:800;text-align:center;margin-bottom:4px;">เข้าสู่ระบบอู่</div>
                        <div style="font-size:0.82rem;color:#94a3b8;text-align:center;margin-bottom:18px;">กรอกรหัสผ่านร้าน (ตั้งค่าใน .env: MOCK_API_KEY)</div>
                        <input type="password" autocomplete="current-password" placeholder="รหัสผ่านร้าน" required
                            style="width:100%;box-sizing:border-box;padding:11px 14px;border-radius:10px;border:1px solid rgba(255,255,255,0.15);background:#0f172a;color:#f1f5f9;font-size:1rem;outline:none;">
                        <div class="login-err" style="min-height:20px;margin-top:8px;font-size:0.8rem;color:#f87171;text-align:center;"></div>
                        <button type="submit" style="width:100%;margin-top:6px;padding:11px;border:none;border-radius:10px;background:#3b82f6;color:#fff;font-weight:700;font-size:0.95rem;cursor:pointer;">เข้าสู่ระบบ</button>
                    </form>`;
                document.body.appendChild(wrap);
                const form = wrap.querySelector('form');
                const input = wrap.querySelector('input');
                const err = wrap.querySelector('.login-err');
                if (message) err.textContent = message;
                input.focus();
                form.addEventListener('submit', async e => {
                    e.preventDefault();
                    const key = input.value.trim();
                    if (!key) return;
                    err.textContent = 'กำลังตรวจสอบ...';
                    try {
                        const r = await nativeFetch('/api/v1/auth/check', { headers: { 'X-API-Key': key } });
                        if (r.ok) {
                            writeKey(key);
                            wrap.remove();
                            resolve();
                        } else {
                            err.textContent = 'รหัสผ่านไม่ถูกต้อง';
                            input.select();
                        }
                    } catch {
                        err.textContent = 'เชื่อมต่อเซิร์ฟเวอร์ไม่ได้';
                    }
                });
            };
            if (document.body) build();
            else document.addEventListener('DOMContentLoaded', build, { once: true });
        });
    }

    // Download a protected file (backup export) — a plain link cannot send the password header
    window.downloadWithAuth = async function (url, fallbackName) {
        const res = await fetch(url);
        if (!res.ok) throw new Error('ดาวน์โหลดไม่สำเร็จ (' + res.status + ')');
        const cd = res.headers.get('Content-Disposition') || '';
        const m = cd.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
        const name = m ? decodeURIComponent(m[1] || m[2]) : fallbackName;
        const blobUrl = URL.createObjectURL(await res.blob());
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(blobUrl), 2000);
    };

    window.shopLogout = function () {
        writeKey('');
        window.location.reload();
    };
})();
