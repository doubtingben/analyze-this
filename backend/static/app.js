// DOM Elements
const loadingEl = document.getElementById("loading");
const emptyStateEl = document.getElementById("empty-state");
const itemsContainerEl = document.getElementById("items-container");
const userNameEl = document.getElementById("user-name");
const userInfoEl = document.getElementById("user-info");
const userMenuTriggerEl = document.getElementById("user-menu-trigger");
const userMenuEl = document.getElementById("user-menu");
const loginStateEl = document.getElementById("login-state");
const filtersEl = document.getElementById("filters");
const showHiddenEl = document.getElementById("show-archive");
const exportBtnEl = document.getElementById("export-btn");
const newItemBtn = document.getElementById("new-item-btn");
const createModal = document.getElementById("create-modal");
const createForm = document.getElementById("create-form");
const itemTypeSelect = document.getElementById("item-type");
const modalCloseBtn = document.getElementById("modal-close");
const cancelCreateBtn = document.getElementById("cancel-create");
const detailModal = document.getElementById("detail-modal");
const detailBackdrop = document.getElementById("detail-modal-backdrop");
const detailCloseBtn = document.getElementById("detail-modal-close");
const detailEditBtn = document.getElementById("detail-edit-btn");
const detailTitleEl = document.getElementById("detail-title");
const detailTitleInput = document.getElementById("detail-title-input");
const detailTypeEl = document.getElementById("detail-type");
const detailContentEl = document.getElementById("detail-content");
const detailTagsEl = document.getElementById("detail-tags");
const detailTagsEditor = document.getElementById("detail-tags-editor");
const detailTagInput = document.getElementById("detail-tag-input");
const detailAddTagBtn = document.getElementById("detail-add-tag");
const detailEditActions = document.getElementById("detail-edit-actions");
const detailCancelBtn = document.getElementById("detail-cancel-btn");
const detailSaveBtn = document.getElementById("detail-save-btn");
const detailNotesList = document.getElementById("detail-notes-list");
const detailNotesLoading = document.getElementById("detail-notes-loading");
const detailNoteForm = document.getElementById("detail-note-form");
const detailNoteText = document.getElementById("detail-note-text");
const detailNoteFollowUp = document.getElementById("detail-note-follow-up");
const detailItemIdEl = document.getElementById("detail-item-id");
const detailFollowUpEl = document.getElementById("detail-follow-up");
const detailFollowUpContentEl = document.getElementById(
  "detail-follow-up-content",
);
const detailFollowUpDeleteBtn = document.getElementById(
  "detail-follow-up-delete",
);
const metricsBtnEl = document.getElementById("metrics-btn");
const metricsModal = document.getElementById("metrics-modal");
const metricsModalBackdrop = document.getElementById("metrics-modal-backdrop");
const metricsModalClose = document.getElementById("metrics-modal-close");
const metricsLoading = document.getElementById("metrics-loading");
const metricsError = document.getElementById("metrics-error");
const metricsContent = document.getElementById("metrics-content");
const metricsTotalCount = document.getElementById("metrics-total-count");
const metricsStatusList = document.getElementById("metrics-status-list");
const metricsWorkerSection = document.getElementById("metrics-worker-section");
const metricsWorkerTotal = document.getElementById("metrics-worker-total");
const metricsWorkerList = document.getElementById("metrics-worker-list");
const searchInputEl = document.getElementById("search-input");
const filterBtnEl = document.getElementById("filter-btn");
const filterCountEl = document.getElementById("filter-count");
const filterModal = document.getElementById("filter-modal");
const filterModalBackdrop = document.getElementById("filter-modal-backdrop");
const filterModalCloseBtn = document.getElementById("filter-modal-close");
const filterTypesEl = document.getElementById("filter-types");
const filterTagsEl = document.getElementById("filter-tags");
const filterApplyBtn = document.getElementById("filter-apply-btn");
const filterClearBtn = document.getElementById("filter-clear-btn");
const tagEditorBtn = document.getElementById("tag-editor-btn");
const tagEditorModal = document.getElementById("tag-editor-modal");
const tagEditorModalBackdrop = document.getElementById(
  "tag-editor-modal-backdrop",
);
const tagEditorModalClose = document.getElementById("tag-editor-modal-close");
const tagSearchInput = document.getElementById("tag-search-input");
const tagSortSelect = document.getElementById("tag-sort-select");
const tagEditorCount = document.getElementById("tag-editor-count");
const tagEditorList = document.getElementById("tag-editor-list");
const detailTimelineEl = document.getElementById("detail-timeline");
const detailTimelineToggle = document.getElementById("detail-timeline-toggle");
const detailTimelineContent = document.getElementById(
  "detail-timeline-content",
);
const detailTimelineCount = document.getElementById("detail-timeline-count");
const detailTimelineList = document.getElementById("detail-timeline-list");
const detailTimelineAddContainer = document.getElementById(
  "detail-timeline-add-container",
);
const detailTimelineAddBtn = document.getElementById("detail-timeline-add-btn");
const followUpCountBadgeEl = document.getElementById("follow-up-count-badge");

// State
let allItems = [];
let currentView = "all"; // 'all', 'timeline', 'follow_up', or 'media'
let selectedTypes = new Set(); // Empty = all types
let selectedTags = new Set(); // Empty = no tag filter
let searchQuery = ""; // Empty = no search
let showHidden = false;
let currentDetailItem = null;
let detailEditMode = false;
let editableTags = [];
let noteCounts = {};
let searchDebounceTimer;
let pendingSelectedTypes = new Set(); // Temporary selection in modal
let pendingSelectedTags = new Set(); // Temporary selection in modal
let tagSearchQuery = ""; // Tag editor search
let tagSortMode = "name"; // Tag editor sort mode
let currentUserTimezone = "America/New_York"; // Default timezone
let isTimelineExpanded = false; // Timeline section expansion state

const VIEW_PATHS = {
  all: "/",
  timeline: "/timeline",
  follow_up: "/followup",
  media: "/media",
};

function getPathForView(view) {
  return VIEW_PATHS[view] || "/";
}

function normalizeView(view) {
  return VIEW_PATHS[view] ? view : "all";
}

function normalizePathname(pathname) {
  if (!pathname) return "/";
  if (pathname.length > 1 && pathname.endsWith("/")) {
    return pathname.slice(0, -1);
  }
  return pathname;
}

function getViewFromPathname(pathname) {
  const normalized = normalizePathname(pathname).toLowerCase();
  if (normalized === "/timeline") return "timeline";
  if (normalized === "/followup" || normalized === "/follow-up") return "follow_up";
  if (normalized === "/media") return "media";
  return "all";
}

function updateViewButtons() {
  document.querySelectorAll(".view-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === currentView);
  });
}

function updateUrlForView(view, replace = false) {
  const targetPath = getPathForView(view);
  if (window.location.pathname === targetPath) return;
  const suffix = `${window.location.search || ""}${window.location.hash || ""}`;
  const targetUrl = `${targetPath}${suffix}`;
  if (replace) {
    window.history.replaceState({ view }, "", targetUrl);
  } else {
    window.history.pushState({ view }, "", targetUrl);
  }
}

function setView(view, options = {}) {
  const { push = true } = options;
  const nextView = normalizeView(view);
  if (currentView === nextView) return;
  currentView = nextView;
  updateViewButtons();
  if (push) {
    updateUrlForView(nextView, false);
  }
  renderFilteredItems();
}

// Helper to get cookies
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
}

function getCsrfHeaders() {
  const token = getCookie("csrf_token");
  return token ? { "X-CSRF-Token": token } : {};
}

// Initialize the app
async function init() {
  try {
    const user = await fetchUser();
    if (!user) {
      showLoginState();
      return;
    }
    if (user.timezone) {
      currentUserTimezone = user.timezone;
    }
    userNameEl.textContent = `Welcome, ${user.name || user.email}`;

    // Show new item button for logged in users
    newItemBtn.style.display = "block";

    currentView = getViewFromPathname(window.location.pathname);

    // Setup filter controls
    setupFilters();
    setupUserMenu();
    setupSearchInput();
    setupFilterModal();
    updateViewButtons();
    updateUrlForView(currentView, true);

    window.addEventListener("popstate", () => {
      const view = getViewFromPathname(window.location.pathname);
      if (view === currentView) return;
      currentView = view;
      updateViewButtons();
      renderFilteredItems();
    });

    // Setup create modal
    setupCreateModal();
    setupDetailModal();
    setupMetricsModal();
    setupTagEditor();

    allItems = await fetchItems();
    await fetchNoteCounts(allItems);
    renderFilteredItems();
  } catch (error) {
    console.error("Initialization error:", error);
    showLoginState();
  }
}

