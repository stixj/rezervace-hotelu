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

    /** Priority badge (API: STANDARD | URGENT) — only urgent uses a chip; standard is omitted in lists. */
    function urgencyChipHtml(urgency, reason) {
        if (urgency !== "URGENT") {
            return "";
        }
        const t = reason ? escapeHtml(String(reason)) : "";
        const title = t ? ` title="${t}"` : "";
        return `<span class="urgency-chip"${title} aria-label="Priorita: urgentní">Urgentní</span>`;
    }

    function roomTypeLabel(v) {
        const key = v == null ? "" : String(v);
        const map = { single: "Jednolůžkový pokoj", multi: "Dvoulůžkový pokoj" };
        return map[key] ?? key;
    }

    function reservationForLabel(v) {
        if (v === "COLLEAGUE") {
            return "Pro jiného kolegu";
        }
        if (v === "SELF") {
            return "Pro mě";
        }
        return v == null ? "" : String(v);
    }

    function stayingPersonCountLabel(n) {
        const x = Number(n);
        if (x === 2) {
            return "2 osoby";
        }
        if (x === 1) {
            return "1 osoba";
        }
        return n == null ? "" : String(n);
    }

    function bedPreferenceLabel(v) {
        if (!v) {
            return "—";
        }
        const map = { double: "Manželská postel", twin: "Oddělená lůžka" };
        const key = String(v);
        return map[key] ?? key;
    }

    /** Name + email for detail <dd> — avoids broken "— <—>" when one part is missing. */
    function formatGuestDetailHtml(name, email) {
        const n = name != null ? String(name).trim() : "";
        const e = email != null ? String(email).trim() : "";
        if (n && e) {
            return `${escapeHtml(n)} &lt;${escapeHtml(e)}&gt;`;
        }
        if (n) {
            return escapeHtml(n);
        }
        if (e) {
            return escapeHtml(e);
        }
        return "—";
    }

    /** Parse API datetime (naive UTC from backend) for correct local display. */
    function parseBackendUtcDateTime(value) {
        if (value == null || value === "") {
            return null;
        }
        let s = String(value).trim().replace(" ", "T");
        if (!/[zZ]$/.test(s) && !/[+-]\d{2}:?\d{2}$/.test(s)) {
            s += "Z";
        }
        const d = new Date(s);
        return Number.isNaN(d.getTime()) ? null : d;
    }

    /** Plain text for a11y / attributes; same rules as formatRequestSubmittedCs. */
    function formatRequestSubmittedPlain(isoValue) {
        const d = parseBackendUtcDateTime(isoValue);
        if (!d) {
            if (isoValue == null || isoValue === "") {
                return "";
            }
            return String(isoValue);
        }
        return new Intl.DateTimeFormat("cs-CZ", {
            dateStyle: "short",
            timeStyle: "short",
            timeZone: "Europe/Prague",
        }).format(d);
    }

    /** Reception: request submission time (created_at) — Czech short date + time. */
    function formatRequestSubmittedCs(isoValue) {
        const plain = formatRequestSubmittedPlain(isoValue);
        if (!plain) {
            return "—";
        }
        return escapeHtml(plain);
    }

    global.HotelCommon = Object.assign({}, global.HotelCommon || {}, {
        parseErrorDetail,
        escapeHtml,
        STATUS_LABELS,
        statusLabel,
        urgencyChipHtml,
        roomTypeLabel,
        reservationForLabel,
        stayingPersonCountLabel,
        bedPreferenceLabel,
        formatGuestDetailHtml,
        parseBackendUtcDateTime,
        formatRequestSubmittedPlain,
        formatRequestSubmittedCs,
    });
})(window);
