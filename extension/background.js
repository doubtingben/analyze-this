// Background Service Worker
importScripts('config.js');

const OFFSCREEN_DOCUMENT_PATH = 'offscreen.html';

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
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
    if (info.menuItemId === "analyze-this-selection") {
        console.log("Context menu clicked: analyze-this-selection");
        const selectedText = info.selectionText || "";
        sendToBackend("text", selectedText, tab.title || "Selected Text");
    } else if (info.menuItemId === "analyze-this-page") {
        console.log("Context menu clicked: analyze-this-page");
        // Capture screenshot instead of just URL
        await captureAndSend(tab);
    } else if (info.menuItemId === "analyze-this-image") {
        console.log("Context menu clicked: analyze-this-image");
        const imageUrl = info.srcUrl || "";
        const title = tab.title ? `Image from ${tab.title}` : "Shared Image";
        sendToBackend("media", imageUrl, title);
    }
});

// Receiver for messages (from popup or offscreen)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // Handle request from popup
    if (message.action === "capture_from_popup") {
        console.log("Received capture request from popup");
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
                captureAndSend(tabs[0], message.title);
            }
        });
        sendResponse({ status: "started" });
    }
});

let creatingOffscreenPromise = null;

async function setupOffscreenDocument(path) {
    if (await chrome.offscreen.hasDocument()) {
        return;
    }

    if (creatingOffscreenPromise) {
        await creatingOffscreenPromise;
        return;
    }

    creatingOffscreenPromise = (async () => {
        try {
            await chrome.offscreen.createDocument({
                url: path,
                reasons: ['BLOBS'],
                justification: 'To stitch screenshots',
            });
        } catch (error) {
            if (!error.message.startsWith('Only a single offscreen')) {
                throw error;
            }
        } finally {
            creatingOffscreenPromise = null;
        }
    })();

    await creatingOffscreenPromise;
}

async function captureFullPage(tabId, token, title) {
    // 1. Setup offscreen (safe)
    await setupOffscreenDocument(OFFSCREEN_DOCUMENT_PATH);

    // 2. Re-verify tab status and URL
    let tab;
    try {
        tab = await chrome.tabs.get(tabId);
    } catch (e) {
        throw new Error(`Could not access tab ${tabId}: ${e.message}`);
    }

    console.log(`[Validation] Target Tab: ID=${tabId}, URL=${tab.url}`);

    if (!tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('edge://') || tab.url.startsWith('about:') || tab.url.startsWith('chrome-extension://')) {
        throw new Error(`Blocked restricted URL during execution: ${tab.url}`);
    }

    // 3. Inject scroll script
    try {
        await chrome.scripting.executeScript({
            target: { tabId },
            files: ['scroll.js']
        });
    } catch (e) {
        throw new Error(`Failed to inject script into ${tab.url}: ${e.message}`);
    }

    // Get info
    const response = await chrome.tabs.sendMessage(tabId, { action: 'getPageInfo' });
    if (!response) {
        throw new Error("No response from page info script");
    }
    const { width, height, windowHeight, devicePixelRatio, originalOverflow } = response;

    // Hide scrollbars to avoid stitching them
    await chrome.tabs.sendMessage(tabId, { action: 'hideScrollbars' });

    // Initialize stitch in offscreen
    await chrome.runtime.sendMessage({
        target: 'offscreen',
        type: 'init-stitch'
    });

    let y = 0;
    const MAX_SCROLLS = 75; // Safety limit
    let scrolls = 0;

    try {
        // Scroll and capture loop
        while (y < height && scrolls < MAX_SCROLLS) {
            await chrome.tabs.sendMessage(tabId, { action: 'scrollTo', y });

            // Wait for render/scroll to settle. Increased to 1000ms (safe)
            await new Promise(r => setTimeout(r, 1000));

            const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: 'png' });

            // Send individually to offscreen
            try {
                await chrome.runtime.sendMessage({
                    target: 'offscreen',
                    type: 'add-image',
                    data: { y, dataUrl }
                });
            } catch (e) {
                console.warn("Failed to send chunk to offscreen:", e);
                // Continue scrolling, though stitching will likely have holes
            }

            y += windowHeight;
            scrolls++;
        }
    } finally {
        // Restore scrollbars
        await chrome.tabs.sendMessage(tabId, { action: 'restoreScrollbars', original: originalOverflow });
    }

    // Finish stitch
    let stitchResponse;
    try {
        stitchResponse = await chrome.runtime.sendMessage({
            target: 'offscreen',
            type: 'finish-stitch',
            data: { width, height, devicePixelRatio, token, title }
        });
    } catch (e) {
        throw new Error("Failed to receive stitch/upload response: " + e.message);
    }

    if (!stitchResponse || !stitchResponse.success) {
        throw new Error((stitchResponse && stitchResponse.error) || "Failed to stitch/upload images (Unknown error)");
    }
    return stitchResponse; // contains {success: true, uploaded: true}
}

async function captureAndSend(tab, customTitle) {
    if (!tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('edge://') || tab.url.startsWith('about:') || tab.url.startsWith('chrome-extension://')) {
        console.error("Cannot capture restricted URL:", tab.url);
        // We could notify user here but for now just log
        return;
    }

    try {
        console.log("Starting full page capture...");
        const token = await getAuthToken();
        if (!token) {
            console.error("No auth token available.");
            return;
        }

        // Pass token and title to capture function which passes it to offscreen
        const result = await captureFullPage(tab.id, token, customTitle || tab.title);

        if (result.uploaded) {
            console.log("Capture and upload complete.");
        } else {
            console.error("Capture finished but upload status unknown");
        }

    } catch (e) {
        console.error("Capture failed:", e);
    }
}

// --- API Methods ---

async function sendFormDataToBackend(formData) {
    try {
        const token = await getAuthToken();
        if (!token) {
            console.error("No auth token available.");
            return;
        }

        const response = await fetch(`${CONFIG.API_BASE_URL}/api/share`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
                // do NOT set Content-Type header manually for FormData, browser does it with boundary
            },
            body: formData
        });

        if (response.ok) {
            console.log("Screenshot shared successfully");
        } else {
            console.error("Failed to share", await response.text());
        }
    } catch (error) {
        console.error("Error sharing item:", error);
    }
}

async function sendToBackend(type, content, title) {
    try {
        // Get OAuth Token
        const token = await getAuthToken();
        if (!token) {
            console.error("No auth token available. Please login via popup.");
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
                user_email: "me@example.com"
            })
        });

        if (response.ok) {
            console.log("Item shared successfully");
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
