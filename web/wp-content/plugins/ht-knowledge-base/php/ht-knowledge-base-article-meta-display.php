<?php
/**
* Displays article meta items on the frontend
*/

//exit if accessed directly
if ( ! defined( 'ABSPATH' ) ) exit;

if (!class_exists('HT_Knowledge_Base_Article_Meta_Display')) {

	class HT_Knowledge_Base_Article_Meta_Display {

		//Constructor
		function __construct() {
			 //display article meta
			add_action( 'ht_kb_article_meta_display', array( $this, 'ht_kb_article_output_meta_items' ) );
			//default values
			add_filter( 'ht_kb_display_article_meta_item_on_frontend', array( $this, 'ht_kb_display_article_meta_item_on_frontend_setting' ), 10, 3 );
		}

		function ht_kb_article_output_meta_items( $meta_postion = 'top' ){
			$valid_meta_items = array(
								'publish_date',
								'last_updated',
								'author',
								'views',
								'rating',
								'comment_count',
								'attachment_count',
								'reading_time',
								'ht_kb_categories',
								'ht_kb_tags',
								'ht_kb_print'
						);

			//run filters
			$valid_meta_items = apply_filters( 'ht_kb_article_valid_meta_items', $valid_meta_items );

			foreach ( $valid_meta_items as $key => $item_name ) {
				$display_item = apply_filters( 'ht_kb_display_article_meta_item_on_frontend', false, $item_name, $meta_postion );
				if( $display_item ){
					switch ( $item_name ) {
						case 'publish_date':
							$this->display_article_publish_date();
							break;
						case 'last_updated':
							$this->display_article_last_updated();
							break;
						case 'author':
							$this->display_article_author();
							break;
						case 'views':
							$this->display_article_view_count();
							break;
						case 'rating':
							$this->display_article_rating();
							break;
						case 'comment_count':
							$this->display_article_comment_count();
							break;
						case 'attachment_count':
							$this->display_article_attachment_count();
							break;
						case 'reading_time':
							$this->display_article_reading_time();
							break;
						case 'ht_kb_categories':
							$this->display_article_categories();
							break;
						case 'ht_kb_tags':
							$this->display_article_tags();
							break;
						case 'ht_kb_print':
							$this->display_print_button();
							break;
						
						default:
							// code...
							break;
					}
					echo '<br/>';
				}
			}
		}

		function display_article_publish_date(){
			$display_article_publish_date_class_name = apply_filters( 'display_article_publish_date_class_name', 'hkb-date' );
			//rely on the WP get_the_date function
			printf( '<li class="%s">%s</li>', $display_article_publish_date_class_name, get_the_date() );
		}

		function display_article_last_updated(){
			$display_article_last_updated_class_name = apply_filters( 'display_article_last_updated_class_name', 'hkb-updated' );
			//rely on the WP get_the_modified_date function
			printf( '<li class="%s">%s</li>', $display_article_last_updated_class_name, get_the_modified_date() );
		}

		function display_article_author(){			
			$display_article_author_class_name = apply_filters( 'display_article_author_class_name', 'hkb-author' );
			//rely on the WP get_the_author function
			printf( '<li class="%s">%s</li>', $display_article_author_class_name, get_the_author() );
		}

		function display_article_view_count(){
			$view_count = (int) get_post_meta( get_the_ID(), HT_KB_POST_VIEW_COUNT_KEY, true );
			$output = esc_attr( apply_filters( 'ht_kb_article_meta_display_view_count', $view_count ) );

			$display_article_view_count_class_name = apply_filters( 'display_article_view_count_class_name', 'hkb-views' );
			printf( '<li class="%s">%s</li>', $display_article_view_count_class_name, $output );
		}

		function display_article_rating(){
			if( function_exists('ht_usefulness') ){                             
				$rating = ht_usefulness( get_the_ID() );
				$output = esc_attr( apply_filters( 'ht_kb_article_meta_display_rating', $rating ) );

				$display_article_rating_class_name = apply_filters( 'display_article_rating_class_name', 'hkb-rating' );
				printf( '<li class="%s">%s</li>', $display_article_rating_class_name, $output );
			}
		}

		function display_article_comment_count(){                           
			$comment_count = get_comments_number();
			$output = esc_attr( apply_filters( 'ht_kb_article_meta_display_comment_count', $comment_count ) );

			$display_article_comment_count_class_name = apply_filters( 'display_article_comment_count_class_name', 'hkb-comment-count' );
			printf( '<li class="%s">%s</li>', $display_article_comment_count_class_name, $output );
		}

		function display_article_attachment_count(){
			if( function_exists('hkb_get_attachments') ){
				$attachments = hkb_get_attachments( get_the_ID() );
				$attachments_count = empty($attachments) ? 0 : count($attachments);
				$output = esc_attr( apply_filters( 'ht_kb_article_meta_display_attachment_count', $attachments_count ) );

				$display_article_attachment_count_class_name = apply_filters( 'display_article_attachment_count_class_name', 'attachment_count' );
				printf( '<li class="%s">%s</li>', $display_article_attachment_count_class_name, $output );
			}
		}

		function display_article_reading_time(){			
			$post_reading_time = apply_filters( 'ht_kb_get_post_reading_time', get_the_ID() );
			$reading_time_raw =  $post_reading_time > 1 ? ceil( $post_reading_time/MINUTE_IN_SECONDS ) : 1 ;
			$reading_time_output = sprintf( _n( '%s minute', '%s minutes', $reading_time_raw, 'ht-knowledge-base' ), $reading_time_raw );
			$output = esc_attr( apply_filters( 'ht_kb_article_meta_display_reading_time', $reading_time_output ) );

			$display_article_reading_time_class_name = apply_filters( 'display_article_reading_time_class_name', 'hkb-reading-time' );
			printf( '<li class="%s">%s</li>', $display_article_reading_time_class_name, $output );
		}

		function display_article_categories(){
			//@todo - replace with get_the_term_list
			$categories = get_the_terms( get_the_ID(), 'ht_kb_category' );

			if(!$categories){
				return;
			}

			$output = '';
			$items_length = count( $categories );
			$counter = 1;

			foreach ( $categories as $key => $category ) {
				if( is_a( $category , 'WP_Term' ) ){
					$category_name = $category->name;
					$category_item_name = esc_attr( apply_filters( 'ht_kb_article_meta_display_article_categories_item_name', $category_name ) );
					$category_span_format = apply_filters( 'ht_kb_article_meta_category_span_format', '<span="hkb-category">%s</span>' );
					$output .= sprintf( $category_span_format , $category_item_name );

					if( $counter < $items_length ){
						$output .= apply_filters( 'ht_kb_article_meta_display_categories_item_separater', ', ' );
					}

					//when PHP7.2 is guaranteed, we can use array_key_last logic instead
					$counter++;
				}
			}

			$display_article_categories_class_name = apply_filters( 'display_article_categories_class_name', 'hkb-categories' );
			printf( '<li class="%s">%s</li>', $display_article_categories_class_name, $output );
		}

		function display_article_tags(){
			//@todo - replace with get_the_term_list
			$tags = get_the_terms( get_the_ID(), 'ht_kb_tag' );

			if(!$tags){
				return;
			}

			$output = '';
			$items_length = count( $tags );
			$counter = 1;

			foreach ( $tags as $key => $tag ) {
				if( is_a( $tag , 'WP_Term' ) ){
					$tag_name = $tag->name;
					$tag_item_name = esc_attr( apply_filters( 'ht_kb_article_meta_display_article_tags_item_name', $tag_name ) );
					$tag_span_format = apply_filters( 'ht_kb_article_meta_tag_span_format', '<span="hkb-tag">%s</span>' );
					$output .= sprintf( $tag_span_format , $tag_item_name );

					if( $counter < $items_length ){
						$output .= apply_filters( 'ht_kb_article_meta_display_article_tags_item_separater', ', ' );
					}
					
					//when PHP7.2 is guaranteed, we can use array_key_last logic instead
					$counter++;
				}
			}

			$display_article_tags_class_name = apply_filters( 'display_article_tags_class_name', 'hkb-tags' );
			printf( '<li class="%s">%s</li>', $display_article_tags_class_name, $output );
		}

		function display_print_button(){

			$print_button_label = esc_attr( apply_filters( 'ht_kb_article_meta_print_button_label', __( 'Print Article', 'ht-knowledge-base' ) ) );
			$js_action = apply_filters( 'ht_kb_article_meta_print_button_js_action', 'onclick="window.print();return false;"' ); //codestandards ignore
			$display_article_print_button_class = apply_filters( 'display_article_print_button_class', 'hkb-print-article' );
			printf( '<li class="%s" %s>%s</li>', $display_article_print_button_class, $js_action, $print_button_label );
		}


		function ht_kb_display_article_meta_item_on_frontend_setting( $display = false, $item_name = false, $meta_postion = 'any' ){
			global $ht_knowledge_base_settings;

			//array map
			$article_meta_item_map = array(
				'publish_date' => 'display-meta-publish-date',
				'last_updated' => 'display-meta-last-updated',
				'author' => 'display-meta-author',
				'views' => 'display-meta-views',
				'rating' => 'display-meta-rating',
				'comment_count' => 'display-meta-comment-count',
				'attachment_count' => 'display-meta-attachment-count',
				'reading_time' => 'display-meta-reading-time',
				'ht_kb_categories' => 'display-meta-article-categories',
				'ht_kb_tags' => 'display-meta-article-tags',
				'ht_kb_print' => 'display-meta-print-button',
			);

			//apply filters to allow for additional items
			$article_meta_item_map = apply_filters( 'article_meta_item_map', $article_meta_item_map );

			$setting_key = array_key_exists( $item_name, $article_meta_item_map ) ? $article_meta_item_map[$item_name] : false;

			//early exit if setting key does not map
			if( !$setting_key ){
				return false;
			}

			$value = array_key_exists( $setting_key, $ht_knowledge_base_settings ) ? $ht_knowledge_base_settings[ $setting_key ] : false;

			return $value;
		}



	} //end class
}//end class exists

//run the module
if(class_exists('HT_Knowledge_Base_Article_Meta_Display')){
	new HT_Knowledge_Base_Article_Meta_Display();
}