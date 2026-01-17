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
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === "analyze-this-selection") {
        console.log("Context menu clicked: analyze-this-selection");
        const selectedText = info.selectionText || "";
        console.log("Selected text:", selectedText);
        sendToBackend("text", selectedText, tab.title || "Selected Text");
    } else if (info.menuItemId === "analyze-this-page") {
        sendToBackend("webUrl", tab.url, tab.title || "Web Page");
    }
});

async function sendToBackend(type, content, title) {
    try {
        // Get OAuth Token
        const token = await getAuthToken();
        if (!token) {
            console.error("No auth token available. Please login via popup.");
            // Open popup or alert user (limitations in SW)
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
            // Optionally show notification
        } else {
            console.error("Failed to share", await response.text());
        }

    } catch (error) {
        console.error("Error sharing item:", error);
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
