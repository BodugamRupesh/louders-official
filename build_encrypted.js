const fs = require('fs');
const path = require('path');
const JavaScriptObfuscator = require('javascript-obfuscator');

const SRC_DIR = path.join(__dirname, 'Louders official');
const DIST_DIR = path.join(__dirname, 'Louders-Official-Encrypted');
const REPO_EXTENSION_DIR = path.join(__dirname, 'louders-official', 'extension');

// Clean and create dist directory
if (fs.existsSync(DIST_DIR)) {
    fs.rmSync(DIST_DIR, { recursive: true, force: true });
}
fs.mkdirSync(DIST_DIR, { recursive: true });

console.log('====================================================');
console.log('    LOUDERS MAXIMUM HARDENED ENCRYPTION PIPELINE    ');
console.log('====================================================');
console.log(`Source:          ${SRC_DIR}`);
console.log(`Protected Out:   ${DIST_DIR}`);
console.log(`Repo Extension:  ${REPO_EXTENSION_DIR}`);
console.log('----------------------------------------------------');

// Hardened Encryption Options tuned for 100% Android Mobile (Kiwi / Mods) & Desktop Chrome compatibility
const MAXIMUM_ENCRYPTION_OPTIONS = {
    compact: true,
    controlFlowFlattening: true,
    controlFlowFlatteningThreshold: 0.75, // Deep state-machine control flow scrambling
    deadCodeInjection: false, // Disabled to eliminate mobile CPU/memory freeze
    identifierNamesGenerator: 'hexadecimal',
    numbersToExpressions: false, // Disabled to keep 44.1kHz audio loop stutter-free on mobile
    simplify: true,
    splitStrings: false, // Prevents GC thrashing on mobile V8
    stringArray: true,
    stringArrayCallsTransform: true,
    stringArrayCallsTransformThreshold: 0.8,
    stringArrayEncoding: ['base64'], // Instantaneous decoding on mobile startup
    stringArrayIndexShift: true,
    stringArrayRotate: true,
    stringArrayShuffle: true,
    stringArrayWrappersCount: 2, // 2 wrappers (prevents call-stack exhaustion on mobile V8)
    stringArrayWrappersChainedCalls: true,
    stringArrayWrappersParametersMaxCount: 2,
    stringArrayWrappersType: 'function',
    stringArrayThreshold: 0.85,
    transformObjectKeys: false, // Preserves standard WebAudio/DOM interfaces
    unicodeEscapeSequence: false,
    reservedNames: [
        '^LicenseManager$',
        '^LOUD_LICENSE_CONFIG$',
        '^originalGetUserMedia$',
        '^currentSettings$',
        '^currentSettings1$',
        '^currentSettings2$',
        '^louders1Enabled$',
        '^louders2Enabled$',
        '^activeAudioNodes$',
        '^activeChains$',
        '^processedTracks$',
        '^hookGetUserMedia$',
        '^syncSettingsToPage$',
        '^syncAllSettingsToPage$',
        '^injectScript$',
        '^buildUnifiedPipeline$',
        '^processUnifiedStream$',
        '^applyModeRouting$',
        '^chrome$'
    ],
    target: 'browser-no-eval' // Strictly compliant with Chrome Manifest V3 CSP
};

function copyRecursiveSync(src, dest) {
    const exists = fs.existsSync(src);
    const stats = exists && fs.statSync(src);
    const isDirectory = exists && stats.isDirectory();
    if (isDirectory) {
        if (!fs.existsSync(dest)) fs.mkdirSync(dest, { recursive: true });
        fs.readdirSync(src).forEach((childItemName) => {
            copyRecursiveSync(path.join(src, childItemName), path.join(dest, childItemName));
        });
    } else {
        fs.copyFileSync(src, dest);
    }
}

// 1. Process and encrypt all files into DIST_DIR
const files = fs.readdirSync(SRC_DIR);

for (const file of files) {
    const srcPath = path.join(SRC_DIR, file);
    const destPath = path.join(DIST_DIR, file);
    const stat = fs.statSync(srcPath);

    if (stat.isDirectory()) {
        console.log(`[DIR]  Copying folder: ${file}/`);
        copyRecursiveSync(srcPath, destPath);
        continue;
    }

    if (file.endsWith('.js')) {
        console.log(`[LOCK] Hardening & Encrypting: ${file}...`);
        const originalCode = fs.readFileSync(srcPath, 'utf8');
        try {
            const obfuscationResult = JavaScriptObfuscator.obfuscate(originalCode, MAXIMUM_ENCRYPTION_OPTIONS);
            const encryptedCode = obfuscationResult.getObfuscatedCode();
            fs.writeFileSync(destPath, encryptedCode, 'utf8');
            console.log(`  ✓ ${file} fully encrypted (${(encryptedCode.length / 1024).toFixed(1)} KB)`);
        } catch (err) {
            console.error(`  ✗ Error encrypting ${file}:`, err.message);
            process.exit(1);
        }
    } else {
        console.log(`[COPY] Copying asset:  ${file}`);
        fs.copyFileSync(srcPath, destPath);
    }
}

// 2. Also copy the fully encrypted files to the git repository's extension folder
if (fs.existsSync(REPO_EXTENSION_DIR)) {
    fs.rmSync(REPO_EXTENSION_DIR, { recursive: true, force: true });
}
fs.mkdirSync(REPO_EXTENSION_DIR, { recursive: true });
copyRecursiveSync(DIST_DIR, REPO_EXTENSION_DIR);
console.log(`[REPO] Copied encrypted extension to: ${REPO_EXTENSION_DIR}`);

// 3. Create POSIX Standard ZIP (100% Compatible with Kiwi Browser, Android, and Desktop)
const ZIP_PATH = path.join(__dirname, 'Louders-Official-Encrypted.zip');
console.log('[ZIP]  Creating cross-platform POSIX ZIP package...');
require('child_process').execSync(`python zip_helper.py "${DIST_DIR}" "${ZIP_PATH}"`);
console.log(`  ✓ ZIP ready: ${ZIP_PATH}`);

// 4. Create Direct-Import CRX File
const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PEM_KEY = path.join(__dirname, 'Louders-Official-Encrypted.pem');
if (fs.existsSync(CHROME_PATH)) {
    console.log('[CRX]  Packing direct-import .crx package via Chrome...');
    try {
        let cmd = `Start-Process -FilePath '${CHROME_PATH}' -ArgumentList '--pack-extension=\"${DIST_DIR}\"' -Wait`;
        if (fs.existsSync(PEM_KEY)) {
            cmd = `Start-Process -FilePath '${CHROME_PATH}' -ArgumentList '--pack-extension=\"${DIST_DIR}\"','--pack-extension-key=\"${PEM_KEY}\"' -Wait`;
        }
        require('child_process').execSync(`powershell -Command "${cmd}"`);
        console.log(`  ✓ CRX ready: ${path.join(__dirname, 'Louders-Official-Encrypted.crx')}`);
    } catch(e) {
        console.warn('  ! CRX packing note:', e.message);
    }
}

console.log('----------------------------------------------------');
console.log('✓ Maximum Hardened Build & Distribution Complete!');
console.log('  1. Direct-Import CRX:  Louders-Official-Encrypted.crx');
console.log('  2. Android ZIP File:   Louders-Official-Encrypted.zip');
console.log('  3. Unpacked Folder:    Louders-Official-Encrypted');
console.log('  4. Repo Extension:     louders-official/extension');
console.log('====================================================');
