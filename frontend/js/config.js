// API base: same origin when served by FastAPI static mount; override for local dev if needed
(function () {
    const script = document.currentScript;
    const fromQuery = new URLSearchParams(window.location.search).get("api");
    if (fromQuery) {
        window.__API_BASE__ = fromQuery.replace(/\/$/, "");
        return;
    }
    if (typeof window.__API_BASE__ === "string" && window.__API_BASE__) {
        return;
    }
    window.__API_BASE__ = "";
})();

/** True when UI is served as static files from username.github.io/repo/… (no FastAPI routes). */
(function () {
    function isGitHubPagesStatic() {
        return /\.github\.io$/i.test(window.location.hostname || "");
    }
    window.__isGitHubPagesStatic__ = isGitHubPagesStatic();
})();

/**
 * Map FastAPI-style paths to static .html (GitHub Pages). Else return path unchanged.
 */
(function () {
    function hotelUiHref(path) {
        if (!path || path[0] !== "/" || path.startsWith("//")) {
            return path;
        }
        if (!window.__isGitHubPagesStatic__) {
            return path;
        }
        const map = {
            "/login": "login.html",
            "/app/new": "app_new.html",
            "/app/my-requests": "app_my_requests.html",
            "/admin/requests": "admin_requests.html",
        };
        if (map[path]) {
            return map[path];
        }
        const am = path.match(/^\/admin\/requests\/([^/?#]+)$/);
        if (am) {
            return (
                "admin_request_detail.html?id=" +
                encodeURIComponent(decodeURIComponent(am[1]))
            );
        }
        const pm = path.match(/^\/app\/requests\/([^/?#]+)$/);
        if (pm) {
            return (
                "app_request_detail.html?id=" +
                encodeURIComponent(decodeURIComponent(pm[1]))
            );
        }
        return path;
    }
    window.hotelUiHref = hotelUiHref;
    window.hotelGo = function (path) {
        window.location.href = hotelUiHref(path);
    };

    /** Path-like string for nav active state (GitHub Pages uses *.html URLs). */
    window.hotelNavPath = function () {
        const path = window.location.pathname || "";
        if (!window.__isGitHubPagesStatic__) {
            return path;
        }
        const file = path.split("/").pop() || "";
        const byFile = {
            "app_new.html": "/app/new",
            "index.html": "/app/new",
            "app_my_requests.html": "/app/my-requests",
            "app_request_detail.html": "/app/my-requests",
            "admin_requests.html": "/admin/requests",
            "admin_request_detail.html": "/admin/requests",
            "login.html": "/login",
        };
        return byFile[file] || path;
    };

    function rewriteAnchors() {
        if (!window.__isGitHubPagesStatic__) {
            return;
        }
        document.querySelectorAll('a[href^="/"]').forEach((a) => {
            const h = a.getAttribute("href");
            if (!h || h.startsWith("//")) {
                return;
            }
            const r = hotelUiHref(h);
            if (r !== h) {
                a.setAttribute("href", r);
            }
        });
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", rewriteAnchors);
    } else {
        rewriteAnchors();
    }
})();

// Brand logo is served by the API app; when the page is opened from another origin (?api=),
// a bare "/Loga/..." src would hit the wrong host and break.
(function applyBrandLogoSrc() {
    function go() {
        const base = (window.__API_BASE__ || "").replace(/\/$/, "");
        document.querySelectorAll("img.brand-direct-logo[data-brand-logo]").forEach((el) => {
            const rel =
                el.getAttribute("data-brand-logo") || "/Loga/Logo-negativni-RGB.png";
            if (window.__isGitHubPagesStatic__ && !base) {
                el.src = rel.replace(/^\//, "");
                return;
            }
            el.src = base + rel;
        });
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", go);
    } else {
        go();
    }
})();
