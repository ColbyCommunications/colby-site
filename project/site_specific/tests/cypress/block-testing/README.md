# Colby Block Testing

## Exposed Commands and Examples

`npm run test:blocks:local` - tests blocks on local environment  
`npm run test:blocks:prod` - test blocks in CI/CD

You run these from the site root as normal.

### Local Examples

`npm run test:blocks:local -- --blocks=article-grid --template=page-with-sidebar` - tests only article grid in page-with-sidebar template  
`npm run test:blocks:local -- --blocks=article-grid,table --template=page-with-sidebar` - tests article grid and table in page-with-sidebar template  
`npm run test:blocks:local -- --blocks=article-grid,table,accordion --template=page-with-sidebar --deletePage` - tests article grid, table, and accordion with page with sidebar and deletes all the pages afterwards

To run all blocks, you'd just leave the `blocks` parameter off, for example:  
`npm run test:blocks:local -- --template=page-with-sidebar --deletePage`

### CI/CD

Our Upsun CI/CD pipeline will only run these tests during maintenance because running all tests for each block could take a long time. So in our maintenance GH action we have:

```
- name: Run Cypress Tests
        run: npm run tests;npm run test:blocks:prod -- --template=page-with-sidebar --deletePage
```

this will run all the site tests (global and site specific) and the block tests
