EDGE_HOSTNAME=$(~/.upsun/bin/upsun domains --format=plain --no-header --columns=name )
JQ="https://rf26.colby.edu"
echo $(cat .github/sitemap.json | jq -r --arg JQ "$JQ" '.urls += [$JQ]') > .github/sitemap.json
cat .github/sitemap.json
