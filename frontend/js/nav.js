(function () {
    const nav = document.getElementById("main-nav");
    if (!nav) {
        return;
    }

    const API_BASE = window.__API_BASE__ ?? "";
    const token = localStorage.getItem("hotel_auth_token");

    function renderLoginLink() {
        nav.innerHTML = '<a href="/login">Přihlásit</a>';
    }

    if (!token) {
        renderLoginLink();
        return;
    }

    (async () => {
        let me;
        try {
            const r = await fetch(`${API_BASE}/auth/me`, {
                headers: { Authorization: "Bearer " + token },
            });
            if (!r.ok) {
                throw new Error("unauthorized");
            }
            me = await r.json();
        } catch {
            localStorage.removeItem("hotel_auth_token");
            renderLoginLink();
            return;
        }

        const path = window.location.pathname || "";
        /** Reception uses admin list only; employee flows are hidden. */
        const items =
            me.role === "RECEPTION"
                ? [
                      {
                          href: "/admin/requests",
                          label: "Recepce",
                          match: "/admin/requests",
                      },
                  ]
                : [
                      { href: "/app/new", label: "Nová žádost", match: "/app/new" },
                      {
                          href: "/app/my-requests",
                          label: "Moje žádosti",
                          match: "/app/my-requests",
                      },
                  ];

        const parts = items.map((i) => {
            let active =
                path === i.match ||
                path.startsWith(i.match + "/") ||
                (i.match === "/admin/requests" && path.startsWith("/admin/requests"));
            if (i.match === "/app/my-requests" && path.startsWith("/app/requests/")) {
                active = true;
            }
            const cls = active ? ' class="active"' : "";
            return `<a href="${i.href}"${cls}>${i.label}</a>`;
        });

        parts.push(
            '<button type="button" class="nav-logout" id="nav-logout">Odhlásit</button>'
        );
        nav.innerHTML = parts.join("");

        document.getElementById("nav-logout").addEventListener("click", () => {
            localStorage.removeItem("hotel_auth_token");
            window.location.href = "/login";
        });
    })();
})();
