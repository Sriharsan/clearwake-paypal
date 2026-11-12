// Real seller quotes. Hidden while data/quotes.json is empty. Only Sri adds an entry, and only with the person's permission.
// An entry is {"text": "...", "name": "...", "role": "...", "permission": true}. An entry without permission true is never shown.
(function () {
  var slots = document.querySelectorAll("[data-quotes]");
  if (!slots.length) return;
  fetch("/data/quotes.json", { credentials: "omit" }).then(function (r) { return r.ok ? r.json() : []; }).then(function (list) {
    var ok = Array.isArray(list) ? list.filter(function (q) { return q && q.permission === true && typeof q.text === "string" && q.text.trim() && typeof q.name === "string" && q.name.trim(); }) : [];
    if (!ok.length) return;
    slots.forEach(function (slot) {
      var host = slot.querySelector("[data-quote-list]") || slot;
      host.textContent = "";
      ok.forEach(function (q) {
        var fig = document.createElement("figure"), bq = document.createElement("blockquote"), cap = document.createElement("figcaption");
        fig.className = "quote"; bq.textContent = q.text.trim();
        cap.textContent = q.name.trim() + (q.role ? ", " + String(q.role).trim() : "");
        fig.append(bq, cap); host.append(fig);
      });
      slot.hidden = false;
    });
  }).catch(function () { /* no file, no quote slot */ });
})();
