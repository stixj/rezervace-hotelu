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

// Brand logo is served by the API app; when the page is opened from another origin (?api=),
// a bare "/Loga/..." src would hit the wrong host and break.
(function applyBrandLogoSrc() {
    function go() {
        const base = (window.__API_BASE__ || "").replace(/\/$/, "");
        document.querySelectorAll("img.brand-direct-logo[data-brand-logo]").forEach((el) => {
            const rel =
                el.getAttribute("data-brand-logo") || "/Loga/Logo-negativni-RGB.png";
            el.src = base + rel;
        });
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", go);
    } else {
        go();
    }
})();
