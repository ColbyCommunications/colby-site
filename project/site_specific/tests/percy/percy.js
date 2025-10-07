const puppeteer = require('puppeteer');
const percySnapshot = require('@percy/puppeteer');
const scrollToBottom = require('scroll-to-bottomjs');

(async () => {
    const browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    const scrollOptions = {
        frequency: 100,
        timing: 200, // milliseconds
    };

    // Home Page
    const testPage = await browser.newPage();
    await testPage.goto('https://www.dev-54ta5gq-ouiqvb5juucvu.us-4.platformsh.site/');
    await new Promise(function (resolve) {
        setTimeout(async function () {
            await testPage.evaluate(scrollToBottom, scrollOptions);

            await percySnapshot(testPage, 'Snapshot of home page', {
                percyCSS: `.carousel { display:none; } .article-grid { display: none; } .featured-post { display: none; }`,
            });
            resolve();
        }, 3000);
    });

    // Academics
    const testPage2 = await browser.newPage();
    await testPage2.goto('https://www.dev-54ta5gq-ouiqvb5juucvu.us-4.platformsh.site/academics/');
    await new Promise(function (resolve) {
        setTimeout(async function () {
            await testPage2.evaluate(scrollToBottom, scrollOptions);

            await percySnapshot(testPage2, 'Snapshot of academics', {
                percyCSS: `.article-section { display:none; }`,
            });
            resolve();
        }, 3000);
    });

    // People
    const testPage3 = await browser.newPage();
    await testPage3.goto('https://www.dev-54ta5gq-ouiqvb5juucvu.us-4.platformsh.site/people/');
    await new Promise(function (resolve) {
        setTimeout(async function () {
            await testPage3.evaluate(scrollToBottom, scrollOptions);

            await percySnapshot(testPage3, 'Snapshot of people page', {
                percyCSS: `.context-article-grid  { display:none; } `,
            });
            resolve();
        }, 3000);
    });

    // Offices
    const testPage4 = await browser.newPage();
    await testPage4.goto(
        'https://www.dev-54ta5gq-ouiqvb5juucvu.us-4.platformsh.site/people/offices-directory/'
    );
    await new Promise(function (resolve) {
        setTimeout(async function () {
            await testPage4.evaluate(scrollToBottom, scrollOptions);

            await percySnapshot(testPage4, 'Snapshot of offices page', {
                percyCSS: `.relatedSection { display:none; } .highlightsSection { display: none; } .read-time { display: none; } .wp-block-embed-youtube { .display: none; }`,
            });
            resolve();
        }, 3000);
    });
    
    // Post 1
    const testPost = await browser.newPage();
    await testPost.goto(
        'https://www.dev-54ta5gq-ouiqvb5juucvu.us-4.platformsh.site/halloran-lab/news/jonathan-godbout-08-entrepreneur-in-residence-eir/'
    );
    await new Promise(function (resolve) {
        setTimeout(async function () {
            await testPage4.evaluate(scrollToBottom, scrollOptions);

            await percySnapshot(testPage4, 'Snapshot of offices page', {
                percyCSS: `.relatedSection { display:none; } .highlightsSection { display: none; } .read-time { display: none; } .wp-block-embed-youtube { .display: none; }`,
            });
            resolve();
        }, 3000);
    });

    await browser.close();
})();
