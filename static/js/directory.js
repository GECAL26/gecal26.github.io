// Filtros del directorio. Mejora progresiva: sin JS el formulario queda oculto y se ven todos los perfiles.
(function () {
  var root = document.querySelector("[data-directory]");
  if (!root) return;
  var form = root.querySelector("[data-filters]");
  var cards = Array.prototype.slice.call(root.querySelectorAll("[data-member]"));
  var out = root.querySelector("[data-count]");
  var none = root.querySelector("[data-none]");
  form.hidden = false;

  function norm(s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  function has(list, v) { return (" " + list + " ").indexOf(" " + v + " ") > -1; }

  function apply() {
    var q = norm(form.elements.q.value.trim());
    var c = form.elements.country.value;
    var a = form.elements.area.value;
    var t = form.elements.tool.value;
    var n = 0;
    cards.forEach(function (el) {
      var ok = (!c || el.dataset.country === c) &&
               (!a || has(el.dataset.areas, a)) &&
               (!t || has(el.dataset.tools, t)) &&
               (!q || el.dataset.text.indexOf(q) > -1);
      el.hidden = !ok;
      if (ok) n++;
    });
    out.textContent = out.dataset.tpl.replace("{n}", n).replace("{total}", cards.length);
    none.hidden = n !== 0;
  }

  var want = (new URLSearchParams(location.search).get("country") || "").replace(/[^A-Z]/g, "");
  if (want && form.elements.country.querySelector('option[value="' + want + '"]')) form.elements.country.value = want;

  form.addEventListener("input", apply);
  form.addEventListener("submit", function (e) { e.preventDefault(); });
  form.addEventListener("reset", function () { setTimeout(apply); });
  apply();
})();
