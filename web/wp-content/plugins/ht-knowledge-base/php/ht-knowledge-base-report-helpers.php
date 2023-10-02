<?php
/**
* Report helper functions
*/

//exit if accessed directly
if ( ! defined( 'ABSPATH' ) ) exit;



if(!function_exists('ht_kb_report_start_date')){
	/**
	* Print start date
	*/
	function ht_kb_report_start_date(){ 
		$report_period_duration = apply_filters( 'ht_kb_report_period_duration', WEEK_IN_SECONDS );
		$report_end_timestamp = apply_filters( 'ht_kb_report_period_end', time() );
		$report_end_timestamp = is_int( $report_end_timestamp ) ? $report_end_timestamp : time();
		$report_start_timestamp = apply_filters( 'ht_kb_report_period_start', $report_end_timestamp - $report_period_duration  );
		$date_format = get_option( 'date_format' );
		echo date( $date_format, $report_start_timestamp ); 
	}

}

if(!function_exists('ht_kb_report_end_date')){
	/**
	* Print end date
	*/
	function ht_kb_report_end_date(){ 
		//default to unix timestamp
		$report_end_timestamp = apply_filters( 'ht_kb_report_period_end', time() );
		$report_end_timestamp = is_int( $report_end_timestamp ) ? $report_end_timestamp : time();
		$date_format = get_option( 'date_format' );
		echo date( $date_format, $report_end_timestamp ); 
	}

}


if(!function_exists('ht_kb_report_total_views')){
	/**
	* Print total number of views for the period
	*/
	function ht_kb_report_total_views(){ 
		//requires $wpdb 
		global $wpdb;
		//default to unix timestamp
		$report_end_timestamp = apply_filters( 'ht_kb_report_period_end', time() );
		$report_end_timestamp = is_int( $report_end_timestamp ) ? $report_end_timestamp : time();
		$report_end_timestamp_offset = (int) apply_filters( 'ht_kb_report_time_offset', $report_end_timestamp + DAY_IN_SECONDS );
		$end_sql = date( 'Y-m-d', $report_end_timestamp_offset );

		$report_period_duration = apply_filters( 'ht_kb_report_period_duration', WEEK_IN_SECONDS );
		$report_start_timestamp = apply_filters( 'ht_kb_report_period_start', $report_end_timestamp - $report_period_duration  );
		$report_start_timestamp = is_int( $report_start_timestamp ) ? $report_start_timestamp : time() - WEEK_IN_SECONDS;
		$report_start_timestamp_offset = (int) apply_filters( 'ht_kb_report_time_offset', $report_start_timestamp + DAY_IN_SECONDS );
		$start_sql = date( 'Y-m-d', $report_start_timestamp_offset );

		$total_visits_query = "SELECT
								  COUNT(*) as viewCount
								 FROM {$wpdb->prefix}hkb_visits
								 WHERE datetime > '{$start_sql}' AND datetime <= '{$end_sql}' 
								 AND object_type = 'ht_kb_article'
								";
					
		//Article views
		$stats = $wpdb->get_results($total_visits_query);
		$view_count = $stats[0]->viewCount;
		//apply number formatting
		$view_count = number_format_i18n( $view_count );
		echo apply_filters( 'ht_kb_report_total_views', $view_count );
	}
}

