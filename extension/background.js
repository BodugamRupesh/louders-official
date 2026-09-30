// background.js - Louders Official Service Worker with License Verification
importScripts('licenseManager.js');

chrome.runtime.onInstalled.addListener(() => {
    console.log("[Louders Official] Installed successfully.");
    
    // Setup recurring background license verification / heartbeat
    chrome.alarms.create('license_heartbeat', {
        periodInMinutes: 60
    });

    // Check license state on install
    LicenseManager.getLicenseState().then((state) => {
        if (state && state.isLicensed) {
            LicenseManager.verifyLicense().catch(() => {});
        }
    });
});

chrome.runtime.onStartup.addListener(() => {
    console.log("[Louders Official] Browser startup - verifying license...");
    LicenseManager.getLicenseState().then((state) => {
        if (state && state.isLicensed) {
            LicenseManager.verifyLicense().catch(() => {});
        }
    });
});

// Alarm listener for periodic license validation and heartbeat
chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'license_heartbeat') {
        LicenseManager.getLicenseState().then((state) => {
            if (state && state.isLicensed) {
                LicenseManager.sendHeartbeat().catch(() => {});
            }
        });
    }
});

// Message listener for popup & content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'LOUD_GET_LICENSE') {
        LicenseManager.getLicenseState().then((state) => {
            sendResponse({ success: true, state });
        });
        return true;
    }

    if (request.type === 'LOUD_ACTIVATE_LICENSE') {
        LicenseManager.activateLicense({
            licenseKey: request.licenseKey,
            customerEmail: request.customerEmail,
            serverUrl: request.serverUrl,
            productApiKey: request.productApiKey
        }).then((newState) => {
            sendResponse({ success: true, state: newState });
        }).catch((err) => {
            sendResponse({ success: false, error: err.message });
        });
        return true;
    }

    if (request.type === 'LOUD_VERIFY_LICENSE') {
        LicenseManager.verifyLicense().then((updatedState) => {
            sendResponse({ success: true, state: updatedState });
        }).catch((err) => {
            sendResponse({ success: false, error: err.message });
        });
        return true;
    }

    if (request.type === 'LOUD_DEACTIVATE_LICENSE') {
        LicenseManager.deactivateLicense().then((clearedState) => {
            sendResponse({ success: true, state: clearedState });
        }).catch((err) => {
            sendResponse({ success: false, error: err.message });
        });
        return true;
    }
});