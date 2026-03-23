(function (global) {
    const KEY = "hotel_auth_token";

    function getToken() {
        return localStorage.getItem(KEY);
    }

    function setToken(t) {
        localStorage.setItem(KEY, t);
    }

    function clearToken() {
        localStorage.removeItem(KEY);
    }

    function authHeaders(extra) {
        const t = getToken();
        const h = Object.assign({ "Content-Type": "application/json" }, extra || {});
        if (t) {
            h.Authorization = "Bearer " + t;
        }
        return h;
    }

    /**
     * Fetch JSON API; on 401 clears token and redirects to /login (unless skipAuthRedirect).
     */
    async function apiJson(path, opts, skipAuthRedirect) {
        const API_BASE = global.__API_BASE__ ?? "";
        const o = opts || {};
        const { headers: extraHeaders, ...rest } = o;
        const res = await fetch(API_BASE + path, {
            ...rest,
            headers: authHeaders(extraHeaders),
        });
        const data = await res.json().catch(() => ({}));
        if (res.status === 401 && !skipAuthRedirect) {
            clearToken();
            window.location.href = "/login";
        }
        return { res, data };
    }

    global.HotelAuth = {
        getToken,
        setToken,
        clearToken,
        authHeaders,
        apiJson,
    };
})(window);
