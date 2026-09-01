/**
 * Nokor Pheas Commune Staff Management System
 * Frontend Interactivity, Live Clock, Charts & Toast Notification System
 */

document.addEventListener("DOMContentLoaded", function () {
  initThemeToggle();
  initSidebarControls();
  initLiveClock();
  initModals();
  initDemoAccountFiller();
  initTableSearch();
  initFlashToasts();
  initPageTransitionsAndPrefetch();
  initBackToTop();
  initLoadingCircleSystem();
});

// ==============================================================================
// 1. TOAST NOTIFICATION SYSTEM
// ==============================================================================

function getOrCreateToastContainer() {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    container.setAttribute("aria-live", "polite");
    document.body.appendChild(container);
  }
  return container;
}

/**
 * Show a toast notification
 * @param {string} message - Message text to display
 * @param {string} type - 'success', 'danger'|'error', 'warning', 'info'
 * @param {string} title - Optional title
 * @param {number} duration - Milliseconds before auto dismiss (default: 4500)
 */
function showToast(message, type = "success", title = "", duration = 4500) {
  const container = getOrCreateToastContainer();

  // Normalize type
  if (type === "error") type = "danger";
  if (!["success", "danger", "warning", "info"].includes(type)) {
    type = "info";
  }

  // Default titles in Khmer
  const defaultTitles = {
    success: "ជោគជ័យ",
    danger: "មានកំហុស / បរាជ័យ",
    warning: "ការដាស់តឿន",
    info: "ដំណឹង / ព័ត៌មាន",
  };

  const icons = {
    success: '<i class="fa-solid fa-circle-check"></i>',
    danger: '<i class="fa-solid fa-circle-xmark"></i>',
    warning: '<i class="fa-solid fa-triangle-exclamation"></i>',
    info: '<i class="fa-solid fa-circle-info"></i>',
  };

  const toastTitle = title || defaultTitles[type];
  const toastIcon = icons[type];

  const toast = document.createElement("div");
  toast.className = `toast-item toast-${type}`;
  toast.innerHTML = `
    <div class="toast-icon">
      ${toastIcon}
    </div>
    <div class="toast-content">
      <div class="toast-title">${toastTitle}</div>
      <div class="toast-message">${message}</div>
    </div>
    <button type="button" class="toast-close" title="បិទ" aria-label="Close">
      <i class="fa-solid fa-xmark"></i>
    </button>
    <div class="toast-progress"></div>
  `;

  container.appendChild(toast);

  const progressBar = toast.querySelector(".toast-progress");
  const closeBtn = toast.querySelector(".toast-close");

  let startTime = Date.now();
  let remaining = duration;
  let timerId = null;
  let isPaused = false;

  // Animate progress bar using CSS transitions
  progressBar.style.transition = `transform ${duration}ms linear`;
  requestAnimationFrame(() => {
    progressBar.style.transform = "scaleX(0)";
  });

  function removeToast() {
    clearTimeout(timerId);
    toast.classList.add("toast-hiding");
    toast.addEventListener("animationend", () => {
      if (toast.parentElement) {
        toast.parentElement.removeChild(toast);
      }
    });
  }

  function startTimer() {
    startTime = Date.now();
    timerId = setTimeout(removeToast, remaining);
  }

  function pauseTimer() {
    clearTimeout(timerId);
    remaining -= Date.now() - startTime;
    progressBar.style.transition = "none";
  }

  function resumeTimer() {
    if (remaining > 0) {
      progressBar.style.transition = `transform ${remaining}ms linear`;
      startTimer();
    }
  }

  // Hover to pause countdown
  toast.addEventListener("mouseenter", () => {
    isPaused = true;
    pauseTimer();
  });

  toast.addEventListener("mouseleave", () => {
    isPaused = false;
    resumeTimer();
  });

  closeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    removeToast();
  });

  startTimer();
  return toast;
}

