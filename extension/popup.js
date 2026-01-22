document.addEventListener('DOMContentLoaded', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (tab) {
        document.getElementById('title').value = tab.title || '';
        document.getElementById('content').value = tab.url || '';
    }

    document.getElementById('send-btn').addEventListener('click', async () => {
        const titleInput = document.getElementById('title');
        const customTitle = titleInput ? titleInput.value : "";

        const statusEl = document.getElementById('status');
        const errorEl = document.getElementById('error');

        statusEl.innerText = 'Starting capture...';
        errorEl.innerText = '';

        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab && (tab.url.startsWith('chrome://') || tab.url.startsWith('edge://') || tab.url.startsWith('about:') || tab.url.startsWith('chrome-extension://'))) {
            errorEl.innerText = 'Error: Cannot capture restricted URLs (chrome://, about:, etc).';
            statusEl.innerText = '';
            return;
        }

        // Send message to background script to handle capture
        console.log("Sending message to background...");
        chrome.runtime.sendMessage({
            action: 'capture_from_popup',
            title: customTitle
        }, (response) => {
            console.log("Response received:", response);
            if (chrome.runtime.lastError) {
                console.error("Runtime error:", chrome.runtime.lastError);
                errorEl.innerText = 'Error: ' + chrome.runtime.lastError.message;
            } else if (response && response.status === 'started') {
                statusEl.innerText = 'Capturing started in background...';
                // Close popup after a delay to show status
                setTimeout(() => window.close(), 3000);
            } else {
                errorEl.innerText = 'Unknown response from background';
            }
        });
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
