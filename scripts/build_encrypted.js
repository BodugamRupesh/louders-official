const fs = require('fs');
const path = require('path');
const JavaScriptObfuscator = require('javascript-obfuscator');

const REPO_ROOT = path.resolve(__dirname, '..');
const PARENT_DIR = path.resolve(REPO_ROOT, '..');

// Clean source code directory
const SRC_DIR = fs.existsSync(path.join(PARENT_DIR, 'Louders official'))
    ? path.join(PARENT_DIR, 'Louders official')
    : path.join(REPO_ROOT, 'extension');

const DIST_DIR = path.join(PARENT_DIR, 'Louders-Official-Encrypted');
const REPO_EXTENSION_DIR = path.join(REPO_ROOT, 'extension');

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

const MAXIMUM_ENCRYPTION_OPTIONS = {
    compact: true,
    controlFlowFlattening: true,
    controlFlowFlatteningThreshold: 1.0,
    deadCodeInjection: true,
    deadCodeInjectionThreshold: 0.35,
    identifierNamesGenerator: 'hexadecimal',
    numbersToExpressions: true,
    simplify: false,
    splitStrings: true,
    splitStringsChunkLength: 3,
    stringArray: true,
    stringArrayCallsTransform: true,
    stringArrayCallsTransformThreshold: 1.0,
    stringArrayEncoding: ['rc4'],
    stringArrayIndexShift: true,
    stringArrayRotate: true,
    stringArrayShuffle: true,
    stringArrayWrappersCount: 5,
    stringArrayWrappersChainedCalls: true,
    stringArrayWrappersParametersMaxCount: 4,
    stringArrayWrappersType: 'function',
    stringArrayThreshold: 1.0,
    transformObjectKeys: false,
    unicodeEscapeSequence: false,
    target: 'browser-no-eval'
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

if (fs.existsSync(REPO_EXTENSION_DIR)) {
    fs.rmSync(REPO_EXTENSION_DIR, { recursive: true, force: true });
}
fs.mkdirSync(REPO_EXTENSION_DIR, { recursive: true });
copyRecursiveSync(DIST_DIR, REPO_EXTENSION_DIR);
console.log(`[REPO] Updated repo extension at: ${REPO_EXTENSION_DIR}`);

console.log('----------------------------------------------------');
console.log('✓ Maximum Hardened Build Complete!');
console.log('====================================================');
