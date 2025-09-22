// cypress/support/commands.js

Cypress.Commands.add('loginToWordPress', () => {
    const wpAdminUrl = Cypress.env('WP_URL');
    const username = Cypress.env('WP_USERNAME');
    const password = Cypress.env('WP_PASSWORD');

    cy.visit(wpAdminUrl);
    cy.get('#user_login').clear({ force: true }).click().type(username);
    cy.get('#user_pass').clear({ force: true }).click().type(password);
    cy.get('#wp-submit').click();
});

Cypress.Commands.add('setupPage', () => {
    const wpAdminUrl = Cypress.env('WP_URL');
    const blockName = Cypress.env('BLOCK_NAME');
    const template = Cypress.env('TEMPLATE');

    cy.visit(`${wpAdminUrl}/post-new.php?post_type=page`);

    cy.url().should('include', 'post-new.php?post_type=page');

    cy.get('h1.editor-post-title__input[contenteditable="true"]')
        .should('be.visible')
        .click()
        .type(`Block Testing for ${blockName}`, { force: true });

    cy.wait(1000);

    cy.get('button[aria-label="Template options"]').should('be.visible').click();

    cy.get('select.components-select-control__input').should('be.visible').select(template);

    cy.wait(1000);

    cy.get('button[aria-label="Close"]').click();
});

// Utility: convert block name into data-type slug
function blockNameToSlug(blockName) {
    return blockName
        .toLowerCase()
        .replace(/\s+/g, '-') // replace spaces with dashes
        .replace(/[^a-z0-9-]/g, ''); // strip out invalid characters
}

// Add a block
Cypress.Commands.add('addBlock', (blockName) => {
    // If blockName wasn’t passed in, fall back to the CLI/env variable
    if (!blockName) {
        blockName = Cypress.env('BLOCK_NAME');
        if (!blockName) {
            throw new Error('addBlock requires a blockName. Pass via CLI or Cypress.env.');
        }
    }
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

    // Dynamically target the block that was just inserted
    const slug = blockNameToSlug(blockName);
    cy.get(`.wp-block[data-type="acf/${slug}"]`).last().as('currentBlock');
});

// Publish the page
Cypress.Commands.add('publishPage', () => {
    cy.get('button.editor-post-publish-panel__toggle').should('be.visible').click({ force: true });

    cy.wait(5000);

    cy.get(
        'button.components-button.editor-post-publish-button.editor-post-publish-button__button.is-primary.is-compact'
    )
        .should('be.visible')
        .click({ force: true });

    cy.wait(5000);

    cy.get('div.components-snackbar', { timeout: 10000 })
        .should('be.visible')
        .within(() => {
            cy.get('a.components-button.components-snackbar__action.is-tertiary')
                .should('be.visible')
                .click({ force: true });
        });

    cy.wait(5000);
});

// Edit the page
Cypress.Commands.add('editPage', () => {
    cy.get('#wp-admin-bar-edit a.ab-item[role="menuitem"]')
        .should('be.visible')
        .click({ force: true });
});

Cypress.Commands.add('savePage', () => {
    // Click the Save button
    cy.get('button.editor-post-publish-button').should('be.visible').click({ force: true });

    // Wait for the snackbar and click "View Page"
    cy.get('div.components-snackbar', { timeout: 10000 })
        .should('be.visible')
        .within(() => {
            cy.get('a.components-button.components-snackbar__action.is-tertiary')
                .should('be.visible')
                .click({ force: true });
        });

    cy.wait(3000);
});
