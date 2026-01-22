const { defineConfig } = require('cypress');

const { execSync } = require('child_process');
let site = execSync('~/.platformsh/bin/platform environment:info edge_hostname');
let siteFull = `https://www.${site}`;

// if (!process.env.PLATFORM_RELATIONSHIPS && process.env.GITHUB_ACTIONS !== 'true') {
//     siteFull = 'https://colby.lndo.site';
// }

module.exports = defineConfig({
    defaultCommandTimeout: 10000,
    e2e: {
        baseUrl: siteFull,
        supportFile: 'project/site_specific/config/cypress/support/e2e.js',
        specPattern: [
            'project/site_specific/tests/cypress/**/*',
            'project/global/tests/cypress/**/*',
        ],
    },
});