function setupDetailModal() {
  if (!detailModal) return;

  detailCloseBtn.addEventListener("click", closeDetailModal);
  detailBackdrop.addEventListener("click", closeDetailModal);

  detailEditBtn.addEventListener("click", () => {
    setDetailEditMode(!detailEditMode);
  });

  detailCancelBtn.addEventListener("click", () => {
    setDetailEditMode(false);
  });

  detailSaveBtn.addEventListener("click", saveDetailEdits);

  detailAddTagBtn.addEventListener("click", (event) => {
    event.preventDefault();
    const tag = detailTagInput.value.trim();
    if (!tag) return;
    if (!editableTags.includes(tag)) {
      editableTags.push(tag);
      renderDetailTags();
    }
    detailTagInput.value = "";
  });

  if (detailFollowUpDeleteBtn) {
    detailFollowUpDeleteBtn.addEventListener("click", confirmDeleteFollowUp);
  }

  // Timeline toggle
  if (detailTimelineToggle) {
    detailTimelineToggle.addEventListener("click", toggleTimeline);
  }

  detailNoteForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!currentDetailItem) return;
    const text = detailNoteText.value.trim();
    if (!text) return;
    const itemId = getItemId(currentDetailItem);

    const formData = new FormData();
    formData.append("text", text);
    const isFollowUp = detailNoteFollowUp.checked;
    formData.append("note_type", isFollowUp ? "follow_up" : "context");

    try {
      const response = await fetch(`/api/items/${itemId}/notes`, {
        method: "POST",
        headers: {
          ...getCsrfHeaders(),
        },
        body: formData,
      });
      if (!response.ok) {
        throw new Error("Failed to add note");
      }
      detailNoteText.value = "";
      detailNoteFollowUp.checked = false;
      const note = await response.json();
      await loadDetailNotes();
    } catch (error) {
      alert(error.message || "Failed to add note");
    }
  });
}

// Setup create modal event listeners
function setupCreateModal() {
  // Open modal
  newItemBtn.addEventListener("click", () => {
    createModal.style.display = "flex";
    createForm.reset();
    updateTypeFields();
  });

  // Close modal
  modalCloseBtn.addEventListener("click", closeModal);
  cancelCreateBtn.addEventListener("click", closeModal);
  createModal
    .querySelector(".modal-backdrop")
    .addEventListener("click", closeModal);

  // Type selection changes visible fields
  itemTypeSelect.addEventListener("change", updateTypeFields);

  // Form submission
  createForm.addEventListener("submit", handleCreateSubmit);

  // Update file hint based on type
  itemTypeSelect.addEventListener("change", () => {
    const fileHint = document.getElementById("file-hint");
    const type = itemTypeSelect.value;
    const hints = {
      image: "Select an image file (PNG, JPG, GIF, etc.)",
      video: "Select a video file (MP4, MOV, etc.)",
      audio: "Select an audio file (MP3, WAV, etc.)",
      file: "Select any file to upload",
    };
    fileHint.textContent = hints[type] || "Select a file to upload";
  });
}

function closeModal() {
  createModal.style.display = "none";
  createForm.reset();
  updateTypeFields();
}

function updateTypeFields() {
  const selectedType = itemTypeSelect.value;
  document.querySelectorAll(".type-field").forEach((field) => {
    const types = field.dataset.types.split(",");
    if (types.includes(selectedType)) {
      field.classList.add("visible");
    } else {
      field.classList.remove("visible");
    }
  });
}

async function handleCreateSubmit(e) {
  e.preventDefault();

  const submitBtn = document.getElementById("submit-create");
  const originalText = submitBtn.textContent;
  submitBtn.disabled = true;
  submitBtn.textContent = "Creating...";

  try {
    const type = itemTypeSelect.value;
    const title = document.getElementById("item-title").value;

    const formData = new FormData();
    formData.append("type", type);
    if (title) formData.append("title", title);

    // Add content based on type
    if (type === "text") {
      const content = document.getElementById("item-text").value;
      if (!content) {
        alert("Please enter text content");
        return;
      }
      formData.append("content", content);
    } else if (type === "web_url") {
      const url = document.getElementById("item-url").value;
      if (!url) {
        alert("Please enter a URL");
        return;
      }
      formData.append("content", url);
    } else {
      // File types
      const fileInput = document.getElementById("item-file");
      const file = fileInput.files[0];
      if (!file) {
        alert("Please select a file");
        return;
      }
      formData.append("file", file);
      formData.append("file_name", file.name);
      formData.append("mime_type", file.type);
      formData.append("file_size", file.size);
    }

    const response = await fetch("/api/share", {
      method: "POST",
      headers: {
        ...getCsrfHeaders(),
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || "Failed to create item");
    }

    // Refresh items and close modal
    allItems = await fetchItems();
    await fetchNoteCounts(allItems);
    renderFilteredItems();
    closeModal();
  } catch (error) {
    console.error("Create error:", error);
    alert("Failed to create item: " + error.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = originalText;
  }
}

// Setup filter event listeners
function setupFilters() {
  // View toggle buttons
  document.querySelectorAll(".view-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      setView(btn.dataset.view, { push: true });
    });
  });

  if (showHiddenEl) {
    showHidden = showHiddenEl.checked;
    showHiddenEl.addEventListener("change", () => {
      showHidden = showHiddenEl.checked;
      renderFilteredItems();
    });
  }
}

function setupUserMenu() {
  if (userMenuTriggerEl) {
    userMenuTriggerEl.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleUserMenu();
    });
  }

  if (exportBtnEl) {
    exportBtnEl.addEventListener("click", () => {
      window.location.href = "/api/export";
      closeUserMenu();
    });
  }

  document.addEventListener("click", (event) => {
    if (!userMenuEl || !userMenuTriggerEl) return;
    if (
      userMenuEl.contains(event.target) ||
      userMenuTriggerEl.contains(event.target)
    ) {
      return;
    }
    closeUserMenu();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeUserMenu();
    }
  });
}

function setupMetricsModal() {
  if (!metricsModal) return;

  if (metricsBtnEl) {
    metricsBtnEl.addEventListener("click", () => {
      closeUserMenu();
      openMetricsModal();
    });
  }

  if (metricsModalClose) {
    metricsModalClose.addEventListener("click", closeMetricsModal);
  }

  if (metricsModalBackdrop) {
    metricsModalBackdrop.addEventListener("click", closeMetricsModal);
  }
}

function openMetricsModal() {
  if (!metricsModal) return;
  metricsModal.style.display = "flex";
  fetchMetrics();
}

// Tag Editor functions
function setupTagEditor() {
  if (!tagEditorModal) return;

  if (tagEditorBtn) {
    tagEditorBtn.addEventListener("click", () => {
      closeUserMenu();
      openTagEditorModal();
    });
  }

  if (tagEditorModalClose) {
    tagEditorModalClose.addEventListener("click", closeTagEditorModal);
  }

  if (tagEditorModalBackdrop) {
    tagEditorModalBackdrop.addEventListener("click", closeTagEditorModal);
  }

  if (tagSearchInput) {
    tagSearchInput.addEventListener("input", (e) => {
      tagSearchQuery = e.target.value.toLowerCase();
      renderTagEditorList();
    });
  }

  if (tagSortSelect) {
    tagSortSelect.addEventListener("change", (e) => {
      tagSortMode = e.target.value;
      renderTagEditorList();
    });
  }
}

function openTagEditorModal() {
  if (!tagEditorModal) return;
  // Reset state
  tagSearchQuery = "";
  tagSortMode = "name";
  if (tagSearchInput) tagSearchInput.value = "";
  if (tagSortSelect) tagSortSelect.value = "name";

  tagEditorModal.style.display = "flex";
  renderTagEditorList();
}

function closeTagEditorModal() {
  if (!tagEditorModal) return;
  tagEditorModal.style.display = "none";
}

function getTagStats() {
  const tagStats = {};

  allItems.forEach((item) => {
    const itemTags = item.analysis?.tags || [];
    const itemDate = item.created_at ? new Date(item.created_at) : new Date(0);

    itemTags.forEach((tag) => {
      if (!tagStats[tag]) {
        tagStats[tag] = {
          name: tag,
          count: 0,
          newestDate: itemDate,
        };
      }
      tagStats[tag].count++;
      if (itemDate > tagStats[tag].newestDate) {
        tagStats[tag].newestDate = itemDate;
      }
    });
  });

  return tagStats;
}

