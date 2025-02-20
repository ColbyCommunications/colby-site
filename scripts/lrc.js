const superagent = require('superagent');
const xml2js = require('xml2js');
const cypress = require('cypress');
const fs = require('fs');

const url = 'https://web.colby.edu/lrctestsite/wp-sitemap-posts-page-1.xml';

(async () => {
    try {
        const res = await superagent.get(url);
        const parser = new xml2js.Parser();
        parser.parseString(res.body, async (err, result) => {
            if (err) {
                console.error('Error parsing XML:', err);
                return;
            }

            // Assuming the structure of the XML has a root element (e.g., 'urlset')
            // and entries within that root element as an array (e.g., 'url')

            if (result && result.urlset && Array.isArray(result.urlset.url)) {
                const entries = result.urlset.url;

                const resultArr = [];
                for (let i = 0; i < entries.length; i++) {
                    await cypress
                        .run({
                            browser: 'chrome',
                            spec: './cypress/e2e/lrc/lrc.cy.js',
                            env: { url: entries[i].loc[0] },
                            reporter: 'json',
                        })
                        .then((results) => {
                            resultArr.push(results);
                        });
                }

                const outputFile = './cypress-results.json'; // Change file name if needed
                fs.writeFileSync(outputFile, JSON.stringify(resultsArr, null, 2), 'utf-8');
                console.log(`Test results saved to ${outputFile}`);
            } else {
                console.error('Unexpected XML structure.  Check the structure of the XML file.');
            }
        });
    } catch (err) {
        console.error(err);
    }
})();
