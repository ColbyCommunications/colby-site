const fs = require('fs');
const path = require('path');
const _ = require('lodash');
const { parse } = require('csv-parse');

const walkSync = (dir, counts, rowData) => {
    const files = fs.readdirSync(dir);
    let thisImgCount = 0;
    let thisFileCount = 0;
    let thisSize = 0;
    files.forEach((file) => {
        let filepath = path.join(dir, file);
        const stats = fs.statSync(filepath);

        // if it's a directory, keep going
        if (stats.isDirectory()) {
            let newCounts = walkSync(filepath, counts, rowData);
            // console.log(newCounts);
            thisImgCount += newCounts.imgCount;
            thisFileCount += newCounts.fileCount;
            thisSize += newCounts.size;
        } else if (
            stats.isFile() &&
            !filepath.includes('.DS_Store') &&
            !filepath.includes('.html') &&
            !filepath.includes('.pdf') &&
            !filepath.includes('.doc') &&
            !filepath.includes('.docx') &&
            !filepath.includes('.ppt') &&
            !filepath.includes('.htaccess') &&
            !filepath.includes('gravity_forms') &&
            !filepath.includes('2024')
        ) {
            // remove first 3 chars "web" so it starts with "wp-content" instead
            filepath_processed = filepath.substring(3);

            // at this point:
            // this might be a preset size image
            // this might be an original

            const regex = /^([A-Za-z0-9_-]+)\-\d+x\d+\.(png|jpg|gif|jpeg|JPG|JPEG)$/;

            // lets split the whole file path
            let filenameParts = filepath_processed.split('/');

            // save the last item, ie just the filename
            let last = filenameParts[filenameParts.length - 1];

            const match = last.match(regex);

            // assume it's an original to start
            let presetSize = false;
            if (match) {
                // we found a preset size file
                presetSize = true;
            }

            // if the file is present in used_files, move on ..we're good
            if (
                _.find(rowData, function (o) {
                    return o.url === 'https://www.colby.edu' + filepath_processed;
                })
            ) {
                return;
            }

            // let's split the filename on '.'
            let filenameDissected = last.split('.');

            // if it's a preset size file and we can't find the original, delete it
            if (
                presetSize &&
                !_.find(rowData, function (o) {
                    // prettier-ignore
                    const regexOriginal = new RegExp(
                        `${match[1]}\\.${filenameDissected[1]}`
                    );
                    return regexOriginal.test(o.url);
                }) &&
                !_.find(rowData, function (o) {
                    // prettier-ignore
                    const regexOriginal = new RegExp(
                        `${match[1]}\\-\\d+x\\d+\\.${filenameDissected[1]}`
                    );
                    return regexOriginal.test(o.url);
                })
            ) {
                // if it's a preset size file and we can't find the original, delete it
                thisImgCount++;
            } else if (
                !presetSize &&
                !_.find(rowData, function (o) {
                    // prettier-ignore
                    const regexPreset = new RegExp(
                        `${filenameDissected[0]}\\-\\d+x\\d+\\.${filenameDissected[1]}`
                    );
                    return regexPreset.test(o.url);
                })
            ) {
                // if it's an original and we can't find a preset, delete it
                thisImgCount++;
                // console.log(fs.statSync(filepath).size);
                thisSize += stats.size;
                // console.log(size);
            }
        } else {
            thisFileCount++;
        }
        // console.log(imgCount);
    });

    return { imgCount: thisImgCount, fileCount: thisFileCount, size: thisSize };
};

(async () => {
    /*
        read in csv
    */
    let rowData = [];
    // let csvData = [];

    await fs
        .createReadStream('./used_images-3-4-24.csv')
        .pipe(parse({ delimiter: ',', from_line: 2, relax_quotes: true }))
        .on('data', async (row) => {
            // save locally
            rowData.push({
                url: row[0],
            });
        })
        .on('error', async (error) => {
            console.log(error.message);
        })
        .on('end', async () => {
            let counts = { imgCount: 0, fileCount: 0, size: 0 };
            console.log('Starting count...\n');
            let totals = walkSync('web/wp-content/uploads', counts, rowData);
            console.log(totals);
            console.log('Done.\n');
            console.log(`Files to be deleted: ${totals.imgCount}`);
            console.log(`Files to be saved: ${totals.fileCount}`);
            console.log(`GB saved: ${parseFloat((totals.size / (1024 * 1024 * 1024)).toFixed(3))}`);
            console.log(`Total files: ${totals.fileCount + totals.imgCount}`);
        });
})();
