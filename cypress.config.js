const { defineConfig } = require('cypress');
const fs = require('fs');

module.exports = defineConfig({
    defaultCommandTimeout: 10000,

    e2e: {
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
