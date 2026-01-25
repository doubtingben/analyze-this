// DOM Elements
const loadingEl = document.getElementById('loading');
const emptyStateEl = document.getElementById('empty-state');
const itemsContainerEl = document.getElementById('items-container');
const userNameEl = document.getElementById('user-name');
const userInfoEl = document.getElementById('user-info');
const loginStateEl = document.getElementById('login-state');

// Initialize the app
async function init() {
    try {
        const user = await fetchUser();
        if (!user) {
            showLoginState();
            return;
        }
        userNameEl.textContent = `Welcome, ${user.name || user.email}`;

        const items = await fetchItems();
        renderItems(items);
    } catch (error) {
        console.error('Initialization error:', error);
        showLoginState();
    }
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

// Render all items
function renderItems(items) {
    loadingEl.style.display = 'none';

    if (!items || items.length === 0) {
        emptyStateEl.style.display = 'block';
        itemsContainerEl.innerHTML = '';
        return;
    }

    emptyStateEl.style.display = 'none';
    itemsContainerEl.innerHTML = '';

    items.forEach(item => {
        const card = renderItem(item);
        itemsContainerEl.appendChild(card);
    });
}

// Render a single item, dispatching to type-specific renderer
function renderItem(item) {
    const card = document.createElement('div');
    card.className = 'item-card';
    card.dataset.id = item.firestore_id;
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

    // Footer with date and delete button
    const footer = document.createElement('div');
    footer.className = 'item-footer';

    const date = document.createElement('span');
    date.className = 'item-date';
    date.textContent = formatDate(item.created_at);
    footer.appendChild(date);

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'delete-btn';
    deleteBtn.textContent = 'Delete';
    deleteBtn.onclick = () => deleteItem(item.firestore_id);
    footer.appendChild(deleteBtn);

    card.appendChild(footer);

    return card;
}

// Render media item (image)
function renderMediaItem(item, container) {
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
            const card = document.querySelector(`.item-card[data-id="${id}"]`);
            if (card) {
                card.remove();
            }

            // Check if empty
            if (itemsContainerEl.children.length === 0) {
                emptyStateEl.style.display = 'block';
            }
        } else {
            alert('Failed to delete item');
        }
    } catch (error) {
        console.error('Delete error:', error);
        alert('An error occurred while deleting');
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
