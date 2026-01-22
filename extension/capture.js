// capture.js - Content script for visible viewport screenshot capture

(function() {
  // Simply request a capture of the visible viewport from background script
  chrome.runtime.sendMessage({ action: 'captureVisibleTab' }, response => {
    if (chrome.runtime.lastError) {
      chrome.runtime.sendMessage({
        action: 'captureError',
        error: chrome.runtime.lastError.message
      });
      return;
    }

    if (response.error) {
      chrome.runtime.sendMessage({
        action: 'captureError',
        error: response.error
      });
      return;
    }

    // Send the captured image directly - no processing needed
    chrome.runtime.sendMessage({
      action: 'captureComplete',
      dataUrl: response.dataUrl
    });
  });
})();