if(!function_exists('ht_kb_report_views_change')){
	/**
	* Print the view change
	* @todo - add some caching to this functionality
	*/
	function ht_kb_report_views_change(){ 
		//requires $wpdb 
		global $wpdb;
		//default to unix timestamp
		$report_end_timestamp = apply_filters( 'ht_kb_report_period_end', time() );
		$report_end_timestamp = is_int( $report_end_timestamp ) ? $report_end_timestamp : time();
		$report_end_timestamp_offset = (int) apply_filters( 'ht_kb_report_time_offset', $report_end_timestamp + DAY_IN_SECONDS );
		$end_sql = date( 'Y-m-d', $report_end_timestamp_offset );

		$report_period_duration = apply_filters( 'ht_kb_report_period_duration', WEEK_IN_SECONDS );
		$report_start_timestamp = apply_filters( 'ht_kb_report_period_start', $report_end_timestamp - $report_period_duration  );
		$report_start_timestamp = is_int( $report_start_timestamp ) ? $report_start_timestamp : time() - WEEK_IN_SECONDS;
		$report_start_timestamp_offset = (int) apply_filters( 'ht_kb_report_time_offset', $report_start_timestamp + DAY_IN_SECONDS );
		$start_sql = date( 'Y-m-d', $report_start_timestamp_offset );

		//compute prior period
		$report_duration = $report_end_timestamp - $report_start_timestamp;

		$prior_period_start_timestamp = $report_end_timestamp - $report_duration;
		$prior_sql = date( 'Y-m-d', $prior_period_start_timestamp );

		$this_period_query = "SELECT
								  COUNT(*) as viewCount
								 FROM {$wpdb->prefix}hkb_visits
								 WHERE datetime > '{$start_sql}' AND datetime <= '{$end_sql}'
								 AND object_type = 'ht_kb_article'
								";

		$stats = $wpdb->get_results($this_period_query);
		$this_period_views = $stats[0]->viewCount;

		$prior_period_query = "SELECT
								  COUNT(*) as viewCount
								 FROM {$wpdb->prefix}hkb_visits
								 WHERE datetime > '{$prior_sql}' AND datetime <= '{$start_sql}'
								 AND object_type = 'ht_kb_article'
								";
					
		$stats = $wpdb->get_results($prior_period_query);
		$prior_period_views = $stats[0]->viewCount; 

		//compute diff
		$view_change = $this_period_views - $prior_period_views;

		//compute percentage, avoid division by 0
		$view_change_percent = $prior_period_views > 0 ? ceil( absint($view_change) / $prior_period_views ) : 100;

		//computer change direction
		$direction_affix = $view_change >= 0 ? '↑' : '↓';

		$change_string = $direction_affix . $view_change_percent . '%';

		echo apply_filters( 'ht_kb_report_views_change', $change_string );
	}
}


if(!function_exists('ht_kb_report_total_articles')){
	/**
	* Print total number of articles
	*/
	function ht_kb_report_total_articles(){  
		$articles = get_posts('post_type=ht_kb&posts_per_page=-1');
		$article_count = count($articles);
		//apply number formatting
		$article_count = number_format_i18n( $article_count );
		echo apply_filters( 'ht_kb_report_total_articles', $article_count );
	}
}

if(!function_exists('ht_kb_report_total_categories')){
	/**
	* Print total number of categories
	*/
	function ht_kb_report_total_categories(){  
		$terms = get_terms( array(
			'taxonomy' => 'ht_kb_category',
			'hide_empty' => false,
		) );
		$cat_count = count($terms);
		//apply number formating
		$cat_count = number_format_i18n( $cat_count );
		echo apply_filters( 'ht_kb_report_total_categories', $cat_count );
	}
}

