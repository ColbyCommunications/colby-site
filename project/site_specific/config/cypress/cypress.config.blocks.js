const { defineConfig } = require('cypress');
const fs = require('fs');

const { execSync } = require('child_process');
let site = execSync('~/.platformsh/bin/platform environment:info edge_hostname');
let siteFull = `https://www.${site}`;

if (!process.env.PLATFORM_RELATIONSHIPS) {
    siteFull = 'https://colby.lndo.site';
}

module.exports = defineConfig({
    defaultCommandTimeout: 10000,
    e2e: {
        supportFile: 'project/site_specific/config/cypress/support/e2e.js',
        specPattern: ['project/site_specific/tests/cypress/**/*.cy.js'],
        baseUrl: siteFull,
        setupNodeEvents(on, config) {
            // Map shell environment variables into Cypress.env
            if (process.env.BLOCK_NAME) config.env.BLOCK_NAME = process.env.BLOCK_NAME;
            if (process.env.TEMPLATE) config.env.TEMPLATE = process.env.TEMPLATE;

            // Registering the saveShortcodeResults task
            on('task', {
                saveShortcodeResults(pagesWithShortcodes) {
                    const shortcodesFile = './shortcodes-found.txt';
                    const shortcodesContent =
                        pagesWithShortcodes.join('\n') +
                        `\nTotal Pages with Shortcodes: ${pagesWithShortcodes.length}`;

                    fs.writeFileSync(shortcodesFile, shortcodesContent, 'utf-8');
                    console.log(`Shortcode results saved to ${shortcodesFile}`);

                    return null;
                },
            });

            return config;
        },
    },
});
