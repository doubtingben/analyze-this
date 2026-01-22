let savedImages = [];

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.target !== 'offscreen') {
        return;
    }

    if (message.type === 'init-stitch') {
        savedImages = [];
        console.log("Offscreen: Initialized stitching");
        sendResponse({ success: true });
        return false; // sync response
    }

    if (message.type === 'add-image') {
        savedImages.push(message.data);
        sendResponse({ success: true });
        return false; // sync response
    }

    if (message.type === 'finish-stitch') {
        console.log("Offscreen: Finishing stitch with " + savedImages.length + " images");

        // Handle async work inside IIFE or just async logic without returning promise from listener
        (async () => {
            try {
                const { width, height, devicePixelRatio, token, title } = message.data;
                const blob = await stitchImages(savedImages, width, height, devicePixelRatio);

                // Upload directly from here
                const uploadUrl = `${CONFIG.API_BASE_URL}/api/share`;
                console.log(`Offscreen: Uploading to ${uploadUrl} (${blob.size} bytes)...`);

                const formData = new FormData();
                formData.append('title', title || "Full Page Screenshot");
                formData.append('type', 'media');
                formData.append('file', blob, 'screenshot.png');

                const response = await fetch(uploadUrl, {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${token}`
                    },
                    body: formData
                });

                const responseText = await response.text();
                console.log(`Offscreen: Upload Response Status: ${response.status} ${response.statusText}`);
                console.log("Offscreen: Response Body:", responseText);

                if (response.ok) {
                    console.log("Offscreen: Upload successful");
                    sendResponse({ success: true, uploaded: true, status: response.status, endpoint: uploadUrl });
                } else {
                    console.error("Offscreen: Upload failed", responseText);
                    sendResponse({ success: false, error: "Upload failed: " + response.status + " " + responseText });
                }
            } catch (error) {
                console.error("Offscreen: Stitch/Upload failed", error);
                sendResponse({ success: false, error: error.message });
            } finally {
                // Clear memory
                savedImages = [];
            }
        })();

        return true; // Keep channel open for async response
    }
});

async function stitchImages(images, totalWidth, totalHeight, devicePixelRatio) {
    const canvas = document.createElement('canvas');
    // Adjust for device pixel ratio if captured screenshots are high res
    // captureVisibleTab returns images at actual device pixel resolution usually.
    // totalWidth/Height passed from content script are usually CSS pixels.
    // We should scale the canvas to match the screenshots.

    canvas.width = totalWidth * devicePixelRatio;
    canvas.height = totalHeight * devicePixelRatio;

    const ctx = canvas.getContext('2d');

    // Draw images
    for (const item of images) {
        const img = await loadImage(item.dataUrl);
        ctx.drawImage(img, 0, item.y * devicePixelRatio);
    }

    return new Promise((resolve) => {
        canvas.toBlob(resolve, 'image/png');
    });
}

function loadImage(url) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = url;
    });
}
