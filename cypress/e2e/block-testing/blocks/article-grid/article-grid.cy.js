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

    it('Adds the first block configuration - internal posts, rectangle images, american studies', () => {
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

    it('Verifies that the block was added successfully - internal posts, rectangle images, american studies', () => {
        cy.visit('/block-testing-for-article-grid/');

        validateBlockName();
        cy.wait(1000);

        validatePostCount(2);
        cy.wait(1000);
    });

    // Second configuration
    it('Adds the second block configuration - internal posts, unlimited posts, anthropology', () => {
        cy.visit('/block-testing-for-article-grid/');
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

    it('Verifies that the block was added successfully - internal posts, unlimited posts, anthropology', () => {
        cy.visit('/block-testing-for-article-grid/');

        validateBlockName();
        cy.wait(1000);

        validatePostCount(1);
        cy.wait(1000);
    });

    // Third configuration
    it('Adds the third block configuration - internal posts, 12 posts, art', () => {
        cy.visit('/block-testing-for-article-grid/');
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

    it('Verifies that the block was added successfully - internal posts, 12 posts, art', () => {
        cy.visit('/block-testing-for-article-grid/');

        validateBlockName();
        cy.wait(5000);

        validatePostCount(12);
        cy.wait(1000);
        cy.editPage();
        //cy.deletePage();
    });
});
