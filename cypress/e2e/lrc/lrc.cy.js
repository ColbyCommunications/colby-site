const url = Cypress.env('url');

describe(`tests for ${url}`, () => {
    beforeEach(() => {
        cy.visit(url);
    });

    it('checks all accordion contents', () => {
        cy.get('body').then(($body) => {
            const accordions = $body.find('.lightweight-accordion');

            // If no accordions are found, log and exit the test
            if (accordions.length === 0) {
                cy.log('No accordions found. Skipping test.');
                return;
            }

            // Loop through each accordion to check its content
            cy.wrap(accordions).each(($accordion) => {
                cy.wrap($accordion)
                    .find('.lightweight-accordion-body')
                    .should(($body) => {
                        expect(
                            $body
                                .html()
                                .includes('<span class="mejs-offscreen">Audio Player</span>') ||
                                $body
                                    .html()
                                    .includes('<span class="mejs-offscreen">Video Player</span>') ||
                                $body.html().includes('<table border="1" width="100%">')
                        ).to.be.true;
                    });
            });
        });
    });
});
