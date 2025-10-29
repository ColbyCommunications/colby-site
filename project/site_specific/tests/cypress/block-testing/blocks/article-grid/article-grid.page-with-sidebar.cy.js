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
    beforeEach(() => {
        cy.loginToWordPress();
    });

    it('Adds the first block configuration - Page with Sidebar, internal posts, rectangle images, american studies', () => {
        cy.setupPage('article-grid', 'Page with Sidebar');
        cy.addBlock('article-grid');

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

    it('Verifies that the block was added successfully - Page with Sidebar, internal posts, rectangle images, american studies', () => {
        cy.visit('/block-testing-for-article-grid-page-with-sidebar/');

        validateBlockName('article-grid');
        cy.wait(1000);

        validatePostCount(2);
        cy.wait(1000);
    });

    // Second configuration
    it('Adds the second block configuration - Page with Sidebar, internal posts, unlimited posts, anthropology', () => {
        cy.visit('/block-testing-for-article-grid-page-with-sidebar/');
        cy.editPage();
        cy.addBlock('article-grid');

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

    it('Verifies that the block was added successfully - Page with Sidebar, internal posts, unlimited posts, anthropology', () => {
        cy.visit('/block-testing-for-article-grid-page-with-sidebar/');

        validateBlockName('article-grid');
        cy.wait(1000);

        validatePostCount(1);
        cy.wait(1000);
    });

    // Third configuration
    it('Adds the third block configuration - Page with Sidebar, internal posts, 12 posts, art', () => {
        cy.visit('/block-testing-for-article-grid-page-with-sidebar/');
        cy.editPage();
        cy.addBlock('article-grid');

        setDisplayPostsMethod('internal');
        setRenderPosts(true);
        setSize('small');
        setColumns('2');
        setImageOrientation('rectangle');
        setBorder(false);
        selectRenderPostsCategory('Art');
        setPostLimit(12);
        cy.wait(3000);
        cy.savePage();
    });

    it('Verifies that the block was added successfully - Page with Sidebar, internal posts, 12 posts, art', () => {
        cy.visit('/block-testing-for-article-grid-page-with-sidebar/');

        validateBlockName('article-grid');
        cy.wait(3000);

        validatePostCount(12);
        cy.wait(1000);
    });

    after(() => {
        if (Cypress.env('DELETEPAGE')) {
            cy.editPage();
            cy.deletePage();
        }
    });
});
