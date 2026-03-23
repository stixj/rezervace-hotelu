(function (global) {
    function parseErrorDetail(data) {
        if (!data || !data.detail) {
            return "Požadavek se nepodařilo zpracovat.";
        }
        const d = data.detail;
        if (typeof d === "string") {
            return d;
        }
        if (Array.isArray(d)) {
            return d
                .map((e) => (e.msg ? `${e.loc?.join(".")}: ${e.msg}` : JSON.stringify(e)))
                .join("<br>");
        }
        return JSON.stringify(d);
    }

    function escapeHtml(s) {
        const div = document.createElement("div");
        div.textContent = s;
        return div.innerHTML;
    }

    /** Internal API status → Czech UI label (values unchanged in DOM/API). */
    const STATUS_LABELS = {
        NEW: "Nová",
        IN_PROGRESS: "V řešení",
        BOOKED: "Rezervováno",
        CANCELLED: "Zrušeno",
    };

    function statusLabel(status) {
        if (status == null || status === "") {
            return "";
        }
        const key = String(status);
        return STATUS_LABELS[key] ?? key;
    }

    /** Urgency badge (API: STANDARD | URGENT) — only render for urgent to avoid visual noise. */
    function urgencyChipHtml(urgency, reason) {
        if (urgency !== "URGENT") {
            return "";
        }
        const t = reason ? escapeHtml(String(reason)) : "";
        const title = t ? ` title="${t}"` : "";
        return `<span class="urgency-chip"${title} aria-label="Urgentní požadavek">Urgentní</span>`;
    }

    global.HotelCommon = Object.assign({}, global.HotelCommon || {}, {
        parseErrorDetail,
        escapeHtml,
        STATUS_LABELS,
        statusLabel,
        urgencyChipHtml,
    });
})(window);