// Global Toast Shortcut Object
window.toast = {
  success: (msg, title, duration) => showToast(msg, "success", title, duration),
  danger: (msg, title, duration) => showToast(msg, "danger", title, duration),
  error: (msg, title, duration) => showToast(msg, "danger", title, duration),
  warning: (msg, title, duration) => showToast(msg, "warning", title, duration),
  info: (msg, title, duration) => showToast(msg, "info", title, duration),
};

window.showToast = showToast;

/**
 * Initialize Flashed Messages from Server as Toasts
 */
function initFlashToasts() {
  const flashElements = document.querySelectorAll(".server-flash-message");
  flashElements.forEach((el, index) => {
    const category = el.getAttribute("data-category") || "info";
    const message = el.getAttribute("data-message") || el.innerText.trim();
    if (message) {
      setTimeout(() => {
        showToast(message, category);
      }, index * 200 + 100);
    }
    el.remove();
  });
}

// ==============================================================================
// 2. KHMER LIVE CLOCK
// ==============================================================================
function initLiveClock() {
  const clockEl = document.getElementById("live-time-display");
  if (!clockEl) return;

  const khmerDigits = ["០", "១", "២", "៣", "៤", "៥", "៦", "៧", "៨", "៩"];
  const toKh = (num) =>
    String(num)
      .padStart(2, "0")
      .split("")
      .map((c) => khmerDigits[parseInt(c)] || c)
      .join("");

  function update() {
    const now = new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes();
    const seconds = now.getSeconds();
    const period = hours >= 12 ? "រសៀល" : "ព្រឹក";
    const h12 = hours % 12 || 12;

    clockEl.innerText = `ម៉ោង ${toKh(h12)}:${toKh(minutes)}:${toKh(
      seconds
    )} ${period}`;
  }

  update();
  setInterval(update, 1000);
}

// ==============================================================================
// 3. MODALS CONTROL
// ==============================================================================
function initModals() {
  // Open modal triggers
  document.querySelectorAll("[data-modal-target]").forEach((trigger) => {
    trigger.addEventListener("click", function () {
      const targetId = this.getAttribute("data-modal-target");
      const modal = document.getElementById(targetId);
      if (modal) {
        modal.classList.add("show");
      }
    });
  });

  // Close buttons
  document
    .querySelectorAll(".modal-close, [data-modal-close]")
    .forEach((btn) => {
      btn.addEventListener("click", function () {
        const modal = this.closest(".modal-backdrop");
        if (modal) {
          modal.classList.remove("show");
        }
      });
    });

  // Close when clicking on backdrop
  document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
    backdrop.addEventListener("click", function (e) {
      if (e.target === this) {
        this.classList.remove("show");
      }
    });
  });
}

// ==============================================================================
// 4. DEMO ACCOUNT AUTO FILLER ON LOGIN
// ==============================================================================
function initDemoAccountFiller() {
  document.querySelectorAll(".demo-account-pill").forEach((pill) => {
    pill.addEventListener("click", function () {
      const u = this.getAttribute("data-user");
      const p = this.getAttribute("data-pass");
      const roleText = this.querySelector(".pill-role") ? this.querySelector(".pill-role").innerText : u;
      const userInp = document.getElementById("username");
      const passInp = document.getElementById("password");
      if (userInp && passInp) {
        userInp.value = u;
        passInp.value = p;
        // Visual indicator
        pill.style.transform = "scale(0.95)";
        setTimeout(() => (pill.style.transform = "scale(1)"), 150);

        if (window.toast) {
          toast.info(`បានជ្រើសរើសគណនីសាកល្បង៖ ${roleText}`, "បំពេញគណនីស្វ័យប្រវត្តិ");
        }
      }
    });
  });
}

