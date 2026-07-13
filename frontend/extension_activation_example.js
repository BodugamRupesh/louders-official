/**
 * Example browser extension activation helper for LOUD License Server.
 *
 * This sample shows how to send the required payload fields, including
 * `customer_email`, when activating an extension license.
 */

const LICENSE_SERVER_BASE_URL = 'http://127.0.0.1:8000';

export async function activateExtensionLicense({
    productApiKey,
    licenseKey,
    deviceUuid,
    browser,
    operatingSystem,
    extensionVersion,
    customerEmail,
    deviceFingerprint,
}) {
    if (!customerEmail) {
        throw new Error('customer_email is required for extension activation');
    }

    const response = await fetch(`${LICENSE_SERVER_BASE_URL}/api/v1/extensions/activate`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            product_api_key: productApiKey,
            license_key: licenseKey,
            device_uuid: deviceUuid,
            browser,
            operating_system: operatingSystem,
            extension_version: extensionVersion,
            customer_email: customerEmail,
            device_fingerprint: deviceFingerprint,
        }),
    });

    if (!response.ok) {
        const payload = await response.json().catch(() => null);
        const message = payload?.detail || payload?.message || response.statusText;
        throw new Error(`Activation failed: ${message}`);
    }

    return response.json();
}
