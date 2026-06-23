/* Update Now modal: setup selector + copy-to-clipboard.
 *
 * No server interaction — a container cannot recreate itself, so the update
 * runs in the user's own container runtime. This only switches which set of
 * instructions is shown and copies a command to the clipboard.
 * See notes/easy-update-autoupdate-design.md.
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
(function () {
  "use strict";

  function activatePane(setup) {
    var selector = document.getElementById("update-setup-selector");
    if (!selector) { return; }
    var buttons = selector.querySelectorAll("[data-update-setup]");
    for (var i = 0; i < buttons.length; i++) {
      if (buttons[i].getAttribute("data-update-setup") === setup) {
        buttons[i].classList.add("active");
      } else {
        buttons[i].classList.remove("active");
      }
    }
    var panes = document.querySelectorAll("[data-update-pane]");
    for (var j = 0; j < panes.length; j++) {
      panes[j].style.display =
        (panes[j].getAttribute("data-update-pane") === setup) ? "" : "none";
    }
  }

  function legacyCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "absolute";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) { /* no-op */ }
    document.body.removeChild(ta);
  }

  function flashCopied(btn) {
    if (!btn) { return; }
    if (!btn.getAttribute("data-orig")) {
      btn.setAttribute("data-orig", btn.textContent);
    }
    btn.textContent = btn.getAttribute("data-copied-label") || "Copied!";
    setTimeout(function () {
      btn.textContent = btn.getAttribute("data-orig");
    }, 1500);
  }

  function copyText(text, btn) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () { flashCopied(btn); },
        function () { legacyCopy(text); flashCopied(btn); }
      );
    } else {
      legacyCopy(text);
      flashCopied(btn);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var selector = document.getElementById("update-setup-selector");
    if (selector) {
      selector.addEventListener("click", function (e) {
        var btn = e.target.closest ? e.target.closest("[data-update-setup]") : null;
        if (!btn) { return; }
        activatePane(btn.getAttribute("data-update-setup"));
      });
    }
    var copyBtns = document.querySelectorAll(".update-copy-btn");
    for (var i = 0; i < copyBtns.length; i++) {
      copyBtns[i].addEventListener("click", function (e) {
        var trigger = e.currentTarget;
        var wrap = trigger.closest ? trigger.closest(".update-cmd") : null;
        var code = wrap ? wrap.querySelector("code") : null;
        if (code) { copyText(code.textContent.trim(), trigger); }
      });
    }
  });
})();
