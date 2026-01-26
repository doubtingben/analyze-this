document.addEventListener('DOMContentLoaded', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) {
        document.getElementById('title').value = tab.title || '';
    }

    document.getElementById('send-btn').addEventListener('click', async () => {
        const title = document.getElementById('title').value;
        const statusEl = document.getElementById('status');
        const errorEl = document.getElementById('error');

        statusEl.innerText = 'Capturing & Sending...';
        errorEl.innerText = '';

        try {
            // Need to capture the visible tab
            const [currentTab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (!currentTab) {
                errorEl.innerText = 'No active tab found';
                return;
            }

            chrome.tabs.captureVisibleTab(null, { format: 'png' }, (dataUrl) => {
                if (chrome.runtime.lastError) {
                    errorEl.innerText = 'Capture Error: ' + chrome.runtime.lastError.message;
                    return;
                }

                // Send to background to handle the upload
                chrome.runtime.sendMessage({
                    action: 'uploadCapture',
                    dataUrl: dataUrl,
                    title: title,
                    url: currentTab.url
                });

                // We can close the popup now, background handles the rest
                statusEl.innerText = 'Sent to background processing...';
                setTimeout(() => window.close(), 1000);
            });
        } catch (e) {
            errorEl.innerText = 'Error: ' + e.message;
        }
    });
});

function getAuthToken() {
    return new Promise((resolve) => {
        chrome.identity.getAuthToken({ interactive: true }, (token) => {
            if (chrome.runtime.lastError) {
                console.error(chrome.runtime.lastError);
                resolve({ error: chrome.runtime.lastError.message });
            } else {
                resolve({ token });
            }
        });
    });
}