function renderTagEditorList() {
  if (!tagEditorList) return;

  const tagStats = getTagStats();
  let tags = Object.values(tagStats);

  // Filter by search query
  if (tagSearchQuery) {
    tags = tags.filter((tag) =>
      tag.name.toLowerCase().includes(tagSearchQuery),
    );
  }

  // Sort tags
  switch (tagSortMode) {
    case "newest":
      tags.sort((a, b) => b.newestDate - a.newestDate);
      break;
    case "count":
      tags.sort((a, b) => b.count - a.count);
      break;
    case "name":
    default:
      tags.sort((a, b) => a.name.localeCompare(b.name));
      break;
  }

  // Update count
  if (tagEditorCount) {
    tagEditorCount.textContent = `${tags.length} tag${tags.length === 1 ? "" : "s"}`;
  }

  // Render list
  tagEditorList.innerHTML = "";

  if (tags.length === 0) {
    const emptyEl = document.createElement("div");
    emptyEl.className = "tag-editor-empty";
    emptyEl.textContent = tagSearchQuery
      ? "No tags match your search."
      : "No tags found.";
    tagEditorList.appendChild(emptyEl);
    return;
  }

  tags.forEach((tag) => {
    const row = document.createElement("div");
    row.className = "tag-editor-item";

    const iconEl = document.createElement("div");
    iconEl.className = "tag-editor-icon";
    iconEl.textContent = "🏷️";
    row.appendChild(iconEl);

    const infoEl = document.createElement("div");
    infoEl.className = "tag-editor-info";

    const nameEl = document.createElement("div");
    nameEl.className = "tag-editor-name";
    nameEl.textContent = tag.name;
    infoEl.appendChild(nameEl);

    const countEl = document.createElement("div");
    countEl.className = "tag-editor-count-label";
    countEl.textContent = `${tag.count} item${tag.count === 1 ? "" : "s"}`;
    infoEl.appendChild(countEl);

    row.appendChild(infoEl);

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "tag-editor-delete";
    deleteBtn.textContent = "🗑️";
    deleteBtn.type = "button";
    deleteBtn.title = "Delete tag";
    deleteBtn.addEventListener("click", () => deleteTag(tag.name));
    row.appendChild(deleteBtn);

    tagEditorList.appendChild(row);
  });
}

