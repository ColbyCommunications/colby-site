const puppeteer = require('puppeteer');
const percySnapshot = require('@percy/puppeteer');
const scrollToBottom = require('scroll-to-bottomjs');
const { execSync } = require('child_process');

let site = execSync('upsun environment:info edge_hostname');
let siteFull = `https://www.${site}`;

(async () => {
    const browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    const scrollOptions = { frequency: 100, timing: 200 };
    const testPage = await browser.newPage();

    // 2. Navigate to the test page (now logged in)
    await testPage.setUserAgent('colby-github');

    // 1. Run the Login Routine
    // This sets the cookies in the local Puppeteer browser
    await loginToWordPress(testPage, siteFull);

    await testPage.goto(`${siteFull}/test-page`);

    // 3. Capture Cookies to share with Percy
    // This ensures Percy's asset discovery browser is ALSO logged in
    const sessionCookies = await testPage.cookies();

    await new Promise(function (resolve) {
        setTimeout(async function () {
            await testPage.evaluate(scrollToBottom, scrollOptions);

            // 4. Take Snapshot with Cookie Injection
            await percySnapshot(testPage, 'Snapshot of test page', {
                discovery: {
                    cookies: sessionCookies,
                },
            });
            resolve();
        }, 3000);
    });

    await browser.close();
})();
