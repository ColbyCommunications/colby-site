// BLOCK_NAME="Article Grid" TEMPLATE="Page with Sidebar" npm run test:blocks:local

const path = require('path');
const { spawnSync, execSync } = require('child_process');

function getArgs() {
    const args = {};
    process.argv.slice(2, process.argv.length).forEach((arg) => {
        // long arg
        if (arg.slice(0, 2) === '--') {
            const longArg = arg.split('=');
            const longArgFlag = longArg[0].slice(2, longArg[0].length);
            const longArgValue = longArg.length > 1 ? longArg[1] : true;
            args[longArgFlag] = longArgValue;
        }
        // flags
        else if (arg[0] === '-') {
            const flags = arg.slice(1, arg.length).split('');
            flags.forEach((flag) => {
                args[flag] = true;
            });
        }
    });
    return args;
}

// get args
const args = getArgs();

let spec = '*all*';
if (args.blocks) {
    spec = args.blocks;
}

let template = 'default';
if (args.template) {
    template = args.template;
}

console.log(`\nRunning spec: ${spec} with template: ${template}`);

let cyArgs = [];

if (process.env.NODE_ENV == 'local') {
    cyArgs = [
        'cypress',
        'run',
        '--headed',
        '--browser',
        'chrome',
        '--config-file',
        `${path.join('project', 'site_specific', 'config', 'cypress', 'cypress.config.blocks.js')}`,
    ];
} else {
    let site = execSync('~/.platformsh/bin/platform environment:info edge_hostname');
    let siteFull = `https://${site}`;

    cyArgs = [
        'cypress',
        'run',
        '--browser',
        'chrome',
        '--config-file',
        `${path.join('project', 'site_specific', 'config', 'cypress', 'cypress.config.js')}`,
    ];
}

if (spec && spec !== '*all*') {
    let blocks = spec.split(',');
    cyArgs.push('--spec');
    for (let i = 0; i < blocks.length; i++) {
        cyArgs.push(
            `project/site_specific/tests/cypress/block-testing/blocks/${blocks[i]}/${blocks[i]}.${template}.cy.js`
        );
    }
}

if (args.deletePage) {
    cyArgs = cyArgs.concat(['--env', 'DELETEPAGE=true']);
}

// Run Cypress
const result = spawnSync('npx', cyArgs, { stdio: 'inherit' });

if (result.error) {
    console.error('Failed to launch Cypress:', result.error);
    process.exit(1);
}

process.exit(result.status);
