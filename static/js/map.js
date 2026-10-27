// Mapa de países: sincroniza el resaltado entre el mapa y la lista, muestra el tooltip y fija la selección con clic o toque.
// La lista funciona sola sin JavaScript; aquí solo se le añade el comportamiento de botón.
(function () {
  document.querySelectorAll("[data-map]").forEach(function (root) {
    var fig = root.querySelector("[data-map-figure]");
    var tip = root.querySelector("[data-map-tip]");
    var shapes = [].slice.call(root.querySelectorAll(".map__c"));
    var rows = [].slice.call(root.querySelectorAll(".map__row"));
    var selected = null;

    function parts(code) { return root.querySelectorAll('[data-c="' + code + '"]'); }
    function mark(code, cls, on) { parts(code).forEach(function (el) { el.classList.toggle(cls, on); }); }

    function showTip(label, e) {
      tip.textContent = label;
      tip.hidden = false;
      var r = fig.getBoundingClientRect();
      var x = e.clientX - r.left + 14, y = e.clientY - r.top - tip.offsetHeight - 10;
      tip.style.left = Math.max(8, Math.min(x, r.width - tip.offsetWidth - 8)) + "px";
      tip.style.top = Math.max(8, y) + "px";
    }
    function hideTip() { tip.hidden = true; }

    function select(code) {
      if (selected) { mark(selected, "is-selected", false); root.querySelectorAll('.map__row[data-c="' + selected + '"]').forEach(function (r) { r.setAttribute("aria-pressed", "false"); }); }
      selected = selected === code ? null : code;
      if (selected) {
        mark(selected, "is-selected", true);
        root.querySelectorAll('.map__row[data-c="' + selected + '"]').forEach(function (r) { r.setAttribute("aria-pressed", "true"); });
      }
    }

    shapes.forEach(function (s) {
      var code = s.dataset.c;
      s.addEventListener("pointerenter", function (e) { if (e.pointerType === "touch") return; mark(code, "is-active", true); showTip(s.dataset.label, e); });
      s.addEventListener("pointermove", function (e) { if (e.pointerType !== "touch") showTip(s.dataset.label, e); });
      // En táctil, pointerleave se dispara al levantar el dedo: el tooltip queda hasta tocar fuera.
      s.addEventListener("pointerleave", function (e) { if (e.pointerType === "touch") return; mark(code, "is-active", false); hideTip(); });
      s.addEventListener("click", function (e) { select(code); showTip(s.dataset.label, e); });
    });
    // Un toque fuera de un país limpia la selección y el tooltip.
    fig.addEventListener("click", function (e) {
      if (!e.target.closest(".map__c")) { if (selected) select(selected); hideTip(); }
    });

    rows.forEach(function (r) {
      var code = r.dataset.c;
      r.setAttribute("role", "button");
      r.setAttribute("aria-pressed", "false");
      r.tabIndex = 0;
      r.classList.add("is-interactive");
      r.addEventListener("pointerenter", function () { mark(code, "is-active", true); });
      r.addEventListener("pointerleave", function () { mark(code, "is-active", false); });
      r.addEventListener("focus", function () { mark(code, "is-active", true); });
      r.addEventListener("blur", function () { mark(code, "is-active", false); });
      r.addEventListener("click", function () { select(code); });
      r.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(code); }
      });
    });
  });
})();
