// DOM Elements
const loadingEl = document.getElementById('loading');
const emptyStateEl = document.getElementById('empty-state');
const itemsContainerEl = document.getElementById('items-container');
const userNameEl = document.getElementById('user-name');
const userInfoEl = document.getElementById('user-info');
const userMenuTriggerEl = document.getElementById('user-menu-trigger');
const userMenuEl = document.getElementById('user-menu');
const loginStateEl = document.getElementById('login-state');
const filtersEl = document.getElementById('filters');
const typeFilterEl = document.getElementById('type-filter');
const showHiddenEl = document.getElementById('show-archive');
const exportBtnEl = document.getElementById('export-btn');
const newItemBtn = document.getElementById('new-item-btn');
const createModal = document.getElementById('create-modal');
const createForm = document.getElementById('create-form');
const itemTypeSelect = document.getElementById('item-type');
const modalCloseBtn = document.getElementById('modal-close');
const cancelCreateBtn = document.getElementById('cancel-create');
const detailModal = document.getElementById('detail-modal');
const detailBackdrop = document.getElementById('detail-modal-backdrop');
const detailCloseBtn = document.getElementById('detail-modal-close');
const detailEditBtn = document.getElementById('detail-edit-btn');
const detailTitleEl = document.getElementById('detail-title');
const detailTitleInput = document.getElementById('detail-title-input');
const detailTypeEl = document.getElementById('detail-type');
const detailContentEl = document.getElementById('detail-content');
const detailTagsEl = document.getElementById('detail-tags');
const detailTagsEditor = document.getElementById('detail-tags-editor');
const detailTagInput = document.getElementById('detail-tag-input');
const detailAddTagBtn = document.getElementById('detail-add-tag');
const detailEditActions = document.getElementById('detail-edit-actions');
const detailCancelBtn = document.getElementById('detail-cancel-btn');
const detailSaveBtn = document.getElementById('detail-save-btn');
const detailNotesList = document.getElementById('detail-notes-list');
const detailNotesLoading = document.getElementById('detail-notes-loading');
const detailNoteForm = document.getElementById('detail-note-form');
const detailNoteText = document.getElementById('detail-note-text');

// State
let allItems = [];
let currentView = 'all'; // 'all', 'timeline', or 'follow_up'
let currentTypeFilter = ''; // '' for all, or specific type
let showHidden = false;
let currentDetailItem = null;
let detailEditMode = false;
let editableTags = [];
let noteCounts = {};

// Initialize the app
async function init() {
    try {
        const user = await fetchUser();
        if (!user) {
            showLoginState();
            return;
        }
        userNameEl.textContent = `Welcome, ${user.name || user.email}`;

        // Show new item button for logged in users
        newItemBtn.style.display = 'block';

        // Setup filter controls
        setupFilters();
        setupUserMenu();

        // Setup create modal
        setupCreateModal();
        setupDetailModal();

        allItems = await fetchItems();
        await fetchNoteCounts(allItems);
        renderFilteredItems();
    } catch (error) {
        console.error('Initialization error:', error);
        showLoginState();
    }
}

function setupDetailModal() {
    if (!detailModal) return;

    detailCloseBtn.addEventListener('click', closeDetailModal);
    detailBackdrop.addEventListener('click', closeDetailModal);

    detailEditBtn.addEventListener('click', () => {
        setDetailEditMode(!detailEditMode);
    });

    detailCancelBtn.addEventListener('click', () => {
        setDetailEditMode(false);
    });

    detailSaveBtn.addEventListener('click', saveDetailEdits);

    detailAddTagBtn.addEventListener('click', (event) => {
        event.preventDefault();
        const tag = detailTagInput.value.trim();
        if (!tag) return;
        if (!editableTags.includes(tag)) {
            editableTags.push(tag);
            renderDetailTags();
        }
        detailTagInput.value = '';
    });

    detailNoteForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!currentDetailItem) return;
        const text = detailNoteText.value.trim();
        if (!text) return;
        const itemId = getItemId(currentDetailItem);

        const formData = new FormData();
        formData.append('text', text);

        try {
            const response = await fetch(`/api/items/${itemId}/notes`, {
                method: 'POST',
                body: formData
            });
            if (!response.ok) {
                throw new Error('Failed to add note');
            }
            detailNoteText.value = '';
            const note = await response.json();
            await loadDetailNotes();
        } catch (error) {
            alert(error.message || 'Failed to add note');
        }
    });
}

