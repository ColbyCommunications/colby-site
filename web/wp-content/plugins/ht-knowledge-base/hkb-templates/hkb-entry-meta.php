<?php
/**
 * Template for the article meta
 *
 * @package hkb-templates/
 */

?>

<?php 
	//set the meta position based on the template part name (else use top)
	$meta_position = ( $args['ht_kb_get_template_part_name'] ) ? $args['ht_kb_get_template_part_name'] : 'top'; 
?>

<!-- .hkb-article__meta -->
<ul class="hkb-article__meta">
	<?php do_action( 'ht_kb_article_meta_display', $meta_position ); ?>
</ul>
<!-- /.hkb-article__meta -->
