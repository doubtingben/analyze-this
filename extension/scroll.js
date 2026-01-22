// Initial scroll setup
function getPageInfo() {
    const body = document.body;
    const html = document.documentElement;

    const fullHeight = Math.max(
        body.scrollHeight, body.offsetHeight,
        html.clientHeight, html.scrollHeight, html.offsetHeight
    );

    return {
        width: window.innerWidth, // Use visual viewport width
        height: fullHeight,
        windowHeight: window.innerHeight,
        devicePixelRatio: window.devicePixelRatio,
        originalOverflow: document.body.style.overflow
    };
}

function scrollTo(y) {
    window.scrollTo(0, y);
}

function hideScrollbars() {
    document.body.style.overflow = 'hidden';
}

function restoreScrollbars(original) {
    document.body.style.overflow = original || '';
}

// Listen for commands
if (!window.hasAnalyzeThisScrollScript) {
    window.hasAnalyzeThisScrollScript = true;

    chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
        if (msg.action === 'getPageInfo') {
            sendResponse(getPageInfo());
        } else if (msg.action === 'scrollTo') {
            scrollTo(msg.y);
            // Give a bit of time for layout to settle?
            // The background script handles the delay usually.
            sendResponse({ status: 'scrolled' });
        } else if (msg.action === 'hideScrollbars') {
            hideScrollbars();
            sendResponse({ status: 'hidden' });
        } else if (msg.action === 'restoreScrollbars') {
            restoreScrollbars(msg.original);
            sendResponse({ status: 'restored' });
        }
    });
}
