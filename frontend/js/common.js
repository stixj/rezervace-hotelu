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

    global.HotelCommon = { parseErrorDetail, escapeHtml };
})(window);
