const superagent = require('superagent');
const xml2js = require('xml2js');
const cypress = require('cypress');
const fs = require('fs');

const url = 'https://web.colby.edu/lrclibrary/wp-sitemap-posts-page-1.xml';

(async () => {
    try {
        const res = await superagent.get(url);
        const parser = new xml2js.Parser();
        parser.parseString(res.body, async (err, result) => {
            if (err) {
                console.error('Error parsing XML:', err);
                return;
            }

            if (result && result.urlset && Array.isArray(result.urlset.url)) {
                const entries = result.urlset.url;
                const resultArr = [];
                let failedUrls = []; // Failed URLs for the accordion test
                let failureCount = 0; // Counter for failures
                let shortcodeUrls = []; // Pages with shortcodes

                for (let i = 0; i < entries.length; i++) {
                    const testUrl = entries[i].loc[0];

                    await cypress
                        .run({
                            browser: 'chrome',
                            spec: './cypress/e2e/lrc/lrc.cy.js',
                            env: { url: testUrl },
                            reporter: 'json',
                        })
                        .then((results) => {
                            resultArr.push(results);

                            // If there are failed tests, track the URL
                            if (results.totalFailed > 0) {
                                failedUrls.push(testUrl);
                                failureCount++;
                            }

                            // Collect shortcode results from Cypress task
                            if (results.runs) {
                                results.runs.forEach((run) => {
                                    run.tests.forEach((test) => {
                                        if (
                                            test.title === 'checks for WordPress shortcodes' &&
                                            test.state === 'passed'
                                        ) {
                                            shortcodeUrls.push(testUrl);
                                        }
                                    });
                                });
                            }
                        });
                }

                // Write failed URLs and total failure count to a text file
                const failedTestsFile = './failed-tests.txt';
                const failedTestsContent =
                    failedUrls.join('\n') + `\nTotal Failures: ${failureCount}`;
                fs.writeFileSync(failedTestsFile, failedTestsContent, 'utf-8');
                console.log(`Failed test results saved to ${failedTestsFile}`);

                // Write shortcode URLs to a separate file
                const shortcodesFile = './shortcodes-found.txt';
                const shortcodesContent =
                    shortcodeUrls.join('\n') +
                    `\nTotal Pages with Shortcodes: ${shortcodeUrls.length}`;
                fs.writeFileSync(shortcodesFile, shortcodesContent, 'utf-8');
                console.log(`Shortcode results saved to ${shortcodesFile}`);
            } else {
                console.error('Unexpected XML structure. Check the structure of the XML file.');
            }
        });
    } catch (err) {
        console.error(err);
    }
})();