async function deleteTag(tagName) {
  const tagStats = getTagStats();
  const tag = tagStats[tagName];
  if (!tag) return;

  const confirmMsg = `Delete tag "${tagName}"?\n\nThis will remove the tag from ${tag.count} item${tag.count === 1 ? "" : "s"}.`;
  if (!confirm(confirmMsg)) return;

  // Find all items with this tag and update them
  const itemsWithTag = allItems.filter((item) => {
    const itemTags = item.analysis?.tags || [];
    return itemTags.includes(tagName);
  });

  try {
    for (const item of itemsWithTag) {
      const itemId = getItemId(item);
      const currentTags = item.analysis?.tags || [];
      const newTags = currentTags.filter((t) => t !== tagName);

      const response = await fetch(`/api/items/${itemId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...getCsrfHeaders(),
        },
        body: JSON.stringify({ tags: newTags }),
      });

      if (!response.ok) {
        throw new Error(`Failed to update item ${itemId}`);
      }

      // Update local state
      if (item.analysis) {
        item.analysis.tags = newTags;
      }
    }

    // Re-render tag list and main items list
    renderTagEditorList();
    renderFilteredItems();
  } catch (error) {
    console.error("Delete tag error:", error);
    alert(error.message || "Failed to delete tag");
  }
}

// Escape HTML to prevent XSS
function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function closeMetricsModal() {
  if (!metricsModal) return;
  metricsModal.style.display = "none";
}

// Setup search input with debounce
function setupSearchInput() {
  if (!searchInputEl) return;

  searchInputEl.addEventListener("input", (e) => {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      searchQuery = e.target.value;
      renderFilteredItems();
    }, 300);
  });
}

// Setup filter modal
function setupFilterModal() {
  if (!filterModal) return;

  // Open modal
  if (filterBtnEl) {
    filterBtnEl.addEventListener("click", openFilterModal);
  }

  // Close modal
  if (filterModalCloseBtn) {
    filterModalCloseBtn.addEventListener("click", closeFilterModal);
  }
  if (filterModalBackdrop) {
    filterModalBackdrop.addEventListener("click", closeFilterModal);
  }

  // Apply button
  if (filterApplyBtn) {
    filterApplyBtn.addEventListener("click", applyFilters);
  }

  // Clear button
  if (filterClearBtn) {
    filterClearBtn.addEventListener("click", clearFilters);
  }
}

function openFilterModal() {
  if (!filterModal) return;

  // Copy current selections to pending
  pendingSelectedTypes = new Set(selectedTypes);
  pendingSelectedTags = new Set(selectedTags);

  // Populate chips
  populateFilterChips();

  filterModal.style.display = "flex";
}

function closeFilterModal() {
  if (!filterModal) return;
  filterModal.style.display = "none";
}

function populateFilterChips() {
  // Static list of types
  const types = [
    "image",
    "video",
    "audio",
    "file",
    "screenshot",
    "text",
    "web_url",
  ];

  // Populate type chips
  if (filterTypesEl) {
    filterTypesEl.innerHTML = "";
    types.forEach((type) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "filter-chip";
      if (pendingSelectedTypes.has(type)) {
        chip.classList.add("selected");
      }
      chip.textContent = formatType(type);
      chip.dataset.value = type;
      chip.addEventListener("click", () => toggleTypeChip(chip, type));
      filterTypesEl.appendChild(chip);
    });
  }

  // Populate tag chips from available tags
  if (filterTagsEl) {
    filterTagsEl.innerHTML = "";
    const availableTags = getAllAvailableTags();
    if (availableTags.size === 0) {
      const emptyMsg = document.createElement("span");
      emptyMsg.className = "filter-empty-msg";
      emptyMsg.textContent = "No tags available";
      filterTagsEl.appendChild(emptyMsg);
    } else {
      // Sort tags alphabetically
      const sortedTags = [...availableTags].sort();
      sortedTags.forEach((tag) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "filter-chip";
        if (pendingSelectedTags.has(tag)) {
          chip.classList.add("selected");
        }
        chip.textContent = tag;
        chip.dataset.value = tag;
        chip.addEventListener("click", () => toggleTagChip(chip, tag));
        filterTagsEl.appendChild(chip);
      });
    }
  }
}

function toggleTypeChip(chip, type) {
  if (pendingSelectedTypes.has(type)) {
    pendingSelectedTypes.delete(type);
    chip.classList.remove("selected");
  } else {
    pendingSelectedTypes.add(type);
    chip.classList.add("selected");
  }
}

function toggleTagChip(chip, tag) {
  if (pendingSelectedTags.has(tag)) {
    pendingSelectedTags.delete(tag);
    chip.classList.remove("selected");
  } else {
    pendingSelectedTags.add(tag);
    chip.classList.add("selected");
  }
}

function applyFilters() {
  // Copy pending selections to actual selections
  selectedTypes = new Set(pendingSelectedTypes);
  selectedTags = new Set(pendingSelectedTags);

  // Update filter count badge
  updateFilterCountBadge();

  // Re-render items
  renderFilteredItems();

  // Close modal
  closeFilterModal();
}

function clearFilters() {
  // Clear pending selections
  pendingSelectedTypes.clear();
  pendingSelectedTags.clear();

  // Re-populate chips to update visual state
  populateFilterChips();
}

function updateFilterCountBadge() {
  if (!filterCountEl) return;

  const count = selectedTypes.size + selectedTags.size;
  if (count > 0) {
    filterCountEl.textContent = count;
    filterCountEl.style.display = "inline-flex";
  } else {
    filterCountEl.style.display = "none";
  }
}

async function fetchMetrics() {
  if (!metricsLoading || !metricsError || !metricsContent) return;

  metricsLoading.style.display = "block";
  metricsError.style.display = "none";
  metricsContent.style.display = "none";

  try {
    const response = await fetch("/api/metrics");
    if (!response.ok) {
      throw new Error("Failed to fetch metrics");
    }
    const data = await response.json();
    displayMetrics(data);
  } catch (error) {
    metricsLoading.style.display = "none";
    metricsError.style.display = "block";
    metricsError.textContent = error.message || "Failed to load metrics";
  }
}

function displayMetrics(data) {
  metricsLoading.style.display = "none";
  metricsContent.style.display = "block";

  // Display total
  metricsTotalCount.textContent = data.total_items || 0;

  // Status labels and icons
  const statusConfig = {
    new: { label: "New", icon: "🆕" },
    analyzing: { label: "Analyzing", icon: "⏳" },
    analyzed: { label: "Analyzed", icon: "✅" },
    timeline: { label: "Timeline", icon: "📅" },
    follow_up: { label: "Follow-up", icon: "🚩" },
    processed: { label: "Processed", icon: "✔️" },
    soft_deleted: { label: "Archived", icon: "📦" },
  };

  const statusOrder = [
    "new",
    "analyzing",
    "analyzed",
    "timeline",
    "follow_up",
    "processed",
    "soft_deleted",
  ];
  const byStatus = data.by_status || {};

  // Clear existing items
  metricsStatusList.innerHTML = "";

  // Render status items
  statusOrder.forEach((status) => {
    const count = byStatus[status] || 0;
    // Always show new and follow_up, hide others if 0
    if (count === 0 && status !== "new" && status !== "follow_up") {
      return;
    }

    const config = statusConfig[status] || { label: status, icon: "●" };
    const item = document.createElement("div");
    item.className = "metrics-status-item";
    item.dataset.status = status;
    item.innerHTML = `
            <div class="metrics-status-item-left">
                <div class="metrics-status-icon">${config.icon}</div>
                <span class="metrics-status-label">${config.label}</span>
            </div>
            <span class="metrics-status-count">${count}</span>
        `;
    metricsStatusList.appendChild(item);
  });

  // Add any unknown statuses
  Object.entries(byStatus).forEach(([status, count]) => {
    if (!statusOrder.includes(status) && count > 0) {
      const item = document.createElement("div");
      item.className = "metrics-status-item";
      item.dataset.status = status;

      const left = document.createElement("div");
      left.className = "metrics-status-item-left";

      const icon = document.createElement("div");
      icon.className = "metrics-status-icon";
      icon.textContent = "●";
      left.appendChild(icon);

      const label = document.createElement("span");
      label.className = "metrics-status-label";
      label.textContent = status;
      left.appendChild(label);

      item.appendChild(left);

      const countEl = document.createElement("span");
      countEl.className = "metrics-status-count";
      countEl.textContent = count;
      item.appendChild(countEl);

      metricsStatusList.appendChild(item);
    }
  });

  // Display worker queue metrics
  displayWorkerQueueMetrics(data.worker_queue);
}

function displayWorkerQueueMetrics(workerQueue) {
  if (!metricsWorkerSection || !metricsWorkerTotal || !metricsWorkerList)
    return;

  // Always show worker queue section
  metricsWorkerSection.style.display = "block";
  const total = workerQueue?.total || 0;
  metricsWorkerTotal.textContent = `${total} jobs`;

  const workerStatusConfig = {
    queued: { label: "Queued", icon: "⏱️" },
    leased: { label: "Processing", icon: "🔄" },
    completed: { label: "Completed", icon: "✅" },
    failed: { label: "Failed", icon: "❌" },
  };

  const workerStatusOrder = ["queued", "leased", "completed", "failed"];
  const byStatus = workerQueue?.by_status || {};

  // Clear existing items
  metricsWorkerList.innerHTML = "";

  // Render worker status items
  workerStatusOrder.forEach((status) => {
    const count = byStatus[status] || 0;
    // Always show queued and leased, hide completed/failed if 0
    if (count === 0 && status !== "queued" && status !== "leased") {
      return;
    }

    const config = workerStatusConfig[status] || { label: status, icon: "●" };
    const item = document.createElement("div");
    item.className = "metrics-status-item";
    item.dataset.status = status;
    item.innerHTML = `
            <div class="metrics-status-item-left">
                <div class="metrics-status-icon">${config.icon}</div>
                <span class="metrics-status-label">${config.label}</span>
            </div>
            <span class="metrics-status-count">${count}</span>
        `;
    metricsWorkerList.appendChild(item);
  });

  // Add any unknown worker statuses
  Object.entries(byStatus).forEach(([status, count]) => {
    if (!workerStatusOrder.includes(status) && count > 0) {
      const item = document.createElement("div");
      item.className = "metrics-status-item";
      item.dataset.status = status;

      const left = document.createElement("div");
      left.className = "metrics-status-item-left";

      const icon = document.createElement("div");
      icon.className = "metrics-status-icon";
      icon.textContent = "●";
      left.appendChild(icon);

      const label = document.createElement("span");
      label.className = "metrics-status-label";
      label.textContent = status;
      left.appendChild(label);

      item.appendChild(left);

      const countEl = document.createElement("span");
      countEl.className = "metrics-status-count";
      countEl.textContent = count;
      item.appendChild(countEl);

      metricsWorkerList.appendChild(item);
    }
  });
}

function openUserMenu() {
  if (!userMenuEl) return;
  userMenuEl.classList.add("is-open");
  userMenuEl.setAttribute("aria-hidden", "false");
}

function closeUserMenu() {
  if (!userMenuEl) return;
  userMenuEl.classList.remove("is-open");
  userMenuEl.setAttribute("aria-hidden", "true");
}

function toggleUserMenu() {
  if (!userMenuEl) return;
  if (userMenuEl.classList.contains("is-open")) {
    closeUserMenu();
  } else {
    openUserMenu();
  }
}

// Get all available tags from items
function getAllAvailableTags() {
  const tags = new Set();
  allItems.forEach((item) => {
    const itemTags = item.analysis?.tags;
    if (Array.isArray(itemTags)) {
      itemTags.forEach((tag) => tags.add(tag));
    }
  });
  return tags;
}

const MEDIA_TAGS = new Set(["to_read", "to_listen", "to_watch"]);

function getConsumptionTime(item) {
  const time = item.analysis?.consumption_time_minutes;
  if (typeof time === "number") return Math.round(time);
  return null;
}

function isFutureAvailability(item) {
  const eventDate = getEventDateTime(item);
  if (!eventDate) return false;
  return eventDate > new Date();
}

function formatConsumptionTime(minutes) {
  if (minutes < 60) return `~${minutes} min`;
  const hours = minutes / 60;
  if (hours < 10) return `~${hours.toFixed(1)} hr`;
  return `~${Math.round(hours)} hr`;
}

function formatAvailabilityDate(date) {
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function groupItemsByMediaTag(items) {
  const groups = {
    to_watch: [],
    to_listen: [],
    to_read: [],
  };

  for (const item of items) {
    const tags = item.analysis?.tags || [];
    for (const tag of MEDIA_TAGS) {
      if (tags.includes(tag)) {
        groups[tag].push(item);
      }
    }
  }

  // Sort each group by consumption time (nulls last), then by created_at
  for (const group of Object.values(groups)) {
    group.sort((a, b) => {
      const timeA = getConsumptionTime(a);
      const timeB = getConsumptionTime(b);
      if (timeA === null && timeB === null)
        return new Date(b.created_at || 0) - new Date(a.created_at || 0);
      if (timeA === null) return 1;
      if (timeB === null) return -1;
      return timeA - timeB;
    });
  }

  return groups;
}

// Get event date from analysis details
function getEventDateTime(item) {
  // Check for timeline events (root-level array or legacy analysis.timeline)
  const timelines = getTimelinesFromItem(item);
  for (const timeline of timelines) {
    if (timeline.date) {
      try {
        let dateStr = timeline.date;
        let isAllDay = false;

        // Check if time is present and not the string "null"
        if (timeline.time && timeline.time !== "null") {
          dateStr += ` ${timeline.time}`;
        } else {
          // No time: use UTC Noon to ensure date stability across timezones
          // Append T12:00:00Z so it is parsed as UTC Noon
          dateStr += "T12:00:00Z";
          isAllDay = true;
        }

        const date = new Date(dateStr);
        if (!isNaN(date.getTime())) {
          if (isAllDay) date.isAllDay = true;
          return date;
        }
      } catch (e) {
        // fall through
      }
    }
  }

  if (!item.analysis) return null;

  if (!item.analysis.details) return null;

  const details = item.analysis.details;
  // Look for date_time in various possible field names
  const dateTimeStr =
    details.date_time ||
    details.dateTime ||
    details.date ||
    details.event_date ||
    details.eventDate ||
    details.start_date;

  if (!dateTimeStr) return null;

  try {
    // Try to parse the date string
    const date = new Date(dateTimeStr);
    if (isNaN(date.getTime())) {
      // Try to extract a date from common formats like "January 29" or "Jan 29"
      const currentYear = new Date().getFullYear();
      const withYear = new Date(`${dateTimeStr} ${currentYear}`);
      if (!isNaN(withYear.getTime())) {
        return withYear;
      }
      return null;
    }
    return date;
  } catch {
    return null;
  }
}

// Filter and sort items based on current view and type filter
function getFilteredItems() {
  let items = getBaseFilteredItems();

  // Apply view-specific filtering and sorting
  if (currentView === "timeline") {
    // Filter to only items with derived date/time
    items = items.filter((item) => getEventDateTime(item) !== null);

    // Sort by event date/time (descending - newest first)
    items.sort((a, b) => {
      const dateA = getEventDateTime(a);
      const dateB = getEventDateTime(b);
      return dateB - dateA;
    });
  } else if (currentView === "follow_up") {
    // Filter to only items with follow_up status
    items = items.filter((item) => item.status === "follow_up");

    // Sort by created_at descending (newest first)
    items.sort((a, b) => {
      const dateA = new Date(a.created_at || 0);
      const dateB = new Date(b.created_at || 0);
      return dateB - dateA;
    });
  } else if (currentView === "media") {
    items = items.filter((item) => {
      const tags = item.analysis?.tags || [];
      return tags.some((t) => MEDIA_TAGS.has(t));
    });
    // Sorting happens in groupItemsByMediaTag
  } else {
    // Default: sort by created_at descending (newest first)
    items.sort((a, b) => {
      const dateA = new Date(a.created_at || 0);
      const dateB = new Date(b.created_at || 0);
      return dateB - dateA;
    });
  }

  return items;
}

function getBaseFilteredItems() {
  let items = [...allItems];

  if (!showHidden) {
    items = items.filter((item) => !item.hidden);
  }

  if (searchQuery) {
    const query = searchQuery.toLowerCase();
    items = items.filter(
      (item) =>
        item.title?.toLowerCase().includes(query) ||
        item.content?.toLowerCase().includes(query),
    );
  }

  if (selectedTypes.size > 0) {
    items = items.filter((item) => selectedTypes.has(normalizeType(item)));
  }

  if (selectedTags.size > 0) {
    items = items.filter((item) => {
      const itemTags = item.analysis?.tags || [];
      return [...selectedTags].some((tag) => itemTags.includes(tag));
    });
  }

  return items;
}

function updateFollowUpBadge() {
  if (!followUpCountBadgeEl) return;
  const count = getBaseFilteredItems().filter(
    (item) => item.status === "follow_up",
  ).length;
  if (count > 0) {
    followUpCountBadgeEl.textContent = String(count);
    followUpCountBadgeEl.style.display = "inline-flex";
  } else {
    followUpCountBadgeEl.style.display = "none";
  }
}

// Render items with current filters applied
function renderFilteredItems() {
  updateFollowUpBadge();
  const items = getFilteredItems();
  renderItems(items);
}

// Show login state (not logged in)
function showLoginState() {
  loadingEl.style.display = "none";
  userInfoEl.style.display = "none";
  loginStateEl.style.display = "block";
}

// Fetch current user
async function fetchUser() {
  const response = await fetch("/api/user");
  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new Error("Failed to fetch user");
  }
  return response.json();
}

// Fetch all items
async function fetchItems() {
  const response = await fetch("/api/items");
  if (response.status === 401) {
    showLoginState();
    throw new Error("Not authenticated");
  }
  if (!response.ok) {
    throw new Error("Failed to fetch items");
  }
  return response.json();
}

async function fetchNoteCounts(items) {
  if (!items || items.length === 0) {
    noteCounts = {};
    return;
  }
  const itemIds = items.map((item) => getItemId(item)).filter(Boolean);
  if (!itemIds.length) {
    noteCounts = {};
    return;
  }

  try {
    const response = await fetch("/api/items/note-counts", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getCsrfHeaders(),
      },
      body: JSON.stringify({ item_ids: itemIds }),
    });
    if (!response.ok) {
      throw new Error("Failed to fetch note counts");
    }
    noteCounts = await response.json();
  } catch (error) {
    console.warn("Note counts unavailable:", error);
    noteCounts = {};
  }
}

// Render all items
function renderItems(items) {
  loadingEl.style.display = "none";
  filtersEl.style.display = "flex";

  if (!items || items.length === 0) {
    emptyStateEl.style.display = "block";
    if (!showHidden && allItems.some((item) => item.hidden)) {
      emptyStateEl.querySelector("p").textContent =
        'No visible items. Use "Show Archive" to view archived items.';
    } else if (currentView === "timeline") {
      emptyStateEl.querySelector("p").textContent =
        "No items with event dates found.";
    } else if (currentView === "follow_up") {
      emptyStateEl.querySelector("p").textContent = "No items need follow-up.";
    } else if (currentView === "media") {
      emptyStateEl.querySelector("p").textContent = "No media items found.";
    } else if (selectedTypes.size > 0) {
      const typeNames = [...selectedTypes].map(formatType).join(", ");
      emptyStateEl.querySelector("p").textContent =
        `No ${typeNames} items found.`;
    } else {
      emptyStateEl.querySelector("p").textContent =
        "No items yet. Share something from the mobile app or browser extension!";
    }
    itemsContainerEl.innerHTML = "";
    return;
  }

  emptyStateEl.style.display = "none";
  itemsContainerEl.innerHTML = "";

  if (currentView === "timeline") {
    renderTimelineItems(items);
  } else if (currentView === "media") {
    renderMediaItems(items);
  } else {
    items.forEach((item) => {
      const card = renderItem(item);
      itemsContainerEl.appendChild(card);
    });
  }
}

// Render items in timeline view with Now divider
function renderTimelineItems(items) {
  const now = new Date();
  let nowDividerInserted = false;
  let nowDividerEl = null;

  items.forEach((item) => {
    const eventDate = getEventDateTime(item);

    // Insert "Now" divider before the first past item
    if (!nowDividerInserted && eventDate < now) {
      nowDividerEl = document.createElement("div");
      nowDividerEl.className = "now-divider";
      nowDividerEl.id = "now-divider";
      nowDividerEl.innerHTML = "<span>Now</span>";
      itemsContainerEl.appendChild(nowDividerEl);
      nowDividerInserted = true;
    }

    const card = renderItem(item);
    if (eventDate < now) {
      card.classList.add("timeline-past");
    }

    // Add event date badge for timeline view
    const eventDateBadge = document.createElement("div");
    eventDateBadge.className = "event-date-badge";
    eventDateBadge.textContent = formatEventDate(eventDate);
    card.insertBefore(eventDateBadge, card.firstChild);

    itemsContainerEl.appendChild(card);
  });

  // If all items are in the future, add Now divider at the end
  if (!nowDividerInserted && items.length > 0) {
    nowDividerEl = document.createElement("div");
    nowDividerEl.className = "now-divider";
    nowDividerEl.id = "now-divider";
    nowDividerEl.innerHTML = "<span>Now</span>";
    itemsContainerEl.appendChild(nowDividerEl);
  }

  // Auto-scroll to Now divider
  if (nowDividerEl) {
    setTimeout(() => {
      nowDividerEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 100);
  }
}

function renderMediaItems(items) {
  const groups = groupItemsByMediaTag(items);
  const groupLabels = {
    to_watch: "To Watch",
    to_listen: "To Listen",
    to_read: "To Read",
  };

  let hasAnyItems = false;

  for (const tag of ["to_watch", "to_listen", "to_read"]) {
    const groupItems = groups[tag];
    if (groupItems.length === 0) continue;

    hasAnyItems = true;

    // Section header
    const header = document.createElement("div");
    header.className = "media-section-header";
    header.textContent = groupLabels[tag];
    itemsContainerEl.appendChild(header);

    // Items
    for (const item of groupItems) {
      const card = renderItem(item);

      // Add badges before the card content
      const badgesRow = document.createElement("div");
      badgesRow.className = "media-badges";

      const consumptionTime = getConsumptionTime(item);
      if (consumptionTime !== null) {
        const badge = document.createElement("span");
        badge.className = "consumption-time-badge";
        badge.textContent = formatConsumptionTime(consumptionTime);
        badgesRow.appendChild(badge);
      }

      if (isFutureAvailability(item)) {
        const badge = document.createElement("span");
        badge.className = "availability-badge";
        badge.textContent = `Available ${formatAvailabilityDate(getEventDateTime(item))}`;
        badgesRow.appendChild(badge);
      }

      if (badgesRow.children.length > 0) {
        // Insert badges after the header element
        const headerEl = card.querySelector(".item-header");
        if (headerEl && headerEl.nextSibling) {
          card.insertBefore(badgesRow, headerEl.nextSibling);
        } else {
          card.appendChild(badgesRow);
        }
      }

      itemsContainerEl.appendChild(card);
    }
  }

  if (!hasAnyItems) {
    emptyStateEl.style.display = "block";
    emptyStateEl.querySelector("p").textContent = "No media items found.";
  }
}

// Format event date for timeline display
function formatEventDate(date) {
  if (!date) return "";
  const options = {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: currentUserTimezone,
  };

  // Only add time if NOT all day
  if (!date.isAllDay) {
    options.hour = "2-digit";
    options.minute = "2-digit";
  }

  return date.toLocaleDateString(undefined, options);
}

// Render a single item, dispatching to type-specific renderer
function renderItem(item) {
  const card = document.createElement("div");
  card.className = "item-card";
  card.dataset.id = item.firestore_id || item.id;
  if (item.hidden) {
    card.classList.add("is-hidden");
  }
  const normalizedType = normalizeType(item);

  const header = document.createElement("div");
  header.className = "item-header";

  const titleSection = document.createElement("div");

  if (item.title) {
    const title = document.createElement("div");
    title.className = "item-title";
    // Show bullet indicator for unnormalized titles
    if (!item.is_normalized) {
      const indicator = document.createElement("span");
      indicator.className = "normalization-indicator";
      indicator.textContent = "• ";
      indicator.title = "Title pending normalization";
      title.appendChild(indicator);
    }
    title.appendChild(document.createTextNode(item.title));
    titleSection.appendChild(title);
  }

  const meta = document.createElement("div");
  meta.className = "item-meta";

  const badge = document.createElement("span");
  badge.className = `type-badge ${normalizedType}`;
  badge.textContent = formatType(normalizedType);
  meta.appendChild(badge);

  // Analysis Sparkle
  const sparkle = document.createElement("span");
  sparkle.textContent = "✨";
  sparkle.style.marginLeft = "10px";
  sparkle.style.fontSize = "1.2em";

  if (item.analysis) {
    sparkle.style.cursor = "pointer";
    sparkle.title = "View Analysis";
    sparkle.onclick = (e) => {
      e.stopPropagation(); // Prevent card clicks if any
      alert(item.analysis.overview);
    };
  } else {
    sparkle.style.filter = "grayscale(100%)";
    sparkle.style.opacity = "0.5";
    sparkle.style.cursor = "default";
    sparkle.title = "No Analysis";
  }
  meta.appendChild(sparkle);

  const count = getNoteCount(item);
  if (count > 0) {
    const noteBadge = document.createElement("span");
    noteBadge.className = "note-count-badge";
    noteBadge.textContent = `${count}`;
    noteBadge.title = `${count} note${count === 1 ? "" : "s"}`;
    noteBadge.dataset.noteCount = count;
    meta.appendChild(noteBadge);
  }

  titleSection.appendChild(meta);
  header.appendChild(titleSection);

  card.appendChild(header);

  // Type-specific content
  const content = document.createElement("div");
  content.className = "item-content";

  switch (normalizedType) {
    case "media":
    case "image":
    case "screenshot":
      renderMediaItem(item, content);
      break;
    case "video":
      renderVideoItem(item, content);
      break;
    case "audio":
      renderAudioItem(item, content);
      break;
    case "web_url":
      renderWebUrlItem(item, content);
      break;
    case "file":
      renderFileItem(item, content);
      break;
    case "text":
    default:
      renderTextItem(item, content);
      break;
  }

  card.appendChild(content);

  // Details section (hidden by default)
  const details = document.createElement("div");
  details.className = "item-details";
  details.style.display = "none";

  const idRow = document.createElement("div");
  idRow.className = "item-details-row";

  const idLabel = document.createElement("span");
  idLabel.className = "item-details-label";
  idLabel.textContent = "ID: ";
  idRow.appendChild(idLabel);

  const idValue = document.createElement("span");
  idValue.className = "item-details-value";
  idValue.textContent = item.firestore_id || "N/A";
  idRow.appendChild(idValue);

  details.appendChild(idRow);

  if (item.analysis?.tags && item.analysis.tags.length > 0) {
    const tagsRow = document.createElement("div");
    tagsRow.className = "item-details-row";

    const label = document.createElement("span");
    label.className = "item-details-label";
    label.textContent = "Tags: ";
    tagsRow.appendChild(label);

    const tagsContainer = document.createElement("span");
    tagsContainer.className = "item-details-tags";

    item.analysis.tags.forEach((tag) => {
      const tagSpan = document.createElement("span");
      tagSpan.className = "item-tag";
      tagSpan.textContent = tag;
      tagsContainer.appendChild(tagSpan);
    });

    tagsRow.appendChild(tagsContainer);
    details.appendChild(tagsRow);
  }

  card.appendChild(details);

  // Footer with date and actions
  const footer = document.createElement("div");
  footer.className = "item-footer";

  if (currentView !== "timeline") {
    const date = document.createElement("span");
    date.className = "item-date";
    date.textContent = formatDate(item.created_at);
    footer.appendChild(date);
  } else {
    footer.classList.add("item-footer--compact");
  }

  const footerActions = document.createElement("div");
  footerActions.className = "item-footer-actions";

  const infoBtn = document.createElement("button");
  infoBtn.className = "info-btn";
  infoBtn.textContent = "ℹ️";
  infoBtn.title = "View details";
  infoBtn.onclick = () => {
    openDetailModal(item);
  };
  footerActions.appendChild(infoBtn);

  const hideBtn = document.createElement("button");
  hideBtn.className = "hide-btn";
  hideBtn.textContent = item.hidden ? "Unhide" : "Hide";
  hideBtn.onclick = () => setItemHidden(card.dataset.id, !item.hidden);
  footerActions.appendChild(hideBtn);

  const deleteBtn = document.createElement("button");
  deleteBtn.className = "delete-btn";
  deleteBtn.textContent = "Delete";
  deleteBtn.onclick = () => deleteItem(card.dataset.id);
  footerActions.appendChild(deleteBtn);

  footer.appendChild(footerActions);

  card.appendChild(footer);

  return card;
}

function getItemId(item) {
  return item.firestore_id || item.id;
}

function getNoteCount(item) {
  const itemId = getItemId(item);
  if (!itemId) return 0;
  const count = noteCounts[itemId];
  return typeof count === "number" ? count : 0;
}

function updateNoteCountBadge(itemId, count) {
  const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
  if (!card) return;
  const meta = card.querySelector(".item-meta");
  if (!meta) return;
  const existing = meta.querySelector(".note-count-badge");

  if (count > 0) {
    if (existing) {
      existing.textContent = `${count}`;
      existing.title = `${count} note${count === 1 ? "" : "s"}`;
      existing.dataset.noteCount = count;
    } else {
      const badge = document.createElement("span");
      badge.className = "note-count-badge";
      badge.textContent = `${count}`;
      badge.title = `${count} note${count === 1 ? "" : "s"}`;
      badge.dataset.noteCount = count;
      meta.appendChild(badge);
    }
  } else if (existing) {
    existing.remove();
  }
}

function openDetailModal(item) {
  if (!detailModal) return;
  currentDetailItem = item;
  detailModal.style.display = "flex";
  detailTitleEl.textContent = item.title || "Untitled";
  detailTitleInput.value = item.title || "";
  detailTypeEl.textContent = formatType(normalizeType(item));

  if (typeof item.content === "string" && item.content.startsWith("http")) {
    detailContentEl.innerHTML = "";
    const link = document.createElement("a");
    link.href = item.content;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = item.content;
    detailContentEl.appendChild(link);
  } else {
    detailContentEl.textContent = item.content || "";
  }

  // Display item ID with copy button
  const itemId = item.firestore_id || item.id || "";
  if (detailItemIdEl) {
    detailItemIdEl.innerHTML = "";
    const code = document.createElement("code");
    code.textContent = itemId;
    detailItemIdEl.appendChild(code);

    const btn = document.createElement("button");
    btn.className = "btn-icon";
    btn.title = "Copy ID";
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>`;
    btn.onclick = () =>
      navigator.clipboard
        .writeText(itemId)
        .then(() => alert("Item ID copied!"));
    detailItemIdEl.appendChild(btn);
  }

  editableTags = item.analysis?.tags ? [...item.analysis.tags] : [];
  renderDetailTags();

  // Populate timeline section
  populateTimelineSection(item);

  // Display follow-up content if available
  const followUp = item.analysis?.follow_up;
  if (detailFollowUpEl && detailFollowUpContentEl) {
    if (followUp && followUp.trim()) {
      detailFollowUpContentEl.textContent = followUp;
      detailFollowUpEl.style.display = "block";
    } else {
      detailFollowUpEl.style.display = "none";
    }
  }

  setDetailEditMode(false);
  loadDetailNotes();
}

function closeDetailModal() {
  if (!detailModal) return;
  detailModal.style.display = "none";
  currentDetailItem = null;
  isTimelineExpanded = false;
}

function toggleTimeline() {
  isTimelineExpanded = !isTimelineExpanded;
  if (detailTimelineContent) {
    detailTimelineContent.style.display = isTimelineExpanded ? "block" : "none";
  }
  if (detailTimelineEl) {
    if (isTimelineExpanded) {
      detailTimelineEl.classList.add("expanded");
    } else {
      detailTimelineEl.classList.remove("expanded");
    }
  }
}

function getTimelinesFromItem(item) {
    if (!item.timeline) {
        // Fallback to legacy single timeline field format just in case it wasn't migrated
        if (item.analysis?.timeline) {
            return [item.analysis.timeline];
        }
        return [];
    }
    return item.timeline;
}

function countTimelineFields(timelines) {
    let count = 0;
    for (const t of timelines) {
        if (t.date) count++;
        if (t.time) count++;
        if (t.duration) count++;
        if (t.principal) count++;
        if (t.location) count++;
        if (t.purpose) count++;
    }
    return count;
}

function createTimelineEventEl(timeline, index) {
    const el = document.createElement('div');
    el.className = 'detail-timeline-event';
    if (index > 0) {
        el.style.borderTop = '1px solid var(--border-light)';
        el.style.paddingTop = '16px';
        el.style.marginTop = '16px';
    }

    el.innerHTML = `
        <div class="detail-timeline-event-header" style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <strong>Event ${index + 1}</strong>
            <button type="button" class="btn-icon btn-danger detail-timeline-remove-btn" title="Remove event" style="display: none;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
            </button>
        </div>
        <div class="detail-timeline-fields">
            <div class="detail-timeline-field">
                <label class="detail-label">Date</label>
                <div class="detail-text timeline-view date-view">${escapeHtml(timeline.date || '')}</div>
                <input class="detail-input timeline-input date-input" type="text" placeholder="YYYY-MM-DD" value="${escapeHtml(timeline.date || '')}" style="display: none;" />
            </div>
            <div class="detail-timeline-field">
                <label class="detail-label">Time</label>
                <div class="detail-text timeline-view time-view">${escapeHtml(timeline.time || '')}</div>
                <input class="detail-input timeline-input time-input" type="text" placeholder="HH:MM:SS" value="${escapeHtml(timeline.time || '')}" style="display: none;" />
            </div>
            <div class="detail-timeline-field">
                <label class="detail-label">Duration</label>
                <div class="detail-text timeline-view duration-view">${escapeHtml(timeline.duration || '')}</div>
                <input class="detail-input timeline-input duration-input" type="text" placeholder="HH:MM:SS" value="${escapeHtml(timeline.duration || '')}" style="display: none;" />
            </div>
            <div class="detail-timeline-field">
                <label class="detail-label">Principal</label>
                <div class="detail-text timeline-view principal-view">${escapeHtml(timeline.principal || '')}</div>
                <input class="detail-input timeline-input principal-input" type="text" placeholder="Person or organization" value="${escapeHtml(timeline.principal || '')}" style="display: none;" />
            </div>
            <div class="detail-timeline-field">
                <label class="detail-label">Location</label>
                <div class="detail-text timeline-view location-view">${escapeHtml(timeline.location || '')}</div>
                <input class="detail-input timeline-input location-input" type="text" placeholder="Where it takes place" value="${escapeHtml(timeline.location || '')}" style="display: none;" />
            </div>
            <div class="detail-timeline-field">
                <label class="detail-label">Purpose</label>
                <div class="detail-text timeline-view purpose-view">${escapeHtml(timeline.purpose || '')}</div>
                <input class="detail-input timeline-input purpose-input" type="text" placeholder="What the event is about" value="${escapeHtml(timeline.purpose || '')}" style="display: none;" />
            </div>
        </div>
    `;

    // Bind remove button
    const removeBtn = el.querySelector('.detail-timeline-remove-btn');
    removeBtn.addEventListener('click', () => {
        el.remove();
        // Re-number remaining events
        const events = detailTimelineList.querySelectorAll('.detail-timeline-event');
        events.forEach((ev, idx) => {
            ev.querySelector('strong').textContent = `Event ${idx + 1}`;
            if (idx === 0) {
                ev.style.borderTop = 'none';
                ev.style.paddingTop = '0';
                ev.style.marginTop = '0';
            }
        });
    });

    return el;
}

function populateTimelineSection(item) {
    const timelines = getTimelinesFromItem(item);
    const count = countTimelineFields(timelines);

    // Show/hide timeline section
    if (detailTimelineEl) {
        if (timelines.length > 0 || detailEditMode) {
            detailTimelineEl.style.display = 'block';
        } else {
            detailTimelineEl.style.display = 'none';
        }
    }

    // Update count badge
    if (detailTimelineCount) {
        if (count > 0) {
            detailTimelineCount.textContent = count;
            detailTimelineCount.style.display = 'inline';
        } else {
            detailTimelineCount.style.display = 'none';
        }
    }

    // Populate list
    if (detailTimelineList) {
        detailTimelineList.innerHTML = '';
        timelines.forEach((timeline, index) => {
            detailTimelineList.appendChild(createTimelineEventEl(timeline, index));
        });
    }

    // Reset expansion state
    isTimelineExpanded = false;
    if (detailTimelineContent) detailTimelineContent.style.display = 'none';
    if (detailTimelineEl) detailTimelineEl.classList.remove('expanded');
    
    // Bind Add button functionality if not already bound (do this in a safer way, but this is fine for now since it's idempotent visually)
    if (detailTimelineAddBtn && !detailTimelineAddBtn.dataset.bound) {
        detailTimelineAddBtn.dataset.bound = "true";
        detailTimelineAddBtn.addEventListener('click', () => {
            if (!detailTimelineList) return;
            const currentCount = detailTimelineList.children.length;
            detailTimelineList.appendChild(createTimelineEventEl({}, currentCount));
            updateTimelineEditMode(true); // force new inputs to be visible
        });
    }
}

function updateTimelineEditMode(enabled) {
    if (!detailTimelineList) return;

    const views = detailTimelineList.querySelectorAll('.timeline-view');
    const inputs = detailTimelineList.querySelectorAll('.timeline-input');
    const removeBtns = detailTimelineList.querySelectorAll('.detail-timeline-remove-btn');
    
    views.forEach(el => el.style.display = enabled ? 'none' : 'block');
    inputs.forEach(el => el.style.display = enabled ? 'block' : 'none');
    removeBtns.forEach(el => el.style.display = enabled ? 'block' : 'none');

    if (detailTimelineAddContainer) {
        detailTimelineAddContainer.style.display = enabled ? 'block' : 'none';
    }

    // If entering edit mode and list is empty, add one empty event
    if (enabled && detailTimelineList.children.length === 0) {
        detailTimelineList.appendChild(createTimelineEventEl({}, 0));
        updateTimelineEditMode(true); // recursive call to set display states for the new element
    }

    if (detailTimelineEl && enabled) {
        detailTimelineEl.style.display = 'block';
    }
}

function getTimelineInputValues() {
    if (!detailTimelineList) return [];

    const timelines = [];
    const events = detailTimelineList.querySelectorAll('.detail-timeline-event');
    
    events.forEach(el => {
        const date = el.querySelector('.date-input')?.value?.trim() || null;
        const time = el.querySelector('.time-input')?.value?.trim() || null;
        const duration = el.querySelector('.duration-input')?.value?.trim() || null;
        const principal = el.querySelector('.principal-input')?.value?.trim() || null;
        const location = el.querySelector('.location-input')?.value?.trim() || null;
        const purpose = el.querySelector('.purpose-input')?.value?.trim() || null;

        // Only add if at least one field has a value
        if (date || time || duration || principal || location || purpose) {
            timelines.push({ date, time, duration, principal, location, purpose });
        }
    });

    return timelines;
}

function confirmDeleteFollowUp() {
  if (!currentDetailItem) return;

  if (
    confirm(
      "This will remove the follow-up and mark the item as processed. Continue?",
    )
  ) {
    deleteFollowUp();
  }
}

async function deleteFollowUp() {
  if (!currentDetailItem) return;

  const itemId = getItemId(currentDetailItem);

  try {
    const response = await fetch(`/api/items/${itemId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...getCsrfHeaders(),
      },
      body: JSON.stringify({
        status: "processed",
        next_step: "none",
        follow_up: "", // Empty string clears the follow_up
      }),
    });

    if (!response.ok) {
      throw new Error("Failed to delete follow-up");
    }

    // Update local item data
    currentDetailItem.status = "processed";
    currentDetailItem.next_step = "none";
    if (currentDetailItem.analysis) {
      delete currentDetailItem.analysis.follow_up;
    }

    // Update the item in allItems array
    const idx = allItems.findIndex((i) => getItemId(i) === itemId);
    if (idx !== -1) {
      allItems[idx] = { ...currentDetailItem };
    }

    // Hide follow-up section
    if (detailFollowUpEl) {
      detailFollowUpEl.style.display = "none";
    }

    // Refresh the list
    renderFilteredItems();
  } catch (error) {
    alert("Failed to delete follow-up: " + error.message);
  }
}

function setDetailEditMode(enabled) {
  detailEditMode = enabled;
  detailEditActions.style.display = enabled ? "flex" : "none";
  detailTagsEditor.style.display = enabled ? "flex" : "none";
  detailTitleInput.style.display = enabled ? "block" : "none";
  detailTitleEl.style.display = enabled ? "none" : "block";
  detailEditBtn.style.display = enabled ? "none" : "inline-flex";
  if (!enabled && currentDetailItem) {
    detailTitleInput.value = currentDetailItem.title || "";
    editableTags = currentDetailItem.analysis?.tags
      ? [...currentDetailItem.analysis.tags]
      : [];
    populateTimelineSection(currentDetailItem);
  }
  updateTimelineEditMode(enabled);
  renderDetailTags();
}

function renderDetailTags() {
  detailTagsEl.innerHTML = "";
  if (!editableTags.length) {
    const emptyTag = document.createElement("span");
    emptyTag.className = "detail-muted";
    emptyTag.textContent = "No tags";
    detailTagsEl.appendChild(emptyTag);
    return;
  }

  editableTags.forEach((tag) => {
    const tagEl = document.createElement("span");
    tagEl.className = "detail-tag";
    tagEl.textContent = tag;
    if (detailEditMode) {
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.textContent = "×";
      removeBtn.onclick = () => {
        editableTags = editableTags.filter((t) => t !== tag);
        renderDetailTags();
      };
      tagEl.appendChild(removeBtn);
    }
    detailTagsEl.appendChild(tagEl);
  });
}

async function saveDetailEdits() {
  if (!currentDetailItem) return;
  const itemId = getItemId(currentDetailItem);
  const newTitle = detailTitleInput.value.trim();
  const tags = editableTags;
  const timeline = getTimelineInputValues();

  const body = {
    title: newTitle,
    tags: tags,
  };

  // Only include timeline if at least one event was provided, otherwise default to empty list (meaning cleared)
  body.timeline = timeline;

  try {
    const response = await fetch(`/api/items/${itemId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...getCsrfHeaders(),
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error("Failed to update item");
    }
    currentDetailItem.title = newTitle;
    currentDetailItem.analysis = currentDetailItem.analysis || {};
    currentDetailItem.analysis.tags = tags;
    // Remove the old singular timeline from analysis inside javascript object model,
    // and instead use the new array root field to reflect backend migration.
    delete currentDetailItem.analysis.timeline;
    currentDetailItem.timeline = timeline;

    detailTitleEl.textContent = newTitle || "Untitled";
    setDetailEditMode(false);
    renderFilteredItems();
  } catch (error) {
    alert(error.message || "Failed to update item");
  }
}

async function loadDetailNotes() {
  if (!currentDetailItem) return;
  detailNotesLoading.style.display = "inline";
  const itemId = getItemId(currentDetailItem);

  try {
    const response = await fetch(`/api/items/${itemId}/notes`);
    if (!response.ok) {
      throw new Error("Failed to load notes");
    }
    const notes = await response.json();
    noteCounts[itemId] = notes.length;
    updateNoteCountBadge(itemId, notes.length);
    renderDetailNotes(notes);
  } catch (error) {
    detailNotesList.innerHTML = `<div class="detail-muted">${error.message || "Failed to load notes"}</div>`;
  } finally {
    detailNotesLoading.style.display = "none";
  }
}

function renderDetailNotes(notes) {
  detailNotesList.innerHTML = "";
  if (!notes.length) {
    detailNotesList.innerHTML = '<div class="detail-muted">No notes yet.</div>';
    return;
  }

  notes.forEach((note) => {
    const noteEl = document.createElement("div");
    noteEl.className = "detail-note";

    if (note.note_type === "follow_up") {
      const badge = document.createElement("span");
      badge.className = "note-type-badge";
      badge.textContent = "Follow-up";
      noteEl.appendChild(badge);
    }

    const textEl = document.createElement("div");
    textEl.textContent = note.text || "";
    noteEl.appendChild(textEl);

    if (note.image_path) {
      const img = document.createElement("img");
      img.src = note.image_path;
      img.alt = "Note attachment";
      img.style.maxWidth = "100%";
      img.style.marginTop = "8px";
      noteEl.appendChild(img);
    }

    const meta = document.createElement("div");
    meta.className = "detail-note-meta";
    meta.textContent = note.updated_at
      ? `Updated ${formatDate(note.updated_at)}`
      : "";
    noteEl.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "detail-note-actions";

    const editBtn = document.createElement("button");
    editBtn.className = "btn-secondary";
    editBtn.type = "button";
    editBtn.textContent = "Edit";
    editBtn.onclick = async () => {
      const newText = prompt("Edit note", note.text || "");
      if (newText === null) return;
      await updateNote(note.id, newText);
    };

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "btn-secondary";
    deleteBtn.type = "button";
    deleteBtn.textContent = "Delete";
    deleteBtn.onclick = async () => {
      if (!confirm("Delete this note?")) return;
      await deleteNote(note.id);
    };

    actions.appendChild(editBtn);
    actions.appendChild(deleteBtn);
    noteEl.appendChild(actions);
    detailNotesList.appendChild(noteEl);
  });
}

async function updateNote(noteId, text) {
  try {
    const response = await fetch(`/api/notes/${noteId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...getCsrfHeaders(),
      },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) {
      throw new Error("Failed to update note");
    }
    await loadDetailNotes();
  } catch (error) {
    alert(error.message || "Failed to update note");
  }
}

async function deleteNote(noteId) {
  try {
    const response = await fetch(`/api/notes/${noteId}`, {
      method: "DELETE",
      headers: {
        ...getCsrfHeaders(),
      },
    });
    if (!response.ok) {
      throw new Error("Failed to delete note");
    }
    await loadDetailNotes();
  } catch (error) {
    alert(error.message || "Failed to delete note");
  }
}

// Render media item (image)
function renderMediaItem(item, container) {
  if (currentView === "timeline") {
    return;
  }
  const img = document.createElement("img");
  img.className = "item-image";
  img.src = item.content;
  img.alt = item.title || "Shared image";
  img.loading = "lazy";

  img.onerror = () => {
    const errorDiv = document.createElement("div");
    errorDiv.className = "item-image-error";
    errorDiv.textContent = "Image could not be loaded";
    container.innerHTML = "";
    container.appendChild(errorDiv);
  };

  container.appendChild(img);
}

// Render video item
function renderVideoItem(item, container) {
  const video = document.createElement("video");
  video.className = "item-video";
  video.src = item.content;
  video.controls = true;
  video.preload = "metadata";
  container.appendChild(video);
}

// Render audio item
function renderAudioItem(item, container) {
  const audio = document.createElement("audio");
  audio.className = "item-audio";
  audio.src = item.content;
  audio.controls = true;
  audio.preload = "metadata";
  container.appendChild(audio);
}

// Render web URL item
function renderWebUrlItem(item, container) {
  const link = document.createElement("a");
  link.className = "item-url";
  link.href = item.content;
  link.target = "_blank";
  link.rel = "noopener noreferrer";

  let domain = "";
  try {
    const url = new URL(item.content);
    domain = url.hostname;
  } catch {
    domain = item.content;
  }

  const favicon = document.createElement("img");
  favicon.className = "item-url-favicon";
  favicon.src = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
  favicon.alt = "";
  link.appendChild(favicon);

  const info = document.createElement("div");
  info.className = "item-url-info";

  const title = document.createElement("div");
  title.className = "item-url-title";
  title.textContent = item.title || item.content;
  info.appendChild(title);

  const domainEl = document.createElement("div");
  domainEl.className = "item-url-domain";
  domainEl.textContent = domain;
  info.appendChild(domainEl);

  link.appendChild(info);
  container.appendChild(link);
}

// Render text item with truncation
function renderTextItem(item, container) {
  const text = document.createElement("div");
  text.className = "item-text truncated";
  text.textContent = item.content || "";

  text.onclick = () => {
    if (text.classList.contains("truncated")) {
      text.classList.remove("truncated");
      text.classList.add("expanded");
    } else {
      text.classList.remove("expanded");
      text.classList.add("truncated");
    }
  };

  container.appendChild(text);
}

// Render file item
function renderFileItem(item, container) {
  const fileDiv = document.createElement("div");
  fileDiv.className = "item-file";

  const icon = document.createElement("span");
  icon.className = "item-file-icon";
  icon.textContent = getFileIcon(item); // File emoji
  fileDiv.appendChild(icon);

  const name = document.createElement("span");
  name.className = "item-file-name";
  name.textContent =
    item.title ||
    item.item_metadata?.fileName ||
    item.content ||
    "Unknown file";
  fileDiv.appendChild(name);

  if (item.content) {
    const link = document.createElement("a");
    link.className = "item-file-link";
    link.href = item.content;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Open";
    fileDiv.appendChild(link);
  }

  container.appendChild(fileDiv);
}

// Delete an item
async function deleteItem(id) {
  if (!confirm("Are you sure you want to delete this item?")) {
    return;
  }

  try {
    const response = await fetch(`/api/items/${id}`, {
      method: "DELETE",
      headers: {
        ...getCsrfHeaders(),
      },
    });

    if (response.ok) {
      allItems = allItems.filter(
        (item) => (item.firestore_id || item.id) !== id,
      );
      delete noteCounts[id];
      renderFilteredItems();
    } else {
      alert("Failed to delete item");
    }
  } catch (error) {
    console.error("Delete error:", error);
    alert("An error occurred while deleting");
  }
}

async function setItemHidden(id, hidden) {
  const action = hidden ? "hide" : "unhide";

  try {
    const response = await fetch(`/api/items/${id}/${action}`, {
      method: "PATCH",
      headers: {
        ...getCsrfHeaders(),
      },
    });

    if (response.ok) {
      const item = allItems.find(
        (entry) => (entry.firestore_id || entry.id) === id,
      );
      if (item) {
        item.hidden = hidden;
      }
      renderFilteredItems();
    } else {
      alert(`Failed to ${hidden ? "hide" : "unhide"} item`);
    }
  } catch (error) {
    console.error("Hide error:", error);
    alert("An error occurred while updating item visibility");
  }
}

// Format date to localized string
function formatDate(dateStr) {
  if (!dateStr) return "";

  try {
    const date = new Date(dateStr);
    return date.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

// Format type for display
function formatType(type) {
  if (!type) return "Text";
  const labels = {
    text: "Text",
    web_url: "Web URL",
    image: "Image",
    video: "Video",
    audio: "Audio",
    file: "File",
    screenshot: "Screenshot",
    media: "Media",
  };
  return labels[type] || type.replace("_", " ");
}

function normalizeType(item) {
  const rawType = (item.type || "").toString();
  const normalized = rawType.toLowerCase();

  if (normalized === "weburl" || normalized === "web_url") {
    return "web_url";
  }

  const mimeType =
    item.item_metadata?.mimeType || item.item_metadata?.mime_type;
  if (mimeType) {
    if (mimeType.startsWith("image/")) return "image";
    if (mimeType.startsWith("video/")) return "video";
    if (mimeType.startsWith("audio/")) return "audio";
  }

  if (normalized === "media") {
    return "image";
  }

  return normalized || "text";
}

function getFileIcon(item) {
  const type = normalizeType(item);
  if (type === "video") return "\uD83C\uDFA5";
  if (type === "audio") return "\uD83C\uDFB5";
  if (type === "image") return "🖼️";
  return "\uD83D\uDCC4";
}

// Start the app
init();
