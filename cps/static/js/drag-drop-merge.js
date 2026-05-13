/* Drag-and-drop book merge for the main book grid.
 *
 * Usage: drag one book cover onto another.
 *   - The dragged book is the SOURCE (will be merged in and deleted).
 *   - The drop target is the KEEPER (its record survives with all formats).
 *
 * Only active when the user has edit permission (window.cwaUserData.canEditBooks).
 * Does nothing while BookOrganizer multi-select mode is active.
 *
 * Calls the existing POST /ajax/mergebooks endpoint:
 *   { "Merge_books": [keeper_id, source_id] }
 *
 * Requires:
 *   - <div id="book-merge-modal"> in layout.html
 *   - window.cwaUserData.canEditBooks set by layout.html
 */
(function () {
  "use strict";

  if (!window.cwaUserData || !window.cwaUserData.canEditBooks) return;

  var BOOK_SELECTOR = ".book";
  var COVER_LINK_SELECTOR = ".book-cover-link";
  var DRAGGING_CLASS = "drag-merge-dragging";
  var OVER_CLASS = "drag-merge-over";
  var DRAG_ENABLED_CLASS = "drag-merge-enabled";

  var dragSourceId = null;
  var dragSourceTitle = null;
  var dragSourceFormats = null;

  function getCsrfToken() {
    var el = document.querySelector('input[name="csrf_token"]');
    return el ? el.value : "";
  }

  function getBookEl(el) {
    return el.closest ? el.closest(BOOK_SELECTOR) : null;
  }

  function getBookId(bookEl) {
    var link = bookEl.querySelector(COVER_LINK_SELECTOR);
    return link ? link.getAttribute("data-book-id") : null;
  }

  function getBookTitle(bookEl) {
    var p = bookEl.querySelector(".title");
    return p ? p.getAttribute("title") || p.textContent.trim() : "(unknown)";
  }

  function getBookFormats(bookEl) {
    var link = bookEl.querySelector(COVER_LINK_SELECTOR);
    var raw = link ? link.getAttribute("data-book-formats") : "";
    return raw ? raw.split(",").filter(Boolean).map(function (f) { return f.toUpperCase(); }) : [];
  }

  // --- Modal helpers ---

  function getModal() { return document.getElementById("book-merge-modal"); }

  function showModal(keeperTitle, keeperFormats, sourceTitle, sourceFormats, onConfirm) {
    var modal = getModal();
    if (!modal) return;

    modal.querySelector("[data-merge-keeper-title]").textContent = keeperTitle;
    modal.querySelector("[data-merge-source-title]").textContent = sourceTitle;

    var keeperFmtEl = modal.querySelector("[data-merge-keeper-formats]");
    var sourceFmtEl = modal.querySelector("[data-merge-source-formats]");
    keeperFmtEl.textContent = keeperFormats.length ? keeperFormats.join(", ") : "—";
    sourceFmtEl.textContent = sourceFormats.length ? sourceFormats.join(", ") : "—";

    // Compute merged format list for preview
    var merged = keeperFormats.slice();
    sourceFormats.forEach(function (f) {
      if (merged.indexOf(f) === -1) merged.push(f);
    });
    var mergedEl = modal.querySelector("[data-merge-result-formats]");
    if (mergedEl) mergedEl.textContent = merged.length ? merged.join(", ") : "—";

    var confirmBtn = modal.querySelector("[data-merge-confirm]");
    function handleConfirm() {
      confirmBtn.removeEventListener("click", handleConfirm);
      hideModal();
      onConfirm();
    }
    confirmBtn.addEventListener("click", handleConfirm);

    var cancelBtn = modal.querySelector("[data-merge-cancel]");
    function handleCancel() {
      cancelBtn.removeEventListener("click", handleCancel);
      confirmBtn.removeEventListener("click", handleConfirm);
      hideModal();
    }
    cancelBtn.addEventListener("click", handleCancel);

    modal.removeAttribute("hidden");
    modal.setAttribute("aria-hidden", "false");
    // Focus the cancel button by default so Enter doesn't accidentally confirm
    cancelBtn.focus();

    // Close on backdrop click
    function handleBackdrop(e) {
      if (e.target === modal) {
        modal.removeEventListener("click", handleBackdrop);
        cancelBtn.removeEventListener("click", handleCancel);
        confirmBtn.removeEventListener("click", handleConfirm);
        hideModal();
      }
    }
    modal.addEventListener("click", handleBackdrop);

    // Close on Escape
    function handleKeydown(e) {
      if (e.key === "Escape") {
        document.removeEventListener("keydown", handleKeydown);
        cancelBtn.removeEventListener("click", handleCancel);
        confirmBtn.removeEventListener("click", handleConfirm);
        hideModal();
      }
    }
    document.addEventListener("keydown", handleKeydown);
  }

  function hideModal() {
    var modal = getModal();
    if (!modal) return;
    modal.setAttribute("hidden", "");
    modal.setAttribute("aria-hidden", "true");
  }

  // --- Merge API call ---

  function doMerge(keeperId, sourceId, onSuccess, onError) {
    fetch("/ajax/mergebooks", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ Merge_books: [parseInt(keeperId, 10), parseInt(sourceId, 10)] }),
    })
      .then(function (resp) {
        return resp.json().then(function (data) {
          return { ok: resp.ok, data: data };
        });
      })
      .then(function (result) {
        if (result.ok && result.data && result.data.success) {
          onSuccess();
        } else {
          var msg = (result.data && result.data.error) || "Merge failed.";
          onError(msg);
        }
      })
      .catch(function (err) {
        onError(err.message || "Network error.");
      });
  }

  // --- Flash helper (reuse book_organizer pattern) ---

  function flash(msg, kind) {
    var holder = document.querySelector(".book-organizer-flash");
    if (!holder) {
      holder = document.createElement("div");
      holder.className = "book-organizer-flash";
      holder.setAttribute("role", "status");
      holder.setAttribute("aria-live", "polite");
      document.body.appendChild(holder);
    }
    holder.textContent = msg;
    holder.dataset.kind = kind || "success";
    holder.classList.add("is-visible");
    clearTimeout(holder._t);
    holder._t = setTimeout(function () {
      holder.classList.remove("is-visible");
    }, kind === "error" ? 6000 : 4000);
  }

  // --- Drag event handlers ---

  function onDragStart(e) {
    // Don't interfere with multi-select mode
    if (document.body.classList.contains("book-organizer-select-mode")) return;

    var bookEl = getBookEl(e.target);
    if (!bookEl) return;

    dragSourceId = getBookId(bookEl);
    dragSourceTitle = getBookTitle(bookEl);
    dragSourceFormats = getBookFormats(bookEl);

    if (!dragSourceId) return;

    bookEl.classList.add(DRAGGING_CLASS);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", dragSourceId);
  }

  function onDragEnd(e) {
    var bookEl = getBookEl(e.target);
    if (bookEl) bookEl.classList.remove(DRAGGING_CLASS);
    // Clean up any lingering over-states
    document.querySelectorAll("." + OVER_CLASS).forEach(function (el) {
      el.classList.remove(OVER_CLASS);
    });
    dragSourceId = null;
    dragSourceTitle = null;
    dragSourceFormats = null;
  }

  function onDragOver(e) {
    if (!dragSourceId) return;
    var bookEl = getBookEl(e.target);
    if (!bookEl) return;

    var targetId = getBookId(bookEl);
    if (!targetId || targetId === dragSourceId) return;

    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    bookEl.classList.add(OVER_CLASS);
  }

  function onDragLeave(e) {
    var bookEl = getBookEl(e.target);
    if (bookEl) bookEl.classList.remove(OVER_CLASS);
  }

  function onDrop(e) {
    e.preventDefault();
    if (!dragSourceId) return;

    var bookEl = getBookEl(e.target);
    if (!bookEl) return;
    bookEl.classList.remove(OVER_CLASS);

    var keeperId = getBookId(bookEl);
    if (!keeperId || keeperId === dragSourceId) return;

    var keeperTitle = getBookTitle(bookEl);
    var keeperFormats = getBookFormats(bookEl);

    var capturedSourceId = dragSourceId;
    var capturedSourceTitle = dragSourceTitle;
    var capturedSourceFormats = dragSourceFormats;

    showModal(keeperTitle, keeperFormats, capturedSourceTitle, capturedSourceFormats, function () {
      doMerge(keeperId, capturedSourceId,
        function () {
          flash("“" + capturedSourceTitle + "” merged into “" + keeperTitle + "”.", "success");
          setTimeout(function () { window.location.reload(); }, 800);
        },
        function (err) {
          flash("Merge failed: " + err, "error");
        }
      );
    });
  }

  // --- Init: enable draggable on all .book elements ---

  function enableDrag(bookEl) {
    if (bookEl.classList.contains(DRAG_ENABLED_CLASS)) return;
    bookEl.classList.add(DRAG_ENABLED_CLASS);
    bookEl.setAttribute("draggable", "true");
    bookEl.addEventListener("dragstart", onDragStart);
    bookEl.addEventListener("dragend", onDragEnd);
    bookEl.addEventListener("dragover", onDragOver);
    bookEl.addEventListener("dragleave", onDragLeave);
    bookEl.addEventListener("drop", onDrop);
  }

  function initBooks() {
    document.querySelectorAll(BOOK_SELECTOR).forEach(enableDrag);
  }

  // Also watch for dynamically added books (load-more scenarios)
  var observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (m) {
      m.addedNodes.forEach(function (node) {
        if (node.nodeType !== 1) return;
        if (node.matches && node.matches(BOOK_SELECTOR)) {
          enableDrag(node);
        } else if (node.querySelectorAll) {
          node.querySelectorAll(BOOK_SELECTOR).forEach(enableDrag);
        }
      });
    });
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initBooks();
      observer.observe(document.body, { childList: true, subtree: true });
    });
  } else {
    initBooks();
    observer.observe(document.body, { childList: true, subtree: true });
  }
})();