if(!function_exists('ht_kb_report_average_helpfulness')){
	/**
	* Print average helpfulness for the period
	*/
	function ht_kb_report_average_helpfulness(){  
		//requires $wpdb 
		global $wpdb;

		//todo - check for voting table?

		$report_end_timestamp = apply_filters( 'ht_kb_report_period_end', time() );
		$report_end_timestamp = is_int( $report_end_timestamp ) ? $report_end_timestamp : time();
		$report_end_timestamp_offset = (int) apply_filters( 'ht_kb_report_time_offset', $report_end_timestamp + DAY_IN_SECONDS );
		$end_sql = date( 'Y-m-d', $report_end_timestamp_offset );

		$report_period_duration = apply_filters( 'ht_kb_report_period_duration', WEEK_IN_SECONDS );
		$report_start_timestamp = apply_filters( 'ht_kb_report_period_start', $report_end_timestamp - $report_period_duration  );
		$report_start_timestamp = is_int( $report_start_timestamp ) ? $report_start_timestamp : time() - WEEK_IN_SECONDS;
		$report_start_timestamp_offset = (int) apply_filters( 'ht_kb_report_time_offset', $report_start_timestamp + DAY_IN_SECONDS );
		$start_sql = date( 'Y-m-d', $report_start_timestamp_offset );

		//doesnt appear to like %1$s formatting
		$feedback_responses_query = sprintf( 	"SELECT COUNT(*) AS totalResponses,
                                    			SUM(CASE WHEN {$wpdb->prefix}%s.magnitude > 0 THEN 1 ELSE 0 END) AS totalUp,
                                    			SUM(CASE WHEN {$wpdb->prefix}%s.magnitude = 0 THEN 1 ELSE 0 END) AS totalDown
                                    			FROM {$wpdb->prefix}%s
                                    			WHERE datetime > '{$start_sql}' AND datetime <= '{$end_sql}'
                                    			",
                                    		HT_VOTING_TABLE, HT_VOTING_TABLE, HT_VOTING_TABLE );
        //feedback overview
        $stats = $wpdb->get_results($feedback_responses_query);
        $data = $stats[0];

        //hard set the variables
        $data->totalUp = (isset($data->totalUp)) ? $data->totalUp : '-';
        $data->totalDown = (isset($data->totalDown)) ? $data->totalDown : '-';

        $average_helpfulness = ((int)$data->totalResponses > 0) ? round( ( (int)$data->totalUp / (int)$data->totalResponses )*100 ) : 100;

        $average_helpfulness_string = sprintf( __('%s%%', 'ht-knowledge-base'), $average_helpfulness );
		
		echo apply_filters( 'ht_kb_report_average_helpfulness', $average_helpfulness_string );
	}
}

