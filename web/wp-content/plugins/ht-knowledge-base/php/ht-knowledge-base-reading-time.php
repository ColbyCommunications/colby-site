<?php
/**
* Self contained article/post reading time calculations
*/

//exit if accessed directly
if ( ! defined( 'ABSPATH' ) ) exit;

if( !class_exists( 'HT_Knowledge_Base_Reading_Time' ) ){

	if(!defined('HT_KB_POST_READING_TIME_KEY')){
		define('HT_KB_POST_READING_TIME_KEY', '_ht_kb_post_reading_time');
	}

	class HT_Knowledge_Base_Reading_Time {

		//constructor
		function __construct() {

			//hook onto save post action
			add_action( 'save_post', array( $this, 'ht_kb_readtime_time_save_post' ), 10, 3 );

			//get post reading time, allows for an offset to be added
			add_filter( 'ht_kb_get_post_reading_time', array( $this, 'ht_kb_get_post_reading_time' ), 10, 2 );

			//set post reading time, allows for an offset to be added
			add_filter( 'ht_kb_set_post_reading_time', array( $this, 'ht_kb_set_post_reading_time' ), 10, 2 );

			//add activation action for table
			add_action( 'ht_kb_activate', array( $this, 'on_activate' ), 10, 1 );

			//display in Article Stats edit meta box
			add_action( 'ht_knowledge_base_render_article_stats_meta_box_additional_items', array( $this, 'ht_kb_reading_time_article_stats' ), 10, 1 );

		}

		function ht_kb_readtime_time_save_post( $post_id, $post, $update ){
			//specify which post types to add read time to
			$post_types_to_add_read_time = apply_filters( 'ht_kb_post_types_to_add_readtime', array( 'ht_kb' ) );

			if( !empty( $post_id ) && is_a( $post, 'WP_Post' ) && in_array( $post->post_type, $post_types_to_add_read_time ) ){
				$ht_kb_readtime_default_offset_seconds = apply_filters( 'ht_kb_readtime_default_offset_seconds', 0, $post_id, $post, $update );
				apply_filters( 'ht_kb_set_post_reading_time', $post_id, $ht_kb_readtime_default_offset_seconds );
			}
		}


		/**
		* Get the reading time from the database
		* @param (Int) $offset How much to offset the view count by
		* @param (Int) $post_id ID of article to fetch count
		* @return (Int) The reading time in seconds
		*/
		function ht_kb_get_post_reading_time( $post_id=0, $offset_seconds=0 ){
			//get the reading time (stored in seconds) 
			$reading_time = get_post_meta( $post_id, HT_KB_POST_READING_TIME_KEY, true );

			//set to 0 if empty
			$reading_time = empty($reading_time) ? 0 : intval( $reading_time );

			//return the reading time plus offset in seconds
			return $reading_time + $offset_seconds; 
		}

		/**
		* Article reading time
		* @param (Int) $post_id The ID of the post to increment the view count
		*/
		function ht_kb_set_post_reading_time( $post_id=0, $offset_seconds=0 ) {
			//do nothing if the post id is empty
			if( empty($post_id) ){
				return;
			}

			//get the posts reading time by running the ht_kb_get_post_reading_time filter 
			$reading_time = $this->ht_kb_compute_post_reading_time( $post_id );
			//set post meta, stored in seconds
			update_post_meta( $post_id, HT_KB_POST_READING_TIME_KEY, $reading_time );
		}

		/**
		 * Computations based on https://blog.medium.com/read-time-and-you-bc2048ab620c
		 */
		function ht_kb_compute_post_reading_time( $post_id, $offset_seconds=0 ){
			//get the reading time WPM (default 250)
			$reading_time_wpm = (int) apply_filters( 'ht_kb_post_reading_time_wpm', 250 );
			//get post content
			$post_content = get_post_field( 'post_content', $post_id );
			//strip shortcodes if required (default false)
			$post_content = apply_filters( 'ht_kb_post_reading_time_strip_shortcodes', false ) ? strip_shortcodes( $post_content ) : $post_content;
			//get the number of images
			$number_of_images = substr_count( strtolower( $post_content ), '<img ' );
			//strip all tags
			$post_content = wp_strip_all_tags( $post_content );
			//compute the word count
			$word_count = count( preg_split( '/\s+/', $post_content ) );
			//computer read time for words 
			$reading_time_seconds = ( $word_count / $reading_time_wpm ) * 60;
			//add in time for images
			$reading_time_seconds += $this->ht_kb_compute_post_images_read_time( $number_of_images );
			//add in any offset (default 0)
			$reading_time_seconds += (int) apply_filters( 'ht_kb_compute_post_reading_time_offset', $offset_seconds, $post_id );
			//apply ceil function to round up to nearest integer
			$reading_time_seconds = ceil( $reading_time_seconds );
			//apply filters and return
			return apply_filters( 'ht_kb_compute_post_reading_time', $reading_time_seconds, $post_id );

		}

		function ht_kb_compute_post_images_read_time( $number_of_images ) {
			$additional_time = 0;
			//12s for first image, then 1 second less for each subsequent image down to a minimum of 3s per image
			for ( $i = 1; $i <= $number_of_images; $i++ ) {
				if ( $i > 10 ) {
					$additional_time += (int) apply_filters( 'ht_kb_post_reading_time_additional_images', 3 );;
				} else {
					$additional_time += (int) apply_filters( 'ht_kb_post_reading_time_first_images', 13 ); - $i;
				}
			}
			//return the computation for additional time based on images
			return $additional_time;
		}


		function on_activate( $network_wide = null ) {
			global $wpdb;
			//@todo - query multisite compatibility
			if ( is_multisite() && $network_wide ) {
				//store the current blog id
				$current_blog = $wpdb->blogid;
				//get all blogs in the network and activate plugin on each one
				$blog_ids = $wpdb->get_col( "SELECT blog_id FROM $wpdb->blogs" );
				foreach ( $blog_ids as $blog_id ) {
					switch_to_blog( $blog_id );
					$this->upgrade_reading_time_on_articles();
					restore_current_blog();
				}
			} else {
				$this->upgrade_reading_time_on_articles();
			}
		}

		static function hkb_visits_plugin_deactivation_hook() {
			//do nothing
		}


		/**
		* Upgrade Knowledge Base install - hook to ht_kb_activate
		*/
		function upgrade_reading_time_on_articles( $recompute = false ){
			$kb_articles_args = array( 'post_type' => 'ht_kb', 'posts_per_page' => -1, 'post_status' => 'any' );
			$kb_articles = get_posts($kb_articles_args);

			foreach ($kb_articles as $key => $article) {
			   $this->update_reading_time_meta( $article->ID, $recompute );
			}
		}

		/**
		 * Add or update reading time to posts without it
		 */
		function update_reading_time_meta( $post_id, $recompute = false ){
			//get the reading time meta
			$reading_time = get_post_meta( $post_id, HT_KB_POST_READING_TIME_KEY, true );
			//if it doesn't exist, add it
			if( empty($reading_time) || $recompute ){
				$reading_time = apply_filters('ht_kb_set_post_reading_time', $post_id, 0 );
			}
		}

		function ht_kb_reading_time_article_stats( $post_id ){
			$post_reading_time = apply_filters( 'ht_kb_get_post_reading_time', $post_id, 0 );
			$reading_time_raw =  $post_reading_time > 1 ? ceil( $post_reading_time/MINUTE_IN_SECONDS ) : 1 ;
			$reading_time_output = sprintf( _n( '%s minute', '%s minutes', $reading_time_raw, 'ht-knowledge-base' ), $reading_time_raw );
			?>
				<div class="hkb-articlestats__reading_time">
					<span class="hkb-articlestats__reading_time-label"><?php _e( 'Reading Time:', 'ht-knowledge-base' ); ?></span>
					<span class="hkb-articlestats__reading_time-value"><?php echo $reading_time_output; ?></span>
				</div>

			<?php
		}

	}
}

//run the module
if( class_exists( 'HT_Knowledge_Base_Reading_Time' ) ){
	new HT_Knowledge_Base_Reading_Time();
}