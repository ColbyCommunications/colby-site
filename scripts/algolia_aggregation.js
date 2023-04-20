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
        attributesToRetrieve: [
          "post_title",
          "content",
          "permalink",
          "post_type",
          "external_url",
        ],
        batch: (batch) => {
          hits = hits.concat(batch);
        },
      });
    }

    for (let i = 0; i < hits.length; i++) {
      let result = {};
      let cleanedTitle = null;
      if (indicies[k].indexName === "Colby News") {
        if (hits[i].post_type === "external_post") {
          result = {
            post_title: hits[i].title,
            cleaned_title: cleanedTitle,
            content: hits[i].excerpt,
            permalink: hits[i].external_url,
            originIndexLabel: indicies[k].label,
            objectID: indicies[k].indexName + "-" + i,
          };
        }
      } else if (indicies[k].indexName === "Identity Site") {
        if (hits[i].title) {
          cleanedTitle = hits[i].title.replace(/<\/?[^>]+(>|$)/g, "");
        }
        result = {
          post_title: hits[i].title,
          cleaned_title: cleanedTitle,
          content: hits[i].excerpt,
          permalink: "https://identity.colby.edu" + hits[i].uri,
          originIndexLabel: indicies[k].label,
          objectID: indicies[k].indexName + "-" + i,
        };
      } else if (indicies[k].indexName === "prod_news_videos") {
        if (hits[i].title) {
          cleanedTitle = hits[i].title.replace(/<\/?[^>]+(>|$)/g, "");
        }
        result = {
          post_title: hits[i].title,
          cleaned_title: cleanedTitle,
          content: hits[i].description,
          permalink: "https://www.youtube.com/watch?v=" + hits[i].videoId,
          originIndexLabel: indicies[k].label,
          objectID: indicies[k].indexName + "-" + i,
        };
      } else {
        if (hits[i].post_title !== "_healthcheck") {
          let cleanedTitle = null;
          if (hits[i].post_title) {
            cleanedTitle = hits[i].post_title.replace(/<\/?[^>]+(>|$)/g, "");
          }
          result = {
            ..._omit(hits[i], ["objectID"]),
            cleaned_title: cleanedTitle,
            originIndexLabel: indicies[k].label,
            objectID: indicies[k].indexName + "-" + i,
          };
        }
      }

      finishedResults.push(result);
    }
  }

  await aggregatedIndex
    .saveObjects(finishedResults, { autoGenerateObjectIDIfNotExist: true })
    .wait();
}

main().catch(console.error);