if(!function_exists('ht_kb_report_average_helpfulness_change')){
	/**
	* Print average helpfulness for the period
	*/
	function ht_kb_report_average_helpfulness_change(){  
		//requires $wpdb 
		global $wpdb;

		//todo - check for voting table?

		$report_end_timestamp = apply_filters( 'ht_kb_report_period_end', time() );
		$report_end_timestamp = is_int( $report_end_timestamp ) ? $report_end_timestamp : time();
		$report_end_timestamp_offset = (int) apply_filters( 'ht_kb_report_time_offset', $report_end_timestamp + DAY_IN_SECONDS );
		$end_sql = date( 'Y-m-d', $report_end_timestamp_offset );

		$report_period_duration = apply_filters( 'ht_kb_report_period_duration', WEEK_IN_SECONDS );
		$report_start_timestamp = apply_filters( 'ht_kb_report_period_start', $report_end_timestamp - $report_period_duration  );
		$report_start_timestamp = is_int( $report_start_timestamp ) ? $report_start_timestamp : time() - WEEK_IN_SECONDS;
		$report_start_timestamp_offset = (int) apply_filters( 'ht_kb_report_time_offset', $report_start_timestamp + DAY_IN_SECONDS );
		$start_sql = date( 'Y-m-d', $report_start_timestamp_offset );

		//compute prior period
		$report_duration = $report_end_timestamp - $report_start_timestamp;

		$prior_period_start_timestamp = $report_end_timestamp - $report_duration;
		$prior_sql = date( 'Y-m-d', $prior_period_start_timestamp );

		$this_period_query = sprintf ( 	"SELECT COUNT(*) AS totalResponses,
                    					SUM(CASE WHEN {$wpdb->prefix}%s.magnitude > 0 THEN 1 ELSE 0 END) AS totalUp,
                    					SUM(CASE WHEN {$wpdb->prefix}%s.magnitude = 0 THEN 1 ELSE 0 END) AS totalDown
                    					FROM {$wpdb->prefix}%s
								 		WHERE datetime > '{$start_sql}' AND datetime <= '{$end_sql}'
										", HT_VOTING_TABLE, HT_VOTING_TABLE, HT_VOTING_TABLE ) ;

		$stats = $wpdb->get_results($this_period_query);
		$this_period_upvotes =  ( isset( $stats[0]->totalUp ) ) ? $stats[0]->totalUp : 0 ;
		$this_period_downvotes = ( isset( $stats[0]->totalDown ) ) ? $stats[0]->totalDown : 0 ;
		$this_period_helpfulness = ((int)$this_period_downvotes > 0) ? round( ( (int)$this_period_upvotes / (int)$this_period_downvotes )*100 ) : 100;

		$prior_period_query = sprintf( 	"SELECT COUNT(*) AS totalResponses,
                    					SUM(CASE WHEN {$wpdb->prefix}%s.magnitude > 0 THEN 1 ELSE 0 END) AS totalUp,
                    					SUM(CASE WHEN {$wpdb->prefix}%s.magnitude = 0 THEN 1 ELSE 0 END) AS totalDown
                    					FROM {$wpdb->prefix}%s
								 		WHERE datetime > '{$prior_sql}' AND datetime <= '{$start_sql}'
										", HT_VOTING_TABLE, HT_VOTING_TABLE, HT_VOTING_TABLE ) ;
					
		$stats = $wpdb->get_results($prior_period_query);
		$prior_period_upvotes =  ( isset( $stats[0]->totalUp ) ) ? $stats[0]->totalUp : 0 ;
		$prior_period_downvotes = ( isset( $stats[0]->totalDown ) ) ? $stats[0]->totalDown : 0 ;
		$prior_period_helpfulness = ((int)$prior_period_downvotes > 0) ? round( ( (int)$prior_period_upvotes / (int)$prior_period_downvotes )*100 ) : 0;

		//compute diff
		$helpfulness_change = $this_period_helpfulness - $prior_period_helpfulness;

		//compute percentage, avoid division by 0
		$helpfulness_change_percent = $prior_period_helpfulness > 0 ? ceil( absint($helpfulness_change) / $prior_period_helpfulness ) : 100;

		//computer change direction
		$direction_affix = $helpfulness_change >= 0 ? '↑' : '↓';

		$change_string = $direction_affix . $helpfulness_change_percent . '%';
		
		echo apply_filters( 'ht_kb_report_average_helpfulness_change', $change_string );
	}
}

if(!function_exists('ht_kb_report_viewed_articles')){
	/**
	* Print most viewed articles
	*/
	function ht_kb_report_viewed_articles( $limit = 5 ){ 
			$args = array();
			$args['post_type'] = 'ht_kb';
			$args['numberposts'] = $limit; 
			$args['order'] = 'DESC';
			$args['orderby'] = 'meta_value_num';
			$args['meta_key'] = HT_KB_POST_VIEW_COUNT_KEY;
			$posts = get_posts($args);
			foreach ($posts as $key => $post) {
				if(!is_a($post, 'WP_Post')){
					return;
				}

				echo '<li>';
				echo $post->post_title;
				echo '</li>';
			}
	}
}

if(!function_exists('ht_kb_report_helpful_articles')){
	/**
	* Print most helpful articles
	*/
	function ht_kb_report_helpful_articles( $limit = 5 ){ 
			$args = array();
			$args['post_type'] = 'ht_kb';
			$args['numberposts'] = $limit; 
			$args['order'] = 'DESC';
			$args['orderby'] = 'meta_value_num';
			$args['meta_key'] = HT_USEFULNESS_KEY;
			$posts = get_posts($args);
			foreach ($posts as $key => $post) {
				if(!is_a($post, 'WP_Post')){
					return;
				}

				echo '<li>';
				echo $post->post_title;
				echo '</li>';
			}
	}
}


