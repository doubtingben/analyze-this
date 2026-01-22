# Full-Page Screenshot Capture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace "Analyze this page" context menu to capture full-page screenshots using scroll-and-stitch instead of sending URLs.

**Architecture:** Content script handles scrolling and stitching, background script calls `captureVisibleTab()` and uploads the final blob. Backend already supports multipart file uploads.

**Tech Stack:** Chrome Extension APIs (scripting, tabs.captureVisibleTab), Canvas API, FastAPI multipart handling

---

### Task 1: Create the Capture Content Script

**Files:**
- Create: `extension/capture.js`

**Step 1: Create the capture content script with overlay and scroll logic**

```javascript
// capture.js - Content script for full-page screenshot capture

(function() {
  const MAX_HEIGHT = 15000;
  const CAPTURE_DELAY = 150;

  // Show overlay to block interaction
  function showOverlay() {
    const overlay = document.createElement('div');
    overlay.id = 'analyze-this-capture-overlay';
    overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.7);
      z-index: 2147483647;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 24px;
    `;
    overlay.innerHTML = '<div>Capturing page...</div>';
    document.body.appendChild(overlay);
    return overlay;
  }

  function removeOverlay(overlay) {
    if (overlay && overlay.parentNode) {
      overlay.parentNode.removeChild(overlay);
    }
  }

  async function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async function captureFullPage() {
    const overlay = showOverlay();
    const originalScrollX = window.scrollX;
    const originalScrollY = window.scrollY;

    try {
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const fullHeight = Math.min(document.documentElement.scrollHeight, MAX_HEIGHT);
      const fullWidth = document.documentElement.scrollWidth;

      // Calculate chunks
      const chunks = [];
      let currentY = 0;

      while (currentY < fullHeight) {
        const chunkHeight = Math.min(viewportHeight, fullHeight - currentY);
        chunks.push({ y: currentY, height: chunkHeight });
        currentY += viewportHeight;
      }

      // Capture each chunk
      const capturedImages = [];
      for (let i = 0; i < chunks.length; i++) {
        const chunk = chunks[i];
        window.scrollTo(0, chunk.y);
        await delay(CAPTURE_DELAY);

        // Request capture from background script
        const dataUrl = await new Promise((resolve, reject) => {
          chrome.runtime.sendMessage({ action: 'captureVisibleTab' }, response => {
            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
            } else if (response.error) {
              reject(new Error(response.error));
            } else {
              resolve(response.dataUrl);
            }
          });
        });

        capturedImages.push({
          dataUrl,
          y: chunk.y,
          height: chunk.height
        });
      }

      // Stitch images on canvas
      const canvas = document.createElement('canvas');
      canvas.width = viewportWidth;
      canvas.height = fullHeight;
      const ctx = canvas.getContext('2d');

      for (const img of capturedImages) {
        const image = new Image();
        await new Promise((resolve, reject) => {
          image.onload = resolve;
          image.onerror = reject;
          image.src = img.dataUrl;
        });

        // For the last chunk, we may need to crop
        const sourceHeight = img.height;
        const sourceY = 0;

        ctx.drawImage(
          image,
          0, sourceY, viewportWidth, sourceHeight,
          0, img.y, viewportWidth, sourceHeight
        );
      }

      // Convert to blob
      const blob = await new Promise(resolve => {
        canvas.toBlob(resolve, 'image/jpeg', 0.85);
      });

      return blob;

    } finally {
      // Always restore scroll and remove overlay
      window.scrollTo(originalScrollX, originalScrollY);
      removeOverlay(overlay);
    }
  }

  // Execute capture and send result back
  captureFullPage()
    .then(blob => {
      // Convert blob to base64 for messaging (can't send blobs directly)
      const reader = new FileReader();
      reader.onload = () => {
        chrome.runtime.sendMessage({
          action: 'captureComplete',
          dataUrl: reader.result
        });
      };
      reader.readAsDataURL(blob);
    })
    .catch(error => {
      chrome.runtime.sendMessage({
        action: 'captureError',
        error: error.message
      });
    });
})();
```

**Step 2: Verify file was created**

Run: `ls -la extension/capture.js`
Expected: File exists with content

**Step 3: Commit**

```bash
git add extension/capture.js
git commit -m "feat(extension): add scroll-and-stitch capture content script"
```

---

### Task 2: Update Background Script for Screenshot Capture

**Files:**
- Modify: `extension/background.js:24-40` (context menu handler)
- Modify: `extension/background.js:42-76` (sendToBackend function)

**Step 1: Add message listener for captureVisibleTab requests**

Add after line 89 in `background.js`:

```javascript
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
    handleCaptureComplete(message.dataUrl, sender.tab);
  }

  if (message.action === 'captureError') {
    console.error('Capture failed:', message.error);
    showNotification('Capture Failed', message.error);
  }
});

// State to track pending captures
let pendingCapture = null;

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
  // Use console for now - notifications require additional permission
  console.log(`[${title}] ${message}`);
}
```

**Step 2: Modify the "analyze-this-page" handler to inject capture script**

Replace lines 30-31 in `background.js`:

```javascript
    } else if (info.menuItemId === "analyze-this-page") {
        // Inject capture script to take full-page screenshot
        chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['capture.js']
        }).catch(error => {
            console.error('Failed to inject capture script:', error);
            showNotification('Capture Failed', 'Cannot capture this page');
        });
```

**Step 3: Verify changes compile (load extension in browser)**

Run: `echo "Load extension in Chrome at chrome://extensions and check for errors"`
Expected: No syntax errors in console

**Step 4: Commit**

```bash
git add extension/background.js
git commit -m "feat(extension): integrate screenshot capture with context menu"
```

---

### Task 3: Update Backend to Handle Screenshot Type

**Files:**
- Modify: `backend/main.py:339` (type handling in multipart)

**Step 1: Update the type handling for screenshots**

The backend already handles multipart uploads correctly. The only change needed is to accept 'screenshot' as a valid type (currently forces 'media' at line 339).

Replace line 339:

```python
                item_data['type'] = item_data.get('type', 'media')  # Preserve type if provided
```

**Step 2: Verify backend starts without errors**

Run: `cd /Users/bwilson/repos/analyze-this-claude-1/backend && python -c "from main import app; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat(backend): support screenshot type in file uploads"
```

---

### Task 4: Manual Integration Test

**Step 1: Start backend server**

Run: `cd /Users/bwilson/repos/analyze-this-claude-1/backend && APP_ENV=development uvicorn main:app --reload --port 8000`

**Step 2: Load extension in Chrome**

1. Open `chrome://extensions`
2. Enable Developer Mode
3. Click "Load unpacked"
4. Select `extension/` folder
5. Check for any errors in service worker console

**Step 3: Test the capture flow**

1. Navigate to any webpage (e.g., https://example.com)
2. Right-click on the page
3. Select "Analyze this page"
4. Verify overlay appears briefly
5. Check backend logs for successful upload
6. Check dashboard for new screenshot item

**Step 4: Verify error handling**

1. Navigate to `chrome://extensions`
2. Right-click and try "Analyze this page"
3. Should show error (restricted page)

---

### Task 5: Final Cleanup and Commit

**Step 1: Test on a longer page**

Navigate to a page with scrollable content and verify stitching works.

**Step 2: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address any issues found during testing"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Create capture.js content script | `extension/capture.js` |
| 2 | Update background.js for screenshot flow | `extension/background.js` |
| 3 | Update backend type handling | `backend/main.py` |
| 4 | Manual integration test | - |
| 5 | Final cleanup | - |
