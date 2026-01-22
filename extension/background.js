// Background Service Worker
importScripts('config.js');

// Create context menu on install
chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
        id: "analyze-this-selection",
        title: "Analyze selection",
        contexts: ["selection"]
    });
    chrome.contextMenus.create({
        id: "analyze-this-page",
        title: "Analyze this page",
        contexts: ["page"]
    });
    chrome.contextMenus.create({
        id: "analyze-this-image",
        title: "Analyze this image",
        contexts: ["image"]
    });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === "analyze-this-selection") {
        console.log("Context menu clicked: analyze-this-selection");
        const selectedText = info.selectionText || "";
        console.log("Selected text:", selectedText);
        sendToBackend("text", selectedText, tab.title || "Selected Text");
    } else if (info.menuItemId === "analyze-this-page") {
        console.log("Context menu clicked: analyze-this-page");
        // Inject capture script to take full-page screenshot
        chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['capture.js']
        }).catch(error => {
            console.error('Failed to inject capture script:', error);
            showNotification('Capture Failed', 'Cannot capture this page');
        });
    } else if (info.menuItemId === "analyze-this-image") {
        console.log("Context menu clicked: analyze-this-image");
        const imageUrl = info.srcUrl || "";
        console.log("Image URL:", imageUrl);
        // Use page title for context, with "Image from" prefix
        const title = tab.title ? `Image from ${tab.title}` : "Shared Image";
        sendToBackend("media", imageUrl, title);
    }
});

async function sendToBackend(type, content, title) {
    try {
        // Get OAuth Token
        const token = await getAuthToken();
        if (!token) {
            console.error("No auth token available. Please login via popup.");
            showNotification('Not Signed In', 'Please sign in via the extension popup');
            return;
        }

        const response = await fetch(`${CONFIG.API_BASE_URL}/api/share`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                type: type,
                content: content,
                title: title,
                user_email: "me@example.com" // Backend will overwrite this from token but model expects it
            })
        });

        if (response.ok) {
            console.log("Item shared successfully");
            showNotification('Success', 'Item shared successfully');
        } else {
            const errorText = await response.text();
            console.error("Failed to share", errorText);
            showNotification('Share Failed', errorText || 'Unknown error');
        }

    } catch (error) {
        console.error("Error sharing item:", error);
        showNotification('Error', error.message || 'Failed to share item');
    }
}

function getAuthToken() {
    return new Promise((resolve) => {
        chrome.identity.getAuthToken({ interactive: true }, (token) => {
            if (chrome.runtime.lastError) {
                console.error(chrome.runtime.lastError);
                resolve(null);
            } else {
                resolve(token);
            }
        });
    });
}

// Message handler for capture requests
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'captureVisibleTab') {
        chrome.tabs.captureVisibleTab(null, { format: 'png' }, dataUrl => {
            if (chrome.runtime.lastError) {
                sendResponse({ error: chrome.runtime.lastError.message });
            } else {
                sendResponse({ dataUrl });
            }
        });
        return true; // Keep message channel open for async response
    }

    if (message.action === 'captureComplete') {
        if (!sender.tab) {
            console.error('captureComplete: sender.tab is undefined');
            return;
        }
        handleCaptureComplete(message.dataUrl, sender.tab);
    }

    if (message.action === 'captureError') {
        console.error('Capture failed:', message.error);
        showNotification('Capture Failed', message.error);
    }
});

async function handleCaptureComplete(dataUrl, tab) {
    try {
        const token = await getAuthToken();
        if (!token) {
            showNotification('Error', 'Not authenticated');
            return;
        }

        // Convert data URL to blob
        const response = await fetch(dataUrl);
        const blob = await response.blob();

        // Create form data
        const formData = new FormData();
        formData.append('file', blob, 'screenshot.jpg');
        formData.append('type', 'screenshot');
        formData.append('title', tab.title || 'Page Screenshot');

        // Upload to backend
        const uploadResponse = await fetch(`${CONFIG.API_BASE_URL}/api/share`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        if (uploadResponse.ok) {
            showNotification('Success', 'Screenshot captured and shared');
        } else {
            const errorText = await uploadResponse.text();
            showNotification('Upload Failed', errorText);
        }
    } catch (error) {
        console.error('Upload error:', error);
        showNotification('Error', error.message);
    }
}

function showNotification(title, message) {
    const notificationId = 'analyze-this-' + Date.now();
    chrome.notifications.create(notificationId, {
        type: 'basic',
        iconUrl: 'icons/icon128.png',
        title: title,
        message: message
    }, (createdId) => {
        if (chrome.runtime.lastError) {
            console.error('Notification error:', chrome.runtime.lastError.message);
        } else {
            console.log('Notification created:', createdId);
        }
    });
}
