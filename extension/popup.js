document.addEventListener('DOMContentLoaded', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (tab) {
        document.getElementById('title').value = tab.title || '';
        document.getElementById('content').value = tab.url || '';
    }

    document.getElementById('send-btn').addEventListener('click', async () => {
        const title = document.getElementById('title').value;
        const content = document.getElementById('content').value;
        const statusEl = document.getElementById('status');
        const errorEl = document.getElementById('error');

        statusEl.innerText = 'Sending...';
        errorEl.innerText = '';

        try {
            const authResult = await getAuthToken();
            if (authResult.error) {
                errorEl.innerText = 'Auth Error: ' + authResult.error;
                return;
            }
            const token = authResult.token;

            const response = await fetch(`${CONFIG.API_BASE_URL}/api/share`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify({
                    type: "webUrl",
                    content: content,
                    title: title,
                    user_email: "placeholder"
                })
            });

            if (response.ok) {
                statusEl.innerText = 'Saved successfully!';
                setTimeout(() => window.close(), 1500);
            } else {
                errorEl.innerText = 'Error: ' + response.statusText;
            }

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
