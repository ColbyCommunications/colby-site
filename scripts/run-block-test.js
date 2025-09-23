// BLOCK_NAME="Article Grid" TEMPLATE="Page with Sidebar" npm run test:blocks:local

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const blockName = process.env.BLOCK_NAME;
const template = process.env.TEMPLATE;

if (!blockName || !template) {
    console.error(
        'Missing env vars. Usage: BLOCK_NAME="Article Grid" TEMPLATE="Page with Sidebar" npm run test:blocks'
    );
    process.exit(1);
}

// Path to Cypress blocks folder
const blocksDir = path.join('cypress', 'e2e', 'block-testing', 'blocks');

// Slug helper: e.g. "Article Grid" -> "article-grid"
function slugify(s) {
    return String(s)
        .trim()
        .toLowerCase()
        .replace(/\s+/g, '-')
        .replace(/[^\w-]/g, '');
}

const blockSlug = slugify(blockName);

// The spec file now lives inside the block's folder
const blockSpecPath = path.join(blocksDir, blockSlug, `${blockSlug}.cy.js`);

if (!fs.existsSync(blockSpecPath)) {
    console.error(`No block found with the name of '${blockName}'`);
    process.exit(2);
}

// Resolve absolute path for Cypress
const specFile = path.resolve(blockSpecPath);

console.log(`\nRunning spec: ${specFile}`);
console.log(`BLOCK_NAME=${blockName}, TEMPLATE=${template}\n`);

let args = [];

if (process.env.NODE_ENV == 'local') {
    args = [
        'cypress',
        'run',
        '--headed',
        '--browser',
        'chrome',
        '--spec',
        specFile,
        '--env',
        `BLOCK_NAME=${blockName},TEMPLATE=${template}`,
    ];
} else {
    args = [
        'cypress',
        'run',
        '--browser',
        'chrome',
        '--spec',
        specFile,
        '--env',
        `BLOCK_NAME=${blockName},TEMPLATE=${template}`,
    ];
}

// Run Cypress
const result = spawnSync('npx', args, { stdio: 'inherit' });

if (result.error) {
    console.error('Failed to launch Cypress:', result.error);
    process.exit(1);
}

process.exit(result.status);
