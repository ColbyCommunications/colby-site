// addBlock function
export function addBlock(blockName = 'Article Grid') {
    // Open the block drawer
    cy.get('button[aria-label="Toggle block inserter"]').click();
    cy.wait(1000);

    // Search and click on the block
    cy.get('input[placeholder="Search"].components-input-control__input').click().type(blockName);
    cy.wait(1000);

    cy.contains('.block-editor-block-types-list__item-title span', blockName)
        .closest('button')
        .click({ force: true });
    cy.wait(1000);

    // Close the block drawer
    cy.get('button[aria-label="Close block inserter"]').click();

    // Grab the most recently added block
    cy.get('.wp-block[data-type="acf/article-grid"]').last().as('currentBlock');

    return this; // allow chaining
}

// Publishes the page
export function publishPage() {
    // Click the first "Publish" button to open the panel
    cy.get('button.editor-post-publish-panel__toggle').should('be.visible').click({ force: true });

    cy.wait(5000);

    // Click the second "Publish" button to confirm
    cy.get(
        'button.components-button.editor-post-publish-button.editor-post-publish-button__button.is-primary.is-compact'
    )
        .should('be.visible')
        .click({ force: true });

    cy.wait(5000);

    // Wait for the "Post published" notice
    // Wait for the snackbar to appear
    cy.get('div.components-snackbar', { timeout: 10000 })
        .should('be.visible')
        .within(() => {
            // Click the "View Page" link inside the snackbar
            cy.get('a.components-button.components-snackbar__action.is-tertiary')
                .should('be.visible')
                .click({ force: true });
        });

    cy.wait(5000);
}

// Sets the display posts method
export function setDisplayPostsMethod(method = 'internal') {
    cy.get('@currentBlock').within(() => {
        cy.get('select[name*="[field_66a797e74888c]"]').select(method);
    });
}

// Sets the render posts checkbox
export function setRenderPosts(checked = true) {
    cy.get('@currentBlock').within(() => {
        cy.get('input[type="checkbox"][name*="field_63571d765ae3d"]').then(($checkbox) => {
            if ($checkbox.prop('checked') !== checked) {
                cy.wrap($checkbox).click({ force: true });
            }
        });
    });
}

// Sets the size radio buttons
export function setSize(size = 'small') {
    cy.get('@currentBlock').within(() => {
        cy.get(`input[type="radio"][name*="field_6344542af7223"][value="${size}"]`).check({
            force: true,
        });
    });
}

// Sets the columns radio buttons
export function setColumns(columns = '2') {
    cy.get('@currentBlock').within(() => {
        cy.get(`input[type="radio"][name*="field_632bc0d32e53c"][value="${columns}"]`).check({
            force: true,
        });
    });
}

// Sets the image orientation radio buttons
export function setImageOrientation(orientation = 'rectangle') {
    cy.get('@currentBlock').within(() => {
        cy.get(`input[type="radio"][name*="field_632bc98b58a51"][value="${orientation}"]`).check({
            force: true,
        });
    });
}

// Sets the border checkbox
export function setBorder(enabled = false) {
    cy.get('@currentBlock').within(() => {
        cy.get('input[type="checkbox"][name*="field_63446eb11e773"]').then(($checkbox) => {
            if (enabled && !$checkbox.prop('checked')) {
                cy.wrap($checkbox).click({ force: true });
            } else if (!enabled && $checkbox.prop('checked')) {
                cy.wrap($checkbox).click({ force: true });
            }
        });
    });
}

// Selects a render posts category by name
export function selectRenderPostsCategory(categoryName) {
    cy.get('@currentBlock').within(() => {
        cy.get('ul.acf-checkbox-list input[type="radio"]').each(($radio) => {
            cy.wrap($radio)
                .parent('label')
                .find('span')
                .invoke('text')
                .then((text) => {
                    if (text.trim() === categoryName) {
                        cy.wrap($radio).check({ force: true });
                    }
                });
        });
    });
}

// Sets the post limit number field
export function setPostLimit(limit = -1) {
    cy.get('@currentBlock').within(() => {
        cy.get('input[type="number"][name*="field_6682ca3641df8"]')
            .clear({ force: true })
            .type(`${limit}`, { force: true });
    });
}

// matches the expected block name (passed in via CLI or manually)
export function validateBlockName(expectedName = Cypress.env('BLOCK_NAME')) {
    if (!expectedName) {
        throw new Error('validateBlockName requires a block name (CLI: BLOCK_NAME="..." )');
    }

    // Convert expected name to slug for class matching
    const expectedSlug = expectedName.toLowerCase().replace(/\s+/g, '-');

    cy.get('div.wysiwyg')
        .first()
        .children()
        .last()
        .should('exist')
        .invoke('attr', 'class')
        .then((classAttr) => {
            cy.log(`Found last block classes: "${classAttr || '(no class attribute)'}"`);
            cy.log(`Expecting it to include: "${expectedSlug}"`);

            if (!classAttr) {
                throw new Error('Last child had no class attribute');
            }

            expect(classAttr).to.include(expectedSlug);
        });
}

// Validates the number of posts currently rendered in the block
export function validatePostCount(expectedCount = 0) {
    if (typeof expectedCount !== 'number') {
        throw new Error('validatePostCount requires a numeric expectedCount parameter');
    }

    cy.get('div.article-grid.grid')
        .last()
        .should('exist')
        .children()
        .then(($children) => {
            const actualCount = $children.length;
            cy.log(`Found ${actualCount} children in the last article-grid block`);
            cy.log(`Expecting ${expectedCount} children`);
            expect(actualCount, `Article Grid children count mismatch`).to.eq(expectedCount);
        });
}
