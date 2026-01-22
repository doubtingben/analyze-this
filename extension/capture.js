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
      reader.onerror = () => {
        chrome.runtime.sendMessage({
          action: 'captureError',
          error: 'Failed to read captured image data'
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
