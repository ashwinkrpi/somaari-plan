// Theme picker and seasonal default theme, the same themes and schedule as somaari-site (D-17).
// Loaded as a blocking classic script in <head> (not a module), so data-theme is set before first
// paint and there is no flash of the wrong theme. The picker in the panel footer (#theme-picker)
// is wired up once the DOM is ready. The colours and fonts live in css/app.css.
//
// Which theme shows: ?theme=<id> in the URL (a preview, never saved), else the saved choice,
// else the date schedule below. Choosing "Auto (seasonal)" clears the saved choice.
(function () {
  "use strict";

  // <meta name="theme-color"> for each theme.
  var THEMES = {
    "warm-tactile": "#EDE3D3",
    "liquid-glass": "#0A0E1C",
    "dasara-jamboo": "#3E0810",
    "rajyotsava": "#E2D3A2"
  };
  var DEFAULT_THEME = "warm-tactile";

  // Seasonal defaults, checked in order using the date in India (Asia/Kolkata). Keep in step with
  // somaari-site/theme.js:
  //   { from: "YYYY-MM-DD", to: "YYYY-MM-DD", theme: "<id>" }  one-off dates, inclusive
  //   { monthDay: ["MM-DD", "MM-DD"], theme: "<id>" }          every year, inclusive
  var SCHEDULE = [
    { from: "2026-10-17", to: "2026-10-20", theme: "dasara-jamboo" },
    { monthDay: ["11-01", "11-07"], theme: "rajyotsava" }
  ];

  var IST_OFFSET_MS = 330 * 60 * 1000; // UTC+5:30; India has no daylight saving

  // The schedule's theme for the instant `date`, judged by the calendar day in India.
  function getDefaultTheme(date) {
    var ymd = new Date(date.getTime() + IST_OFFSET_MS).toISOString().slice(0, 10);
    var md = ymd.slice(5);
    for (var i = 0; i < SCHEDULE.length; i++) {
      var e = SCHEDULE[i];
      if (e.from && ymd >= e.from && ymd <= e.to) return e.theme;
      if (e.monthDay) {
        var a = e.monthDay[0], b = e.monthDay[1];
        if (a <= b ? md >= a && md <= b : md >= a || md <= b) return e.theme; // b < a wraps the new year
      }
    }
    return DEFAULT_THEME;
  }

  if (typeof module === "object" && module.exports) {
    module.exports = { THEMES: THEMES, SCHEDULE: SCHEDULE, DEFAULT_THEME: DEFAULT_THEME, getDefaultTheme: getDefaultTheme };
    return;
  }

  var STORAGE_KEY = "somaari-theme";
  var root = document.documentElement;

  function isTheme(id) { return Object.prototype.hasOwnProperty.call(THEMES, id); }

  function readSaved() {
    try {
      var v = localStorage.getItem(STORAGE_KEY);
      return isTheme(v) ? v : null;
    } catch (e) { return null; }
  }

  function save(id) {
    try {
      if (id) localStorage.setItem(STORAGE_KEY, id); else localStorage.removeItem(STORAGE_KEY);
    } catch (e) { /* storage blocked: the choice lasts for this page view only */ }
  }

  function readPreview() {
    try {
      var v = new URLSearchParams(location.search).get("theme");
      return isTheme(v) ? v : null;
    } catch (e) { return null; }
  }

  function apply(id) {
    root.setAttribute("data-theme", id);
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    for (var i = 0; i < metas.length; i++) metas[i].setAttribute("content", THEMES[id]);
  }

  var preview = readPreview();
  var saved = readSaved();
  apply(preview || saved || getDefaultTheme(new Date()));

  document.addEventListener("DOMContentLoaded", function () {
    var picker = document.getElementById("theme-picker");
    if (!picker) return;
    // The choices are radio buttons inside #theme-picker, valued "auto" or a theme id.
    var choices = picker.querySelectorAll("input[type=radio]");
    var current = preview || saved || "auto";
    for (var i = 0; i < choices.length; i++) choices[i].checked = choices[i].value === current;
    picker.hidden = false; // the picker needs JS, so it stays hidden without it

    picker.addEventListener("change", function (e) {
      var id = isTheme(e.target.value) ? e.target.value : null;
      save(id);
      apply(id || getDefaultTheme(new Date()));
      // A choice replaces any ?theme= preview, so it is what shows after a reload.
      if (preview) {
        preview = null;
        try {
          var url = new URL(location.href);
          url.searchParams.delete("theme");
          history.replaceState(null, "", url);
        } catch (e) { /* leave the URL as it is */ }
      }
    });

    // Popover: the Theme button opens the choices and focuses the checked one. Esc closes it and
    // returns focus to the button; so does a click outside, or tabbing out of it.
    var toggle = document.getElementById("appearance-toggle");
    var menu = document.getElementById("appearance-menu");
    if (!toggle || !menu) return;

    function setOpen(open, refocus) {
      menu.hidden = !open;
      toggle.setAttribute("aria-expanded", String(open));
      if (open) (menu.querySelector("input:checked") || menu.querySelector("input")).focus();
      else if (refocus) toggle.focus();
    }
    toggle.addEventListener("click", function () { setOpen(menu.hidden, false); });
    picker.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !menu.hidden) { e.preventDefault(); setOpen(false, true); }
    });
    picker.addEventListener("focusout", function (e) {
      if (!menu.hidden && e.relatedTarget && !picker.contains(e.relatedTarget)) setOpen(false, false);
    });
    document.addEventListener("click", function (e) {
      if (!menu.hidden && !picker.contains(e.target)) setOpen(false, false);
    });
  });
})();
