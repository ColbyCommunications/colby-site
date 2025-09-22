import {
    setDisplayPostsMethod,
    setRenderPosts,
    setSize,
    setColumns,
    setImageOrientation,
    setBorder,
    selectRenderPostsCategory,
    setPostLimit,
    validateBlockName,
    validatePostCount,
} from './ArticleGrid';

// First configuration
describe('Article Grid Block', () => {
    it('Adds the first block configuration', () => {
        cy.loginToWordPress();
        cy.setupPage();
        cy.addBlock();

        setDisplayPostsMethod('internal');
        setRenderPosts(true);
        setSize('small');
        setColumns('2');
        setImageOrientation('rectangle');
        setBorder(false);
        selectRenderPostsCategory('American Studies');
        setPostLimit(2);
        cy.publishPage();
    });

    it('Verifies that the block was added successfully', () => {
        cy.visit('https://colby.lndo.site/block-testing-for-article-grid/');

        validateBlockName();
        cy.wait(1000);

        validatePostCount(2);
        cy.wait(1000);
    });

    // Second configuration
    it('Adds the second block configuration', () => {
        cy.loginToWordPress();
        cy.visit('https://colby.lndo.site/block-testing-for-article-grid/');
        cy.editPage();
        cy.addBlock();

        setDisplayPostsMethod('internal');
        setRenderPosts(true);
        setSize('small');
        setColumns('2');
        setImageOrientation('rectangle');
        setBorder(false);
        selectRenderPostsCategory('Anthropology');
        setPostLimit(-1);
        cy.savePage();
    });

    it('Verifies that the block was added successfully', () => {
        cy.visit('https://colby.lndo.site/block-testing-for-article-grid/');

        validateBlockName();
        cy.wait(1000);

        validatePostCount(1);
        cy.wait(1000);
    });

    // Third configuration
    it('Adds the third block configuration', () => {
        cy.loginToWordPress();
        cy.visit('https://colby.lndo.site/block-testing-for-article-grid/');
        cy.editPage();
        cy.addBlock();

        setDisplayPostsMethod('internal');
        setRenderPosts(true);
        setSize('small');
        setColumns('2');
        setImageOrientation('rectangle');
        setBorder(false);
        selectRenderPostsCategory('Art');
        setPostLimit(12);
        cy.wait(10000);
        cy.savePage();
    });

    it('Verifies that the block was added successfully', () => {
        cy.visit('https://colby.lndo.site/block-testing-for-article-grid/');

        validateBlockName();
        cy.wait(5000);

        validatePostCount(12);
        cy.wait(1000);
    });
});
