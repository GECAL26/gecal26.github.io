// Filtros de novedades. Mejora progresiva: sin JavaScript el formulario queda oculto y se ven todas.
(function () {
  var root = document.querySelector("[data-news-list]");
  if (!root) return;
  var form = root.querySelector("[data-filters]");
  if (!form) return;
  var cards = Array.prototype.slice.call(root.querySelectorAll("[data-news]"));
  var out = root.querySelector("[data-count]");
  var none = root.querySelector("[data-none]");
  form.hidden = false;

  function norm(s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }

  function apply() {
    var q = norm(form.elements.q.value.trim());
    var tipo = form.elements.type.value;
    var n = 0;
    cards.forEach(function (el) {
      var ok = (!tipo || el.dataset.type === tipo) && (!q || el.dataset.text.indexOf(q) > -1);
      el.hidden = !ok;
      if (ok) n++;
    });
    out.textContent = out.dataset.tpl.replace("{n}", n).replace("{total}", cards.length);
    none.hidden = n !== 0;
  }

  // La portada enlaza por tipo: /news/?type=grant
  var want = (new URLSearchParams(location.search).get("type") || "").replace(/[^a-z]/g, "");
  if (want && form.elements.type.querySelector('option[value="' + want + '"]')) form.elements.type.value = want;

  form.addEventListener("input", apply);
  form.addEventListener("submit", function (e) { e.preventDefault(); });
  form.addEventListener("reset", function () { setTimeout(apply); });
  apply();
})();
