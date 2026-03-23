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

    // If browser cached an older common.js without statusLabel, avoid runtime errors on list/detail pages.
    (function patchStatusLabel() {
        const hc = global.HotelCommon;
        if (!hc || typeof hc.statusLabel === "function") {
            return;
        }
        const L = {
            NEW: "Nová",
            IN_PROGRESS: "V řešení",
            BOOKED: "Rezervováno",
            CANCELLED: "Zrušeno",
        };
        hc.statusLabel = function (status) {
            if (status == null || status === "") {
                return "";
            }
            const key = String(status);
            return L[key] ?? key;
        };
    })();
})(window);
