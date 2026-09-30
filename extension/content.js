function syncSettingsToPage() {
    chrome.storage.local.get(['micSettings', 'louders_license_state'], (result) => {
        const settings = result.micSettings || {};
        const licenseState = result.louders_license_state;
        const isLicensed = !!(licenseState && licenseState.isLicensed);
        
        window.postMessage({
            type: 'MIC_ENHANCER_UPDATE',
            settings: {
                ...settings,
                isLicensed: isLicensed
            }
        }, '*');
    });
}

// Initial sync on load
syncSettingsToPage();

// Listen to storage changes (sliders or license status updates)
chrome.storage.onChanged.addListener((changes, namespace) => {
    if (namespace === 'local' && (changes.micSettings || changes.louders_license_state)) {
        syncSettingsToPage();
    }
});

// Page asks for initial settings
window.addEventListener('message', (event) => {
    if (event.source !== window) return;
    if (event.data && event.data.type === 'MIC_ENHANCER_INIT') {
        syncSettingsToPage();
    }
});

// Runtime messages from popup or background worker
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'MIC_ENHANCER_UPDATE' && request.settings) {
        chrome.storage.local.get(['louders_license_state'], (result) => {
            const isLicensed = !!(result.louders_license_state && result.louders_license_state.isLicensed);
            window.postMessage({
                type: 'MIC_ENHANCER_UPDATE',
                settings: {
                    ...request.settings,
                    isLicensed: isLicensed
                }
            }, '*');
        });
    } else if (request.type === 'MIC_ENHANCER_LICENSE_UPDATE') {
        syncSettingsToPage();
    }
});
