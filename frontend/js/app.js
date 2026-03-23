(function () {
    const API_BASE = window.__API_BASE__ ?? "";

    const form = document.getElementById("reservation-form");
    const roomType = document.getElementById("room_type");
    const bedGroup = document.getElementById("bed-preference-group");
    const bedSelect = document.getElementById("bed_preference");
    const msgEl = document.getElementById("form-message");
    const submitBtn = document.getElementById("submit-btn");

    const lookupForm = document.getElementById("lookup-form");
    const lookupMsg = document.getElementById("lookup-message");
    const lookupResult = document.getElementById("lookup-result");

    function toggleBedPreference() {
        const isSingle = roomType.value === "single";
        bedGroup.hidden = isSingle;
        if (isSingle) {
            bedSelect.value = "";
        }
    }

    roomType.addEventListener("change", toggleBedPreference);
    toggleBedPreference();

    function showMessage(el, type, html) {
        el.className = "message " + type;
        el.innerHTML = html;
        el.hidden = false;
    }

    function hideMessage(el) {
        el.hidden = true;
        el.textContent = "";
        el.className = "message";
    }

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

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideMessage(msgEl);
        submitBtn.disabled = true;

        const dateFrom = document.getElementById("date_from").value;
        const dateTo = document.getElementById("date_to").value;
        if (dateFrom && dateTo && dateTo < dateFrom) {
            showMessage(msgEl, "error", "Datum odjezdu musí být ve stejný den nebo po datu příjezdu.");
            submitBtn.disabled = false;
            return;
        }

        const body = {
            requester_name: document.getElementById("requester_name").value.trim(),
            requester_email: document.getElementById("requester_email").value.trim(),
            city: document.getElementById("city").value,
            date_from: dateFrom,
            date_to: dateTo,
            room_type: roomType.value,
            note: document.getElementById("note").value.trim() || null,
        };

        if (roomType.value === "multi") {
            const bed = bedSelect.value;
            body.bed_preference = bed || null;
        } else {
            body.bed_preference = null;
        }

        if (window.__HOTEL_PREVIEW__) {
            const fakeId =
                typeof crypto !== "undefined" && crypto.randomUUID
                    ? crypto.randomUUID()
                    : "demo-" + String(Date.now());
            showMessage(
                msgEl,
                "success",
                "<strong>(Náhled)</strong> Toto je simulace — žádost se neodeslala. " +
                    `Ukázkové ID: <code style="word-break:break-all">${escapeHtml(fakeId)}</code>`
            );
            form.reset();
            toggleBedPreference();
            submitBtn.disabled = false;
            return;
        }

        try {
            const res = await fetch(`${API_BASE}/reservations`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                showMessage(msgEl, "error", parseErrorDetail(data));
                return;
            }
            showMessage(
                msgEl,
                "success",
                `<strong>Žádost byla odeslána.</strong><br>Číslo žádosti (UUID): <code style="word-break:break-all">${data.id}</code><br>Stav: ${data.status}. Uložte si prosím identifikátor pro případné dotazy.`
            );
            form.reset();
            toggleBedPreference();
        } catch (err) {
            showMessage(
                msgEl,
                "error",
                "Nepodařilo se spojit s API. Spusťte backend a načtěte stránku ze stejného serveru, nebo nastavte <code>?api=http://127.0.0.1:8010</code> v URL (port dle <code>PORT</code> v <code>backend/.env</code>)."
            );
        } finally {
            submitBtn.disabled = false;
        }
    });

    lookupForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideMessage(lookupMsg);
        lookupResult.hidden = true;
        const id = document.getElementById("reservation_id").value.trim();
        if (!id) {
            showMessage(lookupMsg, "error", "Vyplňte UUID žádosti.");
            return;
        }
        if (window.__HOTEL_PREVIEW__) {
            lookupResult.innerHTML = `
        <p class="page-lead" style="margin-bottom:12px"><strong>(Náhled)</strong> Ukázkový stav žádosti — bez napojení na server.</p>
        <div class="status-badge">NEW</div>
        <dl class="status-detail">
          <dt>Město</dt><dd>Praha</dd>
          <dt>Od – do</dt><dd>2026-04-01 – 2026-04-03</dd>
          <dt>Typ pokoje</dt><dd>single</dd>
          <dt>Hotel / číslo rezervace</dt><dd>— / —</dd>
        </dl>`;
            lookupResult.hidden = false;
            return;
        }

        try {
            const res = await fetch(`${API_BASE}/reservations/${encodeURIComponent(id)}`);
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                showMessage(lookupMsg, "error", parseErrorDetail(data));
                return;
            }
            lookupResult.innerHTML = `
        <div class="status-badge">${escapeHtml(data.status)}</div>
        <dl class="status-detail">
          <dt>Město</dt><dd>${escapeHtml(data.city)}</dd>
          <dt>Od – do</dt><dd>${escapeHtml(data.date_from)} – ${escapeHtml(data.date_to)}</dd>
          <dt>Typ pokoje</dt><dd>${escapeHtml(data.room_type)}</dd>
          <dt>Hotel / číslo rezervace</dt><dd>${data.hotel_name ? escapeHtml(data.hotel_name) : "—"} / ${data.reservation_number ? escapeHtml(data.reservation_number) : "—"}</dd>
        </dl>`;
            lookupResult.hidden = false;
        } catch {
            showMessage(lookupMsg, "error", "Spojení s API selhalo.");
        }
    });

    function escapeHtml(s) {
        const div = document.createElement("div");
        div.textContent = s;
        return div.innerHTML;
    }

    document.querySelector(".form-container")?.classList.add("loaded");
})();
