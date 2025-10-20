<?php

if ( 'master' == getenv( 'PLATFORM_BRANCH' ) ) {
    define( 'ALGOLIA_INDEX_NAME_PREFIX', 'prod_colbyedu_' );
} else {
    define( 'ALGOLIA_INDEX_NAME_PREFIX', 'platform_colbyedu_' );
}