const algoliasearch = require("algoliasearch");
const _omit = require("lodash/omit");

function getArgs() {
	const args = {};
	process.argv.slice(2, process.argv.length).forEach((arg) => {
		// long arg
		if (arg.slice(0, 2) === "--") {
			const longArg = arg.split("=");
			const longArgFlag = longArg[0].slice(2, longArg[0].length);
			const longArgValue = longArg.length > 1 ? longArg[1] : true;
			args[longArgFlag] = longArgValue;
		}
		// flags
		else if (arg[0] === "-") {
			const flags = arg.slice(1, arg.length).split("");
			flags.forEach((flag) => {
				args[flag] = true;
			});
		}
	});
	return args;
}

// get args
const args = getArgs();

// initialize algolia client
const client = algoliasearch(args.algoliaAppId, args.algoliaApiKey);
const aggregatedIndexName = "prod_colbyedu_aggregated";

async function main() {
	let aggregatedIndex = client.initIndex(aggregatedIndexName);

	// clear aggregated index
	await aggregatedIndex.clearObjects().wait();

	let finishedResults = [];

	let indicies = JSON.parse(args.algoliaIndicies).indicies;

	for (var k = 0; k < indicies.length; k++) {
		let index = client.initIndex(indicies[k].indexName);
		let hits = [];

		if (indicies[k].indexName === "Identity Site") {
			await index.browseObjects({
				query: "",
				attributesToRetrieve: ["title", "excerpt", "uri"],
				batch: (batch) => {
					hits = hits.concat(batch);
				},
			});
		} else if (indicies[k].indexName === "prod_news_videos") {
			await index.browseObjects({
				query: "",
				attributesToRetrieve: ["title", "description", "videoId"],
				batch: (batch) => {
					hits = hits.concat(batch);
				},
			});
		} else {
			await index.browseObjects({
				query: "",
				attributesToRetrieve: ["post_title", "content", "permalink"],
				batch: (batch) => {
					hits = hits.concat(batch);
				},
			});
		}

		for (let i = 0; i < hits.length; i++) {
			let result = {};
			if (indicies[k].indexName === "Identity Site") {
				result = {
					post_title: hits[i].title,
					content: hits[i].excerpt,
					permalink: "https://identity.colby.edu" + hits[i].uri,
					originIndexLabel: indicies[k].label,
					objectID: indicies[k].indexName + "-" + i,
				};
			} else if (indicies[k].indexName === "prod_news_videos") {
				result = {
					post_title: hits[i].title,
					content: hits[i].description,
					permalink: "https://www.youtube.com/watch?v=" + hits[i].videoId,
					originIndexLabel: indicies[k].label,
					objectID: indicies[k].indexName + "-" + i,
				};
			} else {
				result = {
					..._omit(hits[i], ["objectID"]),
					originIndexLabel: indicies[k].label,
					objectID: indicies[k].indexName + "-" + i,
				};
			}

			finishedResults.push(result);
		}
	}

	await aggregatedIndex.saveObjects(finishedResults).wait();
}

main().catch(console.error);