// Setup create modal event listeners
function setupCreateModal() {
    // Open modal
    newItemBtn.addEventListener('click', () => {
        createModal.style.display = 'flex';
        createForm.reset();
        updateTypeFields();
    });

    // Close modal
    modalCloseBtn.addEventListener('click', closeModal);
    cancelCreateBtn.addEventListener('click', closeModal);
    createModal.querySelector('.modal-backdrop').addEventListener('click', closeModal);

    // Type selection changes visible fields
    itemTypeSelect.addEventListener('change', updateTypeFields);

    // Form submission
    createForm.addEventListener('submit', handleCreateSubmit);

    // Update file hint based on type
    itemTypeSelect.addEventListener('change', () => {
        const fileHint = document.getElementById('file-hint');
        const type = itemTypeSelect.value;
        const hints = {
            image: 'Select an image file (PNG, JPG, GIF, etc.)',
            video: 'Select a video file (MP4, MOV, etc.)',
            audio: 'Select an audio file (MP3, WAV, etc.)',
            file: 'Select any file to upload'
        };
        fileHint.textContent = hints[type] || 'Select a file to upload';
    });
}

function closeModal() {
    createModal.style.display = 'none';
    createForm.reset();
    updateTypeFields();
}

function updateTypeFields() {
    const selectedType = itemTypeSelect.value;
    document.querySelectorAll('.type-field').forEach(field => {
        const types = field.dataset.types.split(',');
        if (types.includes(selectedType)) {
            field.classList.add('visible');
        } else {
            field.classList.remove('visible');
        }
    });
}

async function handleCreateSubmit(e) {
    e.preventDefault();

    const submitBtn = document.getElementById('submit-create');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Creating...';

    try {
        const type = itemTypeSelect.value;
        const title = document.getElementById('item-title').value;

        const formData = new FormData();
        formData.append('type', type);
        if (title) formData.append('title', title);

        // Add content based on type
        if (type === 'text') {
            const content = document.getElementById('item-text').value;
            if (!content) {
                alert('Please enter text content');
                return;
            }
            formData.append('content', content);
        } else if (type === 'web_url') {
            const url = document.getElementById('item-url').value;
            if (!url) {
                alert('Please enter a URL');
                return;
            }
            formData.append('content', url);
        } else {
            // File types
            const fileInput = document.getElementById('item-file');
            const file = fileInput.files[0];
            if (!file) {
                alert('Please select a file');
                return;
            }
            formData.append('file', file);
            formData.append('file_name', file.name);
            formData.append('mime_type', file.type);
            formData.append('file_size', file.size);
        }

        const response = await fetch('/api/share', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.text();
            throw new Error(error || 'Failed to create item');
        }

        // Refresh items and close modal
        allItems = await fetchItems();
        await fetchNoteCounts(allItems);
        renderFilteredItems();
        closeModal();

    } catch (error) {
        console.error('Create error:', error);
        alert('Failed to create item: ' + error.message);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

// Setup filter event listeners
function setupFilters() {
    // View toggle buttons
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentView = btn.dataset.view;
            renderFilteredItems();
        });
    });

    // Type filter dropdown
    typeFilterEl.addEventListener('change', () => {
        currentTypeFilter = typeFilterEl.value;
        renderFilteredItems();
    });

    if (showHiddenEl) {
        showHidden = showHiddenEl.checked;
        showHiddenEl.addEventListener('change', () => {
            showHidden = showHiddenEl.checked;
            renderFilteredItems();
        });
    }
}

