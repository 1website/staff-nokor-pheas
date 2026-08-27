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
// 8. SIDEBAR CONTROLS (AUTO HIDE, COLLAPSE & MOBILE DRAWER)
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
    
    // Smooth transition feedback
    if (window.toast) {
      if (isCollapsed) {
        toast.info("បានលាក់ផ្ទាំងម៉ឺនុយ (Collapsed Sidebar)", "ប្លង់ទូលាយ");
      }
    }
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
        if (window.toast) {
          toast.info("បានលាក់ផ្ទាំងម៉ឺនុយ (Collapsed Sidebar)", "ប្លង់ទូលាយ");
        }
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
        document.body.classList.add("sidebar-collapsed");
        localStorage.setItem("np_sidebar_collapsed", "true");
        if (window.toast) {
          toast.info("បានលាក់ផ្ទាំងម៉ឺនុយ (Collapsed Sidebar)", "ប្លង់ទូលាយ");
        }
      }
    });
  }

  // 5 Seconds Inactivity Auto-Hide Timer (5,000 ms)
  const AUTO_HIDE_SIDEBAR_MS = 5 * 1000;
  let autoHideTimer = null;
  let isMouseOverSidebar = false;

  sidebar.addEventListener("mouseenter", function () {
    isMouseOverSidebar = true;
    if (autoHideTimer) {
      clearTimeout(autoHideTimer);
      autoHideTimer = null;
    }
  });

  sidebar.addEventListener("mouseleave", function () {
    isMouseOverSidebar = false;
    resetAutoHideTimer();
  });

  function resetAutoHideTimer() {
    if (autoHideTimer) {
      clearTimeout(autoHideTimer);
      autoHideTimer = null;
    }

    if (isMouseOverSidebar) return;

    const isDesktopExpanded = window.innerWidth > 992 && !document.body.classList.contains("sidebar-collapsed");
    const isMobileOpen = window.innerWidth <= 992 && (document.body.classList.contains("sidebar-open") || sidebar.classList.contains("show"));

    if (isDesktopExpanded || isMobileOpen) {
      autoHideTimer = setTimeout(function () {
        if (isMouseOverSidebar) return;
        if (window.innerWidth > 992) {
          document.body.classList.add("sidebar-collapsed");
          localStorage.setItem("np_sidebar_collapsed", "true");
        } else {
          closeMobileSidebar();
        }
      }, AUTO_HIDE_SIDEBAR_MS);
    }
  }

  // Reset auto-hide timer on user interaction
  ["mousemove", "mousedown", "keydown", "touchstart", "scroll"].forEach(function (evt) {
    document.addEventListener(evt, resetAutoHideTimer, { passive: true });
  });

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
    resetAutoHideTimer();
  });

  // Start initial auto-hide countdown
  resetAutoHideTimer();
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