// ==============================================================================
// 5. CLIENT-SIDE TABLE FILTER
// ==============================================================================
function initTableSearch() {
  const searchInput = document.getElementById("table-client-search");
  if (!searchInput) return;

  const targetTable = document.querySelector(".filterable-table");
  if (!targetTable) return;

  searchInput.addEventListener("input", function () {
    const query = this.value.toLowerCase().trim();
    const rows = targetTable.querySelectorAll("tbody tr");

    rows.forEach((row) => {
      const text = row.innerText.toLowerCase();
      if (text.includes(query)) {
        row.style.display = "";
      } else {
        row.style.display = "none";
      }
    });
  });
}

// ==============================================================================
// 6. QUICK CHECK-IN AJAX WITH TOAST
// ==============================================================================
function handleQuickCheckin() {
  const btn = document.getElementById("btn-quick-checkin");
  if (!btn) return;

  btn.disabled = true;
  const originalHtml = btn.innerHTML;
  btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> <span>កំពុងកត់ត្រា...</span>`;

  fetch("/attendance/quick-checkin", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.success) {
        if (window.toast) {
          toast.success(data.message, "កត់ត្រាវត្តមានជោគជ័យ");
        }
        setTimeout(() => {
          location.reload();
        }, 1200);
      } else {
        if (window.toast) {
          toast.warning(data.message || "មានបញ្ហាក្នុងការកត់ត្រា!", "ការកត់ត្រាវត្តមាន");
        }
        btn.disabled = false;
        btn.innerHTML = originalHtml;
      }
    })
    .catch((err) => {
      if (window.toast) {
        toast.error("មានបញ្ហាបច្ចេកទេសក្នុងការតភ្ជាប់!", "កំហុសបណ្តាញ");
      }
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    });
}

// ==============================================================================
// 7. PRINT HELPER
// ==============================================================================
function triggerPrint() {
  window.print();
}

// ==============================================================================
// 8. SIDEBAR CONTROLS (COLLAPSE & MOBILE DRAWER)
// ==============================================================================
function initSidebarControls() {
  const sidebar = document.getElementById("app-sidebar") || document.querySelector(".sidebar");
  const toggleBtn = document.getElementById("sidebar-toggle-btn");
  const collapseBtn = document.getElementById("sidebar-collapse-btn");
  const closeBtn = document.getElementById("sidebar-close-btn");
  const overlay = document.getElementById("sidebar-overlay");

  if (!sidebar) return;

  // Restore Desktop Collapsed State from localStorage
  const savedState = localStorage.getItem("np_sidebar_collapsed");
  if (savedState === "true" && window.innerWidth > 992) {
    document.body.classList.add("sidebar-collapsed");
  }

  function openMobileSidebar() {
    document.body.classList.add("sidebar-open");
    sidebar.classList.add("show");
    if (overlay) overlay.classList.add("show");
  }

  function closeMobileSidebar() {
    document.body.classList.remove("sidebar-open");
    sidebar.classList.remove("show");
    if (overlay) overlay.classList.remove("show");
  }

  function toggleMobileSidebar() {
    if (document.body.classList.contains("sidebar-open") || sidebar.classList.contains("show")) {
      closeMobileSidebar();
    } else {
      openMobileSidebar();
    }
  }

  function toggleDesktopSidebar() {
    const isCollapsed = document.body.classList.toggle("sidebar-collapsed");
    localStorage.setItem("np_sidebar_collapsed", isCollapsed ? "true" : "false");
  }

  // Handle Main Toggle Button (Topbar)
  if (toggleBtn) {
    toggleBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (window.innerWidth <= 992) {
        toggleMobileSidebar();
      } else {
        toggleDesktopSidebar();
      }
    });
  }

  // Handle Collapse Button (Inside Sidebar Header)
  if (collapseBtn) {
    collapseBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (window.innerWidth <= 992) {
        closeMobileSidebar();
      } else {
        document.body.classList.add("sidebar-collapsed");
        localStorage.setItem("np_sidebar_collapsed", "true");
      }
    });
  }

  // Handle Close / Hide Button (Inside Sidebar Header)
  if (closeBtn) {
    closeBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (window.innerWidth <= 992) {
        closeMobileSidebar();
      } else {
        document.body.classList.toggle("sidebar-collapsed");
        const isCollapsed = document.body.classList.contains("sidebar-collapsed");
        localStorage.setItem("np_sidebar_collapsed", isCollapsed ? "true" : "false");
      }
    });
  }

  // Handle Overlay Click
  if (overlay) {
    overlay.addEventListener("click", function (e) {
      e.stopPropagation();
      closeMobileSidebar();
    });
  }

  // Close when pressing Escape key
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      if (document.body.classList.contains("sidebar-open")) {
        closeMobileSidebar();
      }
    }
  });

  // Auto close drawer when clicking a navigation link on mobile/tablet
  const navLinks = sidebar.querySelectorAll(".nav-link");
  navLinks.forEach((link) => {
    link.addEventListener("click", function () {
      if (window.innerWidth <= 992) {
        closeMobileSidebar();
      }
    });
  });

  // Automatically handle screen resize
  window.addEventListener("resize", function () {
    if (window.innerWidth > 992) {
      if (document.body.classList.contains("sidebar-open")) {
        closeMobileSidebar();
      }
      if (localStorage.getItem("np_sidebar_collapsed") === "true") {
        document.body.classList.add("sidebar-collapsed");
      } else {
        document.body.classList.remove("sidebar-collapsed");
      }
    } else {
      document.body.classList.remove("sidebar-collapsed");
    }
  });
}

// ==============================================================================
// 9. INSTANT NAVIGATION PROGRESS & LINK PREFETCHING
// ==============================================================================
function initPageTransitionsAndPrefetch() {
  const progressBar = document.getElementById("top-progress-bar");
  const prefetchedUrls = new Set();

  function startProgress() {
    if (!progressBar) return;
    progressBar.classList.remove("done");
    progressBar.classList.add("loading");
  }

  function finishProgress() {
    if (!progressBar) return;
    progressBar.classList.remove("loading");
    progressBar.classList.add("done");
    setTimeout(() => {
      progressBar.classList.remove("done");
    }, 400);
  }

  // Finish progress on initial load
  finishProgress();

  // Prefetch internal URLs on hover
  function prefetchUrl(url) {
    if (!url || prefetchedUrls.has(url)) return;
    if (url.startsWith("#") || url.startsWith("javascript:") || url.includes("/logout")) return;
    try {
      const parsed = new URL(url, window.location.origin);
      if (parsed.origin !== window.location.origin) return;
      
      prefetchedUrls.add(url);
      const link = document.createElement("link");
      link.rel = "prefetch";
      link.href = url;
      document.head.appendChild(link);
    } catch (e) {}
  }

  // Intercept internal link clicks for top progress bar
  document.addEventListener("click", function (e) {
    const link = e.target.closest("a");
    if (!link) return;
    const href = link.getAttribute("href");
    const target = link.getAttribute("target");

    if (
      href &&
      !href.startsWith("#") &&
      !href.startsWith("javascript:") &&
      !href.startsWith("tel:") &&
      !href.startsWith("mailto:") &&
      target !== "_blank" &&
      !e.ctrlKey &&
      !e.metaKey &&
      !e.shiftKey
    ) {
      try {
        const parsed = new URL(href, window.location.origin);
        if (parsed.origin === window.location.origin) {
          startProgress();
        }
      } catch (err) {}
    }
  });

  // Hover prefetching on navigation links
  document.addEventListener("mouseover", function (e) {
    const link = e.target.closest("a");
    if (link) {
      const href = link.getAttribute("href");
      if (href) prefetchUrl(href);
    }
  }, { passive: true });

  // Handle browser back/forward buttons
  window.addEventListener("pageshow", function (event) {
    finishProgress();
  });
}

// ==============================================================================
// 10. FLOATING BACK TO TOP BUTTON
// ==============================================================================
function initBackToTop() {
  const btn = document.getElementById("btn-back-to-top");
  if (!btn) return;

  let ticking = false;
  window.addEventListener("scroll", function () {
    if (!ticking) {
      window.requestAnimationFrame(function () {
        if (window.scrollY > 260) {
          btn.classList.add("show");
        } else {
          btn.classList.remove("show");
        }
        ticking = false;
      });
      ticking = true;
    }
  }, { passive: true });

  btn.addEventListener("click", function (e) {
    e.preventDefault();
    window.scrollTo({
      top: 0,
      behavior: "smooth"
    });
  });
}

// ==============================================================================
// 9. THEME TOGGLE (LIGHT & DARK MODE)
// ==============================================================================
function initThemeToggle() {
  const toggleBtn = document.getElementById("theme-toggle-btn");
  const toggleIcon = document.getElementById("theme-toggle-icon");

  if (!toggleBtn || !toggleIcon) return;

  function updateThemeUI(theme) {
    if (theme === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
      toggleIcon.className = "fa-solid fa-sun";
      toggleIcon.style.color = "#fbbf24";
      toggleBtn.setAttribute("title", "ប្តូរទៅ Light Mode (ពន្លឺ)");
    } else {
      document.documentElement.setAttribute("data-theme", "light");
      toggleIcon.className = "fa-solid fa-moon";
      toggleIcon.style.color = "#d97706";
      toggleBtn.setAttribute("title", "ប្តូរទៅ Dark Mode (ងងឹត)");
    }
  }

  // Read initial theme from localStorage or document
  const currentTheme = localStorage.getItem("np_theme") || document.documentElement.getAttribute("data-theme") || "light";
  updateThemeUI(currentTheme);

  // Toggle on click
  toggleBtn.addEventListener("click", function (e) {
    e.preventDefault();
    const activeTheme = document.documentElement.getAttribute("data-theme") || "light";
    const nextTheme = activeTheme === "dark" ? "light" : "dark";

    localStorage.setItem("np_theme", nextTheme);
    updateThemeUI(nextTheme);

    // Dispatch global event for charts to adapt colors
    window.dispatchEvent(new CustomEvent("themeChanged", { detail: { theme: nextTheme } }));

    // Provide friendly toast feedback in Khmer
    if (window.toast) {
      if (nextTheme === "dark") {
        toast.info("បានប្តូរទៅ Dark Mode (ផ្ទាំងងងឹត)", "រូបរាងកម្មវិធី");
      } else {
        toast.info("បានប្តូរទៅ Light Mode (ផ្ទាំងភ្លឺ)", "រូបរាងកម្មវិធី");
      }
    }
  });
}

// ==============================================================================
// 11. GLOBAL LOADING CIRCLE SYSTEM (ប្រព័ន្ធ Loading Circle ពេលរង់ចាំ/ទាញយកទិន្នន័យ)
// ==============================================================================

let _globalLoadingTimer = null;

/**
 * Show the global Loading Circle overlay
 * @param {string} title - Main loading title text in Khmer
 * @param {string} subtitle - Subtitle/description text in Khmer
 * @param {number} autoDismissMs - Auto hide timeout in ms (default 8000ms)
 */
function showLoading(title = "កំពុងដំណើរការ...", subtitle = "សូមរង់ចាំមួយភ្លែត ប្រព័ន្ធកំពុងទាញយកទិន្នន័យ", autoDismissMs = 8000) {
  const overlay = document.getElementById("global-loading-overlay");
  const titleEl = document.getElementById("global-loading-title");
  const subtitleEl = document.getElementById("global-loading-subtitle");

  if (titleEl) titleEl.textContent = title;
  if (subtitleEl) subtitleEl.textContent = subtitle;

  if (_globalLoadingTimer) {
    clearTimeout(_globalLoadingTimer);
    _globalLoadingTimer = null;
  }

  if (overlay) {
    overlay.style.display = "flex";
    requestAnimationFrame(function () {
      overlay.classList.add("active");
      overlay.setAttribute("aria-hidden", "false");
    });
  }

  // Safety fallback: auto-hide after autoDismissMs (default 8s) if page didn't unload
  if (autoDismissMs && autoDismissMs > 0) {
    _globalLoadingTimer = setTimeout(function () {
      hideLoading();
      document.querySelectorAll(".is-loading").forEach(function (btn) {
        resetButtonLoading(btn);
      });
    }, autoDismissMs);
  }
}

/**
 * Hide the global Loading Circle overlay
 */
function hideLoading() {
  if (_globalLoadingTimer) {
    clearTimeout(_globalLoadingTimer);
    _globalLoadingTimer = null;
  }
  const overlay = document.getElementById("global-loading-overlay");
  if (overlay) {
    overlay.classList.remove("active");
    overlay.setAttribute("aria-hidden", "true");
    setTimeout(function () {
      if (!overlay.classList.contains("active")) {
        overlay.style.display = "none";
      }
    }, 280);
  }
}

// Attach to window object for global access
window.showLoading = showLoading;
window.hideLoading = hideLoading;

/**
 * Set a button into loading state with inline spinning circle
 * @param {HTMLElement} btn - The button element
 * @param {string} text - Optional loading text
 */
function setButtonLoading(btn, text = "កំពុងដំណើរការ...") {
  if (!btn) return;
  if (btn.getAttribute("data-original-html") === null) {
    btn.setAttribute("data-original-html", btn.innerHTML);
  }
  btn.disabled = true;
  btn.classList.add("is-loading");
  btn.innerHTML = `<span class="spinner-circle-sm"></span> <span>${text}</span>`;
}

/**
 * Restore button from loading state
 * @param {HTMLElement} btn - The button element
 */
function resetButtonLoading(btn) {
  if (!btn) return;
  const original = btn.getAttribute("data-original-html");
  if (original !== null) {
    btn.innerHTML = original;
    btn.removeAttribute("data-original-html");
  }
  btn.disabled = false;
  btn.classList.remove("is-loading");
}

window.setButtonLoading = setButtonLoading;
window.resetButtonLoading = resetButtonLoading;

function initLoadingCircleSystem() {
  // 1. Auto-intercept form submissions (except forms marked data-no-loading or preventDefault)
  document.addEventListener("submit", function (e) {
    if (e.defaultPrevented) return;
    const form = e.target;
    if (!form || form.tagName !== "FORM") return;
    if (
      form.hasAttribute("data-no-loading") ||
      form.classList.contains("no-loading") ||
      form.id === "manual-scan-form" ||
      form.id === "deductionForm" ||
      form.id === "changePhotoForm"
    ) {
      return;
    }

    // Check HTML5 validity
    if (form.checkValidity && !form.checkValidity()) {
      return;
    }

    const action = (form.getAttribute("action") || window.location.pathname).toLowerCase();
    const submitBtn = form.querySelector("button[type='submit'], input[type='submit']");

    let title = "កំពុងដំណើរការ...";
    let subtitle = "សូមរង់ចាំមួយភ្លែត ប្រព័ន្ធកំពុងទាញយក និងរក្សាទុកទិន្នន័យ";

    if (action.includes("login") || form.id === "loginForm") {
      title = "កំពុងផ្ទៀងផ្ទាត់...";
      subtitle = "សូមរង់ចាំមួយភ្លែត ប្រព័ន្ធកំពុងដំណើរការចូលគណនី";
    } else if (action.includes("payroll") && (action.includes("generate") || action.includes("calculate"))) {
      title = "កំពុងគណនាប្រាក់បៀវត្សរ៍...";
      subtitle = "ប្រព័ន្ធកំពុងដំណើរការគណនាប្រាក់បៀវត្សរ៍ និងប្រាក់ឧបត្ថម្ភជូនមន្ត្រី";
    } else if (action.includes("export") || action.includes("excel") || action.includes("pdf")) {
      title = "កំពុងទាញយកទិន្នន័យ...";
      subtitle = "ប្រព័ន្ធកំពុងទាញយក និងបង្កើតឯកសារ Excel/PDF...";
      setTimeout(hideLoading, 3000);
    } else if (action.includes("delete") || (form.getAttribute("onsubmit") && form.getAttribute("onsubmit").includes("confirm"))) {
      title = "កំពុងលុបទិន្នន័យ...";
      subtitle = "សូមរង់ចាំមួយភ្លែត...";
    } else if (action.includes("handover")) {
      title = "កំពុងផ្ទេរការកាន់កាប់...";
      subtitle = "កំពុងកត់ត្រាការផ្ទេរការគ្រប់គ្រងសម្ភារៈ...";
    } else if (action.includes("maintenance")) {
      title = "កំពុងកត់ត្រាការជួសជុល...";
      subtitle = "កំពុងរក្សាទុកប្រវត្តិថែទាំសម្ភារៈ...";
    } else if (action.includes("attendance")) {
      title = "កំពុងកត់ត្រាវត្តមាន...";
      subtitle = "កំពុងរក្សាទុកទិន្នន័យវត្តមាន...";
    } else if (form.method.toUpperCase() === "GET") {
      title = "កំពុងស្វែងរក & ចម្រាញ់ទិន្នន័យ...";
      subtitle = "សូមរង់ចាំមួយភ្លែត ប្រព័ន្ធកំពុងផ្ទុកទិន្នន័យ...";
    } else {
      title = "កំពុងរក្សាទុកទិន្នន័យ...";
      subtitle = "សូមរង់ចាំមួយភ្លែត ប្រព័ន្ធកំពុងធ្វើបច្ចុប្បន្នភាពទិន្នន័យ";
    }

    if (submitBtn) {
      setButtonLoading(submitBtn, "កំពុងដំណើរការ...");
    }
    showLoading(title, subtitle);
  });

  // 2. Auto-intercept Excel, PDF, and Reports Export download links
  document.addEventListener("click", function (e) {
    const link = e.target.closest("a");
    if (!link) return;
    const href = link.getAttribute("href") || "";

    if (
      href.includes("export_excel") ||
      href.includes("export_pdf") ||
      href.includes("/export_") ||
      href.includes("/download") ||
      link.classList.contains("btn-export-excel") ||
      (link.classList.contains("btn-success") && href.includes("export"))
    ) {
      showLoading("កំពុងទាញយកទិន្នន័យ...", "ប្រព័ន្ធកំពុងទាញយក និងរៀបចំឯកសារ Excel/PDF...", 2800);
    }
  });

  // 3. User Escape / Click Dismiss
  const overlay = document.getElementById("global-loading-overlay");
  if (overlay) {
    overlay.addEventListener("click", function () {
      hideLoading();
      document.querySelectorAll(".is-loading").forEach(function (btn) {
        resetButtonLoading(btn);
      });
    });
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      hideLoading();
      document.querySelectorAll(".is-loading").forEach(function (btn) {
        resetButtonLoading(btn);
      });
    }
  });

  // 4. Auto hide on page restoration (back/forward bfcache)
  window.addEventListener("pageshow", function () {
    hideLoading();
    document.querySelectorAll(".is-loading").forEach(function (btn) {
      resetButtonLoading(btn);
    });
  });
}

// ==============================================================================
// 12. PWA SERVICE WORKER & DESKTOP INSTALLATION
// ==============================================================================
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker
      .register("/sw.js")
      .then(function (reg) {
        console.log("[PWA] Service Worker registered:", reg.scope);
      })
      .catch(function (err) {
        console.log("[PWA] Service Worker registration notice:", err);
      });
  });
}