function setupUserMenu() {
    if (userMenuTriggerEl) {
        userMenuTriggerEl.addEventListener('click', (event) => {
            event.stopPropagation();
            toggleUserMenu();
        });
    }

    if (exportBtnEl) {
        exportBtnEl.addEventListener('click', () => {
            window.location.href = '/api/export';
            closeUserMenu();
        });
    }

    document.addEventListener('click', (event) => {
        if (!userMenuEl || !userMenuTriggerEl) return;
        if (userMenuEl.contains(event.target) || userMenuTriggerEl.contains(event.target)) {
            return;
        }
        closeUserMenu();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeUserMenu();
        }
    });
}

function openUserMenu() {
    if (!userMenuEl) return;
    userMenuEl.classList.add('is-open');
    userMenuEl.setAttribute('aria-hidden', 'false');
}

function closeUserMenu() {
    if (!userMenuEl) return;
    userMenuEl.classList.remove('is-open');
    userMenuEl.setAttribute('aria-hidden', 'true');
}

function toggleUserMenu() {
    if (!userMenuEl) return;
    if (userMenuEl.classList.contains('is-open')) {
        closeUserMenu();
    } else {
        openUserMenu();
    }
}

// Get event date from analysis details
function getEventDateTime(item) {
    if (!item.analysis) return null;

    // Check for new 'timeline' structure
    if (item.analysis.timeline) {
        const timeline = item.analysis.timeline;
        if (timeline.date) {
            try {
                let dateStr = timeline.date;
                if (timeline.time) {
                    dateStr += ` ${timeline.time}`;
                }
                const date = new Date(dateStr);
                if (!isNaN(date.getTime())) {
                    return date;
                }
            } catch (e) {
                // fall through
            }
        }
    }

    if (!item.analysis.details) return null;

    const details = item.analysis.details;
    // Look for date_time in various possible field names
    const dateTimeStr = details.date_time || details.dateTime || details.date ||
        details.event_date || details.eventDate || details.start_date;

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
    let items = [...allItems];

    if (!showHidden) {
        items = items.filter(item => !item.hidden);
    }

    // Apply type filter
    if (currentTypeFilter) {
        items = items.filter(item => normalizeType(item) === currentTypeFilter);
    }

    // Apply view-specific filtering and sorting
    if (currentView === 'timeline') {
        // Filter to only items with derived date/time
        items = items.filter(item => getEventDateTime(item) !== null);

        // Sort by event date/time (descending - newest first)
        items.sort((a, b) => {
            const dateA = getEventDateTime(a);
            const dateB = getEventDateTime(b);
            return dateB - dateA;
        });
    } else if (currentView === 'follow_up') {
        // Filter to only items with follow_up status
        items = items.filter(item => item.status === 'follow_up');

        // Sort by created_at descending (newest first)
        items.sort((a, b) => {
            const dateA = new Date(a.created_at || 0);
            const dateB = new Date(b.created_at || 0);
            return dateB - dateA;
        });
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

// Render items with current filters applied
function renderFilteredItems() {
    const items = getFilteredItems();
    renderItems(items);
}

// Show login state (not logged in)
function showLoginState() {
    loadingEl.style.display = 'none';
    userInfoEl.style.display = 'none';
    loginStateEl.style.display = 'block';
}

// Fetch current user
async function fetchUser() {
    const response = await fetch('/api/user');
    if (response.status === 401) {
        return null;
    }
    if (!response.ok) {
        throw new Error('Failed to fetch user');
    }
    return response.json();
}

// Fetch all items
async function fetchItems() {
    const response = await fetch('/api/items');
    if (response.status === 401) {
        showLoginState();
        throw new Error('Not authenticated');
    }
    if (!response.ok) {
        throw new Error('Failed to fetch items');
    }
    return response.json();
}

async function fetchNoteCounts(items) {
    if (!items || items.length === 0) {
        noteCounts = {};
        return;
    }
    const itemIds = items.map(item => getItemId(item)).filter(Boolean);
    if (!itemIds.length) {
        noteCounts = {};
        return;
    }

    try {
        const response = await fetch('/api/items/note-counts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ item_ids: itemIds })
        });
        if (!response.ok) {
            throw new Error('Failed to fetch note counts');
        }
        noteCounts = await response.json();
    } catch (error) {
        console.warn('Note counts unavailable:', error);
        noteCounts = {};
    }
}

// Render all items
function renderItems(items) {
    loadingEl.style.display = 'none';
    filtersEl.style.display = 'flex';

    if (!items || items.length === 0) {
        emptyStateEl.style.display = 'block';
        if (!showHidden && allItems.some(item => item.hidden)) {
            emptyStateEl.querySelector('p').textContent = 'No visible items. Use "Show Archive" to view archived items.';
        } else if (currentView === 'timeline') {
            emptyStateEl.querySelector('p').textContent = 'No items with event dates found.';
        } else if (currentView === 'follow_up') {
            emptyStateEl.querySelector('p').textContent = 'No items need follow-up.';
        } else if (currentTypeFilter) {
            emptyStateEl.querySelector('p').textContent = `No ${formatType(currentTypeFilter)} items found.`;
        } else {
            emptyStateEl.querySelector('p').textContent = 'No items yet. Share something from the mobile app or browser extension!';
        }
        itemsContainerEl.innerHTML = '';
        return;
    }

    emptyStateEl.style.display = 'none';
    itemsContainerEl.innerHTML = '';

    if (currentView === 'timeline') {
        renderTimelineItems(items);
    } else {
        items.forEach(item => {
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

    items.forEach(item => {
        const eventDate = getEventDateTime(item);

        // Insert "Now" divider before the first past item
        if (!nowDividerInserted && eventDate < now) {
            nowDividerEl = document.createElement('div');
            nowDividerEl.className = 'now-divider';
            nowDividerEl.id = 'now-divider';
            nowDividerEl.innerHTML = '<span>Now</span>';
            itemsContainerEl.appendChild(nowDividerEl);
            nowDividerInserted = true;
        }

        const card = renderItem(item);
        if (eventDate < now) {
            card.classList.add('timeline-past');
        }

        // Add event date badge for timeline view
        const eventDateBadge = document.createElement('div');
        eventDateBadge.className = 'event-date-badge';
        eventDateBadge.textContent = formatEventDate(eventDate);
        card.insertBefore(eventDateBadge, card.firstChild);

        itemsContainerEl.appendChild(card);
    });

    // If all items are in the future, add Now divider at the end
    if (!nowDividerInserted && items.length > 0) {
        nowDividerEl = document.createElement('div');
        nowDividerEl.className = 'now-divider';
        nowDividerEl.id = 'now-divider';
        nowDividerEl.innerHTML = '<span>Now</span>';
        itemsContainerEl.appendChild(nowDividerEl);
    }

    // Auto-scroll to Now divider
    if (nowDividerEl) {
        setTimeout(() => {
            nowDividerEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
    }
}

// Format event date for timeline display
function formatEventDate(date) {
    if (!date) return '';
    return date.toLocaleDateString(undefined, {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Render a single item, dispatching to type-specific renderer
function renderItem(item) {
    const card = document.createElement('div');
    card.className = 'item-card';
    card.dataset.id = item.firestore_id || item.id;
    if (item.hidden) {
        card.classList.add('is-hidden');
    }
    const normalizedType = normalizeType(item);

    const header = document.createElement('div');
    header.className = 'item-header';

    const titleSection = document.createElement('div');

    if (item.title) {
        const title = document.createElement('div');
        title.className = 'item-title';
        title.textContent = item.title;
        titleSection.appendChild(title);
    }

    const meta = document.createElement('div');
    meta.className = 'item-meta';

    const badge = document.createElement('span');
    badge.className = `type-badge ${normalizedType}`;
    badge.textContent = formatType(normalizedType);
    meta.appendChild(badge);

    // Analysis Sparkle
    const sparkle = document.createElement('span');
    sparkle.textContent = '✨';
    sparkle.style.marginLeft = '10px';
    sparkle.style.fontSize = '1.2em';

    if (item.analysis) {
        sparkle.style.cursor = 'pointer';
        sparkle.title = 'View Analysis';
        sparkle.onclick = (e) => {
            e.stopPropagation(); // Prevent card clicks if any
            alert(item.analysis.overview);
        };
    } else {
        sparkle.style.filter = 'grayscale(100%)';
        sparkle.style.opacity = '0.5';
        sparkle.style.cursor = 'default';
        sparkle.title = 'No Analysis';
    }
    meta.appendChild(sparkle);

    const count = getNoteCount(item);
    if (count > 0) {
        const noteBadge = document.createElement('span');
        noteBadge.className = 'note-count-badge';
        noteBadge.textContent = `${count}`;
        noteBadge.title = `${count} note${count === 1 ? '' : 's'}`;
        noteBadge.dataset.noteCount = count;
        meta.appendChild(noteBadge);
    }

    titleSection.appendChild(meta);
    header.appendChild(titleSection);

    card.appendChild(header);

    // Type-specific content
    const content = document.createElement('div');
    content.className = 'item-content';

    switch (normalizedType) {
        case 'media':
        case 'image':
        case 'screenshot':
            renderMediaItem(item, content);
            break;
        case 'video':
            renderVideoItem(item, content);
            break;
        case 'audio':
            renderAudioItem(item, content);
            break;
        case 'web_url':
            renderWebUrlItem(item, content);
            break;
        case 'file':
            renderFileItem(item, content);
            break;
        case 'text':
        default:
            renderTextItem(item, content);
            break;
    }

    card.appendChild(content);

    // Details section (hidden by default)
    const details = document.createElement('div');
    details.className = 'item-details';
    details.style.display = 'none';

    const idRow = document.createElement('div');
    idRow.className = 'item-details-row';
    idRow.innerHTML = `<span class="item-details-label">ID:</span> <span class="item-details-value">${item.firestore_id || 'N/A'}</span>`;
    details.appendChild(idRow);

    if (item.analysis?.tags && item.analysis.tags.length > 0) {
        const tagsRow = document.createElement('div');
        tagsRow.className = 'item-details-row';
        const tagsHtml = item.analysis.tags.map(tag => `<span class="item-tag">${tag}</span>`).join('');
        tagsRow.innerHTML = `<span class="item-details-label">Tags:</span> <span class="item-details-tags">${tagsHtml}</span>`;
        details.appendChild(tagsRow);
    }

    card.appendChild(details);

    // Footer with date and actions
    const footer = document.createElement('div');
    footer.className = 'item-footer';

    if (currentView !== 'timeline') {
        const date = document.createElement('span');
        date.className = 'item-date';
        date.textContent = formatDate(item.created_at);
        footer.appendChild(date);
    } else {
        footer.classList.add('item-footer--compact');
    }

    const footerActions = document.createElement('div');
    footerActions.className = 'item-footer-actions';

    const infoBtn = document.createElement('button');
    infoBtn.className = 'info-btn';
    infoBtn.textContent = 'ℹ️';
    infoBtn.title = currentView === 'follow_up' ? 'View details' : 'Show details';
    infoBtn.onclick = () => {
        if (currentView === 'follow_up') {
            openDetailModal(item);
            return;
        }
        const isVisible = details.style.display !== 'none';
        details.style.display = isVisible ? 'none' : 'block';
        infoBtn.classList.toggle('active', !isVisible);
    };
    footerActions.appendChild(infoBtn);

    const hideBtn = document.createElement('button');
    hideBtn.className = 'hide-btn';
    hideBtn.textContent = item.hidden ? 'Unhide' : 'Hide';
    hideBtn.onclick = () => setItemHidden(card.dataset.id, !item.hidden);
    footerActions.appendChild(hideBtn);

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'delete-btn';
    deleteBtn.textContent = 'Delete';
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
    return typeof count === 'number' ? count : 0;
}

function updateNoteCountBadge(itemId, count) {
    const card = document.querySelector(`.item-card[data-id="${itemId}"]`);
    if (!card) return;
    const meta = card.querySelector('.item-meta');
    if (!meta) return;
    const existing = meta.querySelector('.note-count-badge');

    if (count > 0) {
        if (existing) {
            existing.textContent = `${count}`;
            existing.title = `${count} note${count === 1 ? '' : 's'}`;
            existing.dataset.noteCount = count;
        } else {
            const badge = document.createElement('span');
            badge.className = 'note-count-badge';
            badge.textContent = `${count}`;
            badge.title = `${count} note${count === 1 ? '' : 's'}`;
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
    detailModal.style.display = 'flex';
    detailTitleEl.textContent = item.title || 'Untitled';
    detailTitleInput.value = item.title || '';
    detailTypeEl.textContent = formatType(normalizeType(item));

    if (typeof item.content === 'string' && item.content.startsWith('http')) {
        detailContentEl.innerHTML = `<a href="${item.content}" target="_blank" rel="noopener noreferrer">${item.content}</a>`;
    } else {
        detailContentEl.textContent = item.content || '';
    }

    editableTags = item.analysis?.tags ? [...item.analysis.tags] : [];
    renderDetailTags();
    setDetailEditMode(false);
    loadDetailNotes();
}

function closeDetailModal() {
    if (!detailModal) return;
    detailModal.style.display = 'none';
    currentDetailItem = null;
}

function setDetailEditMode(enabled) {
    detailEditMode = enabled;
    detailEditActions.style.display = enabled ? 'flex' : 'none';
    detailTagsEditor.style.display = enabled ? 'flex' : 'none';
    detailTitleInput.style.display = enabled ? 'block' : 'none';
    detailTitleEl.style.display = enabled ? 'none' : 'block';
    detailEditBtn.style.display = enabled ? 'none' : 'inline-flex';
    if (!enabled && currentDetailItem) {
        detailTitleInput.value = currentDetailItem.title || '';
        editableTags = currentDetailItem.analysis?.tags ? [...currentDetailItem.analysis.tags] : [];
    }
    renderDetailTags();
}

function renderDetailTags() {
    detailTagsEl.innerHTML = '';
    if (!editableTags.length) {
        const emptyTag = document.createElement('span');
        emptyTag.className = 'detail-muted';
        emptyTag.textContent = 'No tags';
        detailTagsEl.appendChild(emptyTag);
        return;
    }

    editableTags.forEach(tag => {
        const tagEl = document.createElement('span');
        tagEl.className = 'detail-tag';
        tagEl.textContent = tag;
        if (detailEditMode) {
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.textContent = '×';
            removeBtn.onclick = () => {
                editableTags = editableTags.filter(t => t !== tag);
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

    try {
        const response = await fetch(`/api/items/${itemId}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: newTitle,
                tags: tags
            })
        });
        if (!response.ok) {
            throw new Error('Failed to update item');
        }
        currentDetailItem.title = newTitle;
        currentDetailItem.analysis = currentDetailItem.analysis || {};
        currentDetailItem.analysis.tags = tags;
        detailTitleEl.textContent = newTitle || 'Untitled';
        setDetailEditMode(false);
        renderFilteredItems();
    } catch (error) {
        alert(error.message || 'Failed to update item');
    }
}

async function loadDetailNotes() {
    if (!currentDetailItem) return;
    detailNotesLoading.style.display = 'inline';
    const itemId = getItemId(currentDetailItem);

    try {
        const response = await fetch(`/api/items/${itemId}/notes`);
        if (!response.ok) {
            throw new Error('Failed to load notes');
        }
        const notes = await response.json();
        noteCounts[itemId] = notes.length;
        updateNoteCountBadge(itemId, notes.length);
        renderDetailNotes(notes);
    } catch (error) {
        detailNotesList.innerHTML = `<div class="detail-muted">${error.message || 'Failed to load notes'}</div>`;
    } finally {
        detailNotesLoading.style.display = 'none';
    }
}

function renderDetailNotes(notes) {
    detailNotesList.innerHTML = '';
    if (!notes.length) {
        detailNotesList.innerHTML = '<div class="detail-muted">No notes yet.</div>';
        return;
    }

    notes.forEach(note => {
        const noteEl = document.createElement('div');
        noteEl.className = 'detail-note';

        const textEl = document.createElement('div');
        textEl.textContent = note.text || '';
        noteEl.appendChild(textEl);

        if (note.image_path) {
            const img = document.createElement('img');
            img.src = note.image_path;
            img.alt = 'Note attachment';
            img.style.maxWidth = '100%';
            img.style.marginTop = '8px';
            noteEl.appendChild(img);
        }

        const meta = document.createElement('div');
        meta.className = 'detail-note-meta';
        meta.textContent = note.updated_at ? `Updated ${formatDate(note.updated_at)}` : '';
        noteEl.appendChild(meta);

        const actions = document.createElement('div');
        actions.className = 'detail-note-actions';

        const editBtn = document.createElement('button');
        editBtn.className = 'btn-secondary';
        editBtn.type = 'button';
        editBtn.textContent = 'Edit';
        editBtn.onclick = async () => {
            const newText = prompt('Edit note', note.text || '');
            if (newText === null) return;
            await updateNote(note.id, newText);
        };

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn-secondary';
        deleteBtn.type = 'button';
        deleteBtn.textContent = 'Delete';
        deleteBtn.onclick = async () => {
            if (!confirm('Delete this note?')) return;
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
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text })
        });
        if (!response.ok) {
            throw new Error('Failed to update note');
        }
        await loadDetailNotes();
    } catch (error) {
        alert(error.message || 'Failed to update note');
    }
}

async function deleteNote(noteId) {
    try {
        const response = await fetch(`/api/notes/${noteId}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            throw new Error('Failed to delete note');
        }
        await loadDetailNotes();
    } catch (error) {
        alert(error.message || 'Failed to delete note');
    }
}

// Render media item (image)
function renderMediaItem(item, container) {
    if (currentView === 'timeline') {
        return;
    }
    const img = document.createElement('img');
    img.className = 'item-image';
    img.src = item.content;
    img.alt = item.title || 'Shared image';
    img.loading = 'lazy';

    img.onerror = () => {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'item-image-error';
        errorDiv.textContent = 'Image could not be loaded';
        container.innerHTML = '';
        container.appendChild(errorDiv);
    };

    container.appendChild(img);
}

// Render video item
function renderVideoItem(item, container) {
    const video = document.createElement('video');
    video.className = 'item-video';
    video.src = item.content;
    video.controls = true;
    video.preload = 'metadata';
    container.appendChild(video);
}

// Render audio item
function renderAudioItem(item, container) {
    const audio = document.createElement('audio');
    audio.className = 'item-audio';
    audio.src = item.content;
    audio.controls = true;
    audio.preload = 'metadata';
    container.appendChild(audio);
}

// Render web URL item
function renderWebUrlItem(item, container) {
    const link = document.createElement('a');
    link.className = 'item-url';
    link.href = item.content;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';

    let domain = '';
    try {
        const url = new URL(item.content);
        domain = url.hostname;
    } catch {
        domain = item.content;
    }

    const favicon = document.createElement('img');
    favicon.className = 'item-url-favicon';
    favicon.src = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
    favicon.alt = '';
    link.appendChild(favicon);

    const info = document.createElement('div');
    info.className = 'item-url-info';

    const title = document.createElement('div');
    title.className = 'item-url-title';
    title.textContent = item.title || item.content;
    info.appendChild(title);

    const domainEl = document.createElement('div');
    domainEl.className = 'item-url-domain';
    domainEl.textContent = domain;
    info.appendChild(domainEl);

    link.appendChild(info);
    container.appendChild(link);
}

// Render text item with truncation
function renderTextItem(item, container) {
    const text = document.createElement('div');
    text.className = 'item-text truncated';
    text.textContent = item.content || '';

    text.onclick = () => {
        if (text.classList.contains('truncated')) {
            text.classList.remove('truncated');
            text.classList.add('expanded');
        } else {
            text.classList.remove('expanded');
            text.classList.add('truncated');
        }
    };

    container.appendChild(text);
}

// Render file item
function renderFileItem(item, container) {
    const fileDiv = document.createElement('div');
    fileDiv.className = 'item-file';

    const icon = document.createElement('span');
    icon.className = 'item-file-icon';
    icon.textContent = getFileIcon(item); // File emoji
    fileDiv.appendChild(icon);

    const name = document.createElement('span');
    name.className = 'item-file-name';
    name.textContent = item.title || item.item_metadata?.fileName || item.content || 'Unknown file';
    fileDiv.appendChild(name);

    if (item.content) {
        const link = document.createElement('a');
        link.className = 'item-file-link';
        link.href = item.content;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'Open';
        fileDiv.appendChild(link);
    }

    container.appendChild(fileDiv);
}

// Delete an item
async function deleteItem(id) {
    if (!confirm('Are you sure you want to delete this item?')) {
        return;
    }

    try {
        const response = await fetch(`/api/items/${id}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            allItems = allItems.filter(item => (item.firestore_id || item.id) !== id);
            delete noteCounts[id];
            renderFilteredItems();
        } else {
            alert('Failed to delete item');
        }
    } catch (error) {
        console.error('Delete error:', error);
        alert('An error occurred while deleting');
    }
}

async function setItemHidden(id, hidden) {
    const action = hidden ? 'hide' : 'unhide';

    try {
        const response = await fetch(`/api/items/${id}/${action}`, {
            method: 'PATCH'
        });

        if (response.ok) {
            const item = allItems.find(entry => (entry.firestore_id || entry.id) === id);
            if (item) {
                item.hidden = hidden;
            }
            renderFilteredItems();
        } else {
            alert(`Failed to ${hidden ? 'hide' : 'unhide'} item`);
        }
    } catch (error) {
        console.error('Hide error:', error);
        alert('An error occurred while updating item visibility');
    }
}

// Format date to localized string
function formatDate(dateStr) {
    if (!dateStr) return '';

    try {
        const date = new Date(dateStr);
        return date.toLocaleString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return dateStr;
    }
}

// Format type for display
function formatType(type) {
    if (!type) return 'Text';
    const labels = {
        text: 'Text',
        web_url: 'Web URL',
        image: 'Image',
        video: 'Video',
        audio: 'Audio',
        file: 'File',
        screenshot: 'Screenshot',
        media: 'Media'
    };
    return labels[type] || type.replace('_', ' ');
}

function normalizeType(item) {
    const rawType = (item.type || '').toString();
    const normalized = rawType.toLowerCase();

    if (normalized === 'weburl' || normalized === 'web_url') {
        return 'web_url';
    }

    const mimeType = item.item_metadata?.mimeType || item.item_metadata?.mime_type;
    if (mimeType) {
        if (mimeType.startsWith('image/')) return 'image';
        if (mimeType.startsWith('video/')) return 'video';
        if (mimeType.startsWith('audio/')) return 'audio';
    }

    if (normalized === 'media') {
        return 'image';
    }

    return normalized || 'text';
}

function getFileIcon(item) {
    const type = normalizeType(item);
    if (type === 'video') return '\uD83C\uDFA5';
    if (type === 'audio') return '\uD83C\uDFB5';
    if (type === 'image') return '🖼️';
    return '\uD83D\uDCC4';
}

// Start the app
init();
