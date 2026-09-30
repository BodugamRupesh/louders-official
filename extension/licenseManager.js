/**
 * Louders Official - Extension License Manager
 * Connects browser extension to LOUD Platform License Server
 * Handles activation, verification, heartbeat, and deactivation.
 */

const LOUD_LICENSE_CONFIG = {
    DEFAULT_SERVER_URL: 'https://louders-official.onrender.com',
    DEFAULT_PRODUCT_API_KEY: 'lp_AqzVY9OZc1ZyVSYgfc-J6XLxff9lejdLtzClROBrUgU',
    EXTENSION_VERSION: '1.0.0',
    STORAGE_KEY: 'louders_license_state',
    DEVICE_ID_KEY: 'louders_device_uuid'
};

const LicenseManager = {
    config: LOUD_LICENSE_CONFIG,

    /**
     * Get or generate a persistent device UUID
     */
    async getDeviceUuid() {
        return new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.get([this.config.DEVICE_ID_KEY], (res) => {
                    if (res && res[this.config.DEVICE_ID_KEY]) {
                        resolve(res[this.config.DEVICE_ID_KEY]);
                    } else {
                        const newUuid = this.generateUuid();
                        chrome.storage.local.set({ [this.config.DEVICE_ID_KEY]: newUuid }, () => {
                            resolve(newUuid);
                        });
                    }
                });
            } else {
                let uuid = localStorage.getItem(this.config.DEVICE_ID_KEY);
                if (!uuid) {
                    uuid = this.generateUuid();
                    localStorage.setItem(this.config.DEVICE_ID_KEY, uuid);
                }
                resolve(uuid);
            }
        });
    },

    /**
     * Helper to generate UUIDv4
     */
    generateUuid() {
        if (typeof crypto !== 'undefined' && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    },

    /**
     * Detect browser type allowed by backend schema:
     * Chrome, Edge, Firefox, Brave, Opera
     */
    detectBrowser() {
        const ua = navigator.userAgent;
        if (/Edg\//i.test(ua)) return 'Edge';
        if (/OPR\//i.test(ua) || /Opera/i.test(ua)) return 'Opera';
        if (navigator.brave && typeof navigator.brave.isBrave === 'function') return 'Brave';
        if (/Firefox\//i.test(ua)) return 'Firefox';
        return 'Chrome';
    },

    /**
     * Detect operating system
     */
    detectOS() {
        const ua = navigator.userAgent;
        if (/Windows/i.test(ua)) return 'Windows';
        if (/Macintosh|Mac OS X/i.test(ua)) return 'macOS';
        if (/Linux/i.test(ua)) return 'Linux';
        if (/Android/i.test(ua)) return 'Android';
        return 'Unknown';
    },

    /**
     * Retrieve current cached license state from storage
     */
    async getLicenseState() {
        return new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.get([this.config.STORAGE_KEY], (res) => {
                    const state = res?.[this.config.STORAGE_KEY] || {
                        isLicensed: false,
                        status: 'unlicensed',
                        licenseKey: '',
                        customerEmail: '',
                        serverUrl: this.config.DEFAULT_SERVER_URL,
                        productApiKey: this.config.DEFAULT_PRODUCT_API_KEY
                    };
                    resolve(state);
                });
            } else {
                try {
                    const raw = localStorage.getItem(this.config.STORAGE_KEY);
                    resolve(raw ? JSON.parse(raw) : { isLicensed: false, status: 'unlicensed' });
                } catch {
                    resolve({ isLicensed: false, status: 'unlicensed' });
                }
            }
        });
    },

    /**
     * Save license state to storage and sync tabs
     */
    async setLicenseState(state) {
        return new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.set({ [this.config.STORAGE_KEY]: state }, () => {
                    this.notifyTabsOfLicenseUpdate(state.isLicensed);
                    resolve(state);
                });
            } else {
                localStorage.setItem(this.config.STORAGE_KEY, JSON.stringify(state));
                resolve(state);
            }
        });
    },

    /**
     * Notify tabs running inject/content script of license changes
     */
    notifyTabsOfLicenseUpdate(isLicensed) {
        if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.query) {
            chrome.tabs.query({}, (tabs) => {
                (tabs || []).forEach((t) => {
                    if (t.id) {
                        chrome.tabs.sendMessage(t.id, {
                            type: 'MIC_ENHANCER_LICENSE_UPDATE',
                            isLicensed: !!isLicensed
                        }).catch(() => {});
                    }
                });
            });
        }
    },

    /**
     * Activate a license key with customer email
     */
    async activateLicense({ licenseKey, customerEmail, serverUrl, productApiKey }) {
        if (!licenseKey || !licenseKey.trim()) {
            throw new Error('License key is required.');
        }
        if (!customerEmail || !customerEmail.trim()) {
            throw new Error('Customer email is required for activation.');
        }

        const cleanLicenseKey = licenseKey.trim().toUpperCase();
        const cleanEmail = customerEmail.trim().toLowerCase();
        const baseUrl = (serverUrl || this.config.DEFAULT_SERVER_URL).replace(/\/+$/, '');
        const apiKey = productApiKey || this.config.DEFAULT_PRODUCT_API_KEY;
        const deviceUuid = await this.getDeviceUuid();
        const browser = this.detectBrowser();
        const os = this.detectOS();

        const endpoint = `${baseUrl}/api/v1/extensions/activate`;
        const payload = {
            product_api_key: apiKey,
            license_key: cleanLicenseKey,
            customer_email: cleanEmail,
            device_uuid: deviceUuid,
            browser: browser,
            operating_system: os,
            extension_version: this.config.EXTENSION_VERSION,
            device_fingerprint: `${browser}-${os}-${deviceUuid}`
        };

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(payload)
        }).catch((err) => {
            throw new Error(`Cannot connect to license server at ${baseUrl}. Ensure the server is online. (${err.message})`);
        });

        const data = await response.json().catch(() => null);

        if (!response.ok) {
            let errorMsg = data?.message || data?.detail || `Server error (${response.status})`;
            if (Array.isArray(data?.detail)) {
                errorMsg = data.detail.map(d => d.msg || d.detail || JSON.stringify(d)).join(', ');
            } else if (typeof errorMsg !== 'string') {
                errorMsg = JSON.stringify(errorMsg);
            }
            throw new Error(errorMsg);
        }

        const newState = {
            isLicensed: true,
            status: 'active',
            licenseKey: cleanLicenseKey,
            customerEmail: cleanEmail,
            serverUrl: baseUrl,
            productApiKey: apiKey,
            extensionToken: data.extension_token,
            expiresAt: data.expires_at,
            activatedAt: data.activated_at,
            deviceId: data.device_id,
            deviceUuid: deviceUuid,
            maxDevices: data.max_devices,
            lastVerified: new Date().toISOString()
        };

        await this.setLicenseState(newState);
        return newState;
    },

    /**
     * Verify license is still active and device is registered
     */
    async verifyLicense() {
        const state = await this.getLicenseState();
        if (!state.isLicensed || !state.licenseKey) {
            return { isLicensed: false, status: 'unlicensed' };
        }

        const baseUrl = (state.serverUrl || this.config.DEFAULT_SERVER_URL).replace(/\/+$/, '');
        const apiKey = state.productApiKey || this.config.DEFAULT_PRODUCT_API_KEY;
        const deviceUuid = state.deviceUuid || await this.getDeviceUuid();
        const browser = this.detectBrowser();

        const endpoint = `${baseUrl}/api/v1/extensions/verify`;
        const payload = {
            product_api_key: apiKey,
            license_key: state.licenseKey,
            device_uuid: deviceUuid,
            browser: browser,
            extension_token: state.extensionToken || undefined
        };

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json().catch(() => null);

            if (!response.ok) {
                // Verification rejected by server
                const updatedState = {
                    ...state,
                    isLicensed: false,
                    status: data?.message || data?.detail || 'revoked_or_invalid',
                    lastVerified: new Date().toISOString()
                };
                await this.setLicenseState(updatedState);
                return updatedState;
            }

            const isStillActive = data.status === 'active' && data.activated;
            const updatedState = {
                ...state,
                isLicensed: isStillActive,
                status: data.status,
                expiresAt: data.expires_at,
                daysRemaining: data.days_remaining,
                activatedDevices: data.activated_devices,
                maxDevices: data.max_devices,
                lastVerified: new Date().toISOString()
            };

            await this.setLicenseState(updatedState);
            return updatedState;
        } catch (err) {
            console.warn('[LOUD License] Could not verify with server:', err);
            // In case of transient network failure, don't immediately lock out if verified recently
            return state;
        }
    },

    /**
     * Send heartbeat to keep device session active
     */
    async sendHeartbeat() {
        const state = await this.getLicenseState();
        if (!state.isLicensed || !state.licenseKey) {
            return null;
        }

        const baseUrl = (state.serverUrl || this.config.DEFAULT_SERVER_URL).replace(/\/+$/, '');
        const apiKey = state.productApiKey || this.config.DEFAULT_PRODUCT_API_KEY;
        const deviceUuid = state.deviceUuid || await this.getDeviceUuid();
        const browser = this.detectBrowser();
        const os = this.detectOS();

        const endpoint = `${baseUrl}/api/v1/extensions/heartbeat`;
        const payload = {
            product_api_key: apiKey,
            license_key: state.licenseKey,
            device_uuid: deviceUuid,
            browser: browser,
            operating_system: os,
            extension_version: this.config.EXTENSION_VERSION,
            extension_token: state.extensionToken || undefined
        };

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                const data = await response.json();
                state.daysRemaining = data.days_remaining;
                state.lastVerified = data.last_checked_at || new Date().toISOString();
                await this.setLicenseState(state);
                return data;
            }
        } catch (err) {
            console.warn('[LOUD License] Heartbeat failed:', err);
        }
        return null;
    },

    /**
     * Deactivate current device session and remove from license
     */
    async deactivateLicense() {
        const state = await this.getLicenseState();
        const baseUrl = (state.serverUrl || this.config.DEFAULT_SERVER_URL).replace(/\/+$/, '');
        const apiKey = state.productApiKey || this.config.DEFAULT_PRODUCT_API_KEY;
        const deviceUuid = state.deviceUuid || await this.getDeviceUuid();

        if (state.licenseKey) {
            try {
                const endpoint = `${baseUrl}/api/v1/extensions/deactivate`;
                await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        product_api_key: apiKey,
                        license_key: state.licenseKey,
                        device_uuid: deviceUuid
                    })
                });
            } catch (err) {
                console.warn('[LOUD License] Server deactivate request error:', err);
            }
        }

        const clearedState = {
            isLicensed: false,
            status: 'unlicensed',
            licenseKey: '',
            customerEmail: '',
            serverUrl: state.serverUrl || this.config.DEFAULT_SERVER_URL,
            productApiKey: state.productApiKey || this.config.DEFAULT_PRODUCT_API_KEY
        };

        await this.setLicenseState(clearedState);
        return clearedState;
    }
};

if (typeof module !== 'undefined' && module.exports) {
    module.exports = LicenseManager;
}
