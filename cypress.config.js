const { defineConfig } = require('cypress');
const fs = require('fs');

module.exports = defineConfig({
    defaultCommandTimeout: 10000,

    e2e: {
        setupNodeEvents(on, config) {
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
