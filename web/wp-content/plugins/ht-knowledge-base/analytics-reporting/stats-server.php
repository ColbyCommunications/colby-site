<?php
/**
* Heroic Knowledge Base Reporting (HKBR)
* API for stats for Analytics 2.0 / Reporting
*	Heroic 
*/

//exit if accessed directly
if ( ! defined( 'ABSPATH' ) ) exit;

if( !class_exists( 'HKB_Stats_Server' )) {
	class HKB_Stats_Server {
	
		function __construct() {
			add_action( 'wp_ajax_hkbr_stats' , array( $this, 'hkbr_stats' ));
			add_action( 'wp_ajax_hkbr_actions' , array( $this, 'hkbr_actions' ));
		}

		//used in stats dashboard widget
		//@todo - refactor
		function hkbr_get_total_article_views(){
			global $wpdb;
			 $total_visits_query = "SELECT
									 COUNT(*) as totalVisits
									 FROM {$wpdb->prefix}hkb_visits
									 WHERE object_type = 'ht_kb_article'
									";
			
			//Article views
			$stats = $wpdb->get_results($total_visits_query);
			return (int) $stats[0]->totalVisits;
		}

		//used in stats dashboard widget
		//@todo - refactor
		function hkbr_get_feedback_overview(){
			global $wpdb;
			$feedback_responses_query = "SELECT COUNT(*) AS totalResponses,
										SUM(CASE WHEN {$wpdb->prefix}" . HT_VOTING_TABLE  .".magnitude > 0 THEN 1 ELSE 0 END) AS totalUp,
										SUM(CASE WHEN {$wpdb->prefix}" . HT_VOTING_TABLE  .".magnitude = 0 THEN 1 ELSE 0 END) AS totalDown
										FROM {$wpdb->prefix}" . HT_VOTING_TABLE  .
										" ";
			//feedback overview
			$stats = $wpdb->get_results($feedback_responses_query);
			$data = $stats[0];

			//hard set the variables
			$data->totalUp = (isset($data->totalUp)) ? $data->totalUp : '-';
			$data->totalDown = (isset($data->totalDown)) ? $data->totalDown : '-';

			return ((int)$data->totalResponses > 0) ? round( ( (int)$data->totalUp / (int)$data->totalResponses )*100 ) : 100;
		}

		/**
		* used in stats dashboard widget
		* @todo - refactor
		* Returns an array of the top search terms
		*/
		function hkbr_get_top_searches($limit=5){
			global $wpdb;

			//limit is one year, though we can look to filter this
			$begin_sql = date('Y-m-d', strtotime('-1 year'));
			$end_sql = date('Y-m-d', time() + DAY_IN_SECONDS );

			//hard cast limit
			$limit = (int) $limit;

			$top_searches_query = "SELECT *, COUNT(*) as count 
									FROM {$wpdb->prefix}hkb_analytics_search_atomic  
									WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
									GROUP BY terms 
									ORDER BY count 
									DESC LIMIT {$limit}
									";
			//top searches
			$top_searches_results = $wpdb->get_results($top_searches_query);
			$rows = array();
			foreach($top_searches_results as $result) {
				$row = array();
				$row['terms'] = $result->terms;
				$row['count'] = $result->count;
				$row['link'] = apply_filters( 'hkb_search_url', $row['terms'] );
				array_push($rows, $row);
			}
			//apply any filters and return
			$rows = apply_filters( 'hkbr_top_searches', $rows );
			return $rows;
		}

		/**
		* AJAX dynamic stats handler
		* request requires
		* 	* aq - action stat
		* 	* begin - begin time stamp
		*   * end - end time stamp
		*   * nonce - security ticket
		*/
		function hkbr_stats() {
			global $wpdb;

			//response object
			$data = array();

			//the main action
			$action = (isset($_REQUEST['aq']) && $_REQUEST['aq']) ? sanitize_text_field ( $_REQUEST['aq'] ) : '';

			$timezone_offset = ( get_option( 'gmt_offset' ) ) ? intval( get_option( 'gmt_offset' ) ) * HOUR_IN_SECONDS : 0;

			$wp_time_format = ( get_option( 'date_format' ) ) ? get_option( 'date_format' ) : 'F j, Y';

			//BEGIN TIMESTAMP
			//santize the period begin timestamp
			$begin = (isset($_REQUEST['begin']) && $_REQUEST['begin']) ? intval( $_REQUEST['begin'] ) : '';
			if(empty($begin)){
				$begin_timestamp = time();
			} else {
				$begin_timestamp = (int) $begin;
			}
			//the sql date needs to be offset by a day for the queries to work
			$begin_offset = apply_filters( 'hkbr_begin_offset', DAY_IN_SECONDS );
			$begin_sql = date('Y-m-d', $begin_timestamp + $begin_offset);
			//beginning user date format
			$begin_user_format = date_i18n( $wp_time_format, $begin_timestamp );

			//END TIMESTAMP
			//sanitize the end period timestamp
			$end = ( isset( $_REQUEST['end']) && $_REQUEST['end'] ) ? intval( $_REQUEST['end'] ) : '';
			if(empty($end)){
				$end_timestamp = time();
			} else {
				$end_timestamp = (int) $end;
			}
			//the sql date needs to be offset by a day for the queries to work
			$end_offset = apply_filters( 'hkbr_end_offset', DAY_IN_SECONDS );
			$end_sql = date('Y-m-d', $end_timestamp + $end_offset);
			//end user date format
			$end_user_format = date_i18n( $wp_time_format, $end_timestamp ); 

			$timestamp_difference = $end_timestamp - $begin_timestamp;
			$days_difference = floor( $timestamp_difference / DAY_IN_SECONDS ); 


			//meta function to populate data object here

			//check check_ajax_referer here

			check_ajax_referer( $action,'wpnonce' );

			//array of possible actions
			$actions = array( 	'updateusermetadates',
								//'kbviewsmonthly',
								'kboverviewmonthly',
								//'newarticlescount',
								//'totalarticles',
								//'articlesperiod',
								//'articlevisits',
								'feedbackoverview',
								'searchesoverview',
								//'newarticles',
								'totalsearches',
								//'articleviewsdetail',
								'searchmonthly',
								'nullsearches',
								'topsearches',
								'feedbackresponses',
								'feedbackitems',
								//'authorstats', //<- currently unused
								'exitsoverview',
								'exitssplit',
								'exitsfromcats',
								'exitsfromarticles',
							);


			if( !in_array( $action , $actions ) ){
				$data['state'] = 'ERROR';
				$data['message'] = 'No valid action';
				wp_send_json_error($data);
				die;
			}

			foreach ($actions as $key => $action_key ) {
				if( $action == $action_key ){
					$data[$action] = $this->fetch_result( $action, $begin_sql, $begin_user_format, $end_sql, $end_user_format, $begin_timestamp, $end_timestamp, $days_difference );
					$data['state'] = 'OK';
					wp_send_json_success($data);
					die;	
				}
				
			}

			$data['state'] = 'ERROR';
			$data['message'] = 'Unable to process request';
			wp_send_json_error($data);
			die;
			
			
			
		} //end get dynamic stats


		function fetch_result( $action, $begin_sql, $begin_user_format, $end_sql, $end_user_format, $begin_timestamp, $end_timestamp, $days_difference ){
			global $wpdb;

			$data = array();

			//switch on action
			switch ($action) {
				case 'updateusermetadates':
					//check_ajax_referer('updateUserMetaDates','nonce');
					$user_ID = get_current_user_id();
					//update meta
					update_user_meta( $user_ID, HT_KB_ANALYTICS_REPORTING_BEGIN_DATE_META_KEY, $begin_timestamp );
					update_user_meta( $user_ID, HT_KB_ANALYTICS_REPORTING_END_DATE_META_KEY, $end_timestamp );
					$active_period = (isset($_REQUEST['period']) && $_REQUEST['period']) ? sanitize_text_field($_REQUEST['period']) : '';
					update_user_meta( $user_ID, HT_KB_ANALYTICS_REPORTING_ACTIVE_PERIOD_META_KEY, $active_period );
					$active_view = (isset($_REQUEST['view']) && $_REQUEST['view']) ? sanitize_text_field($_REQUEST['view']) : '';
					update_user_meta( $user_ID, HT_KB_ANALYTICS_REPORTING_ACTIVE_VIEW_META_KEY, $active_view );
					$data['response'] = 'usermetaset';
					$data['test']= HT_KB_ANALYTICS_REPORTING_BEGIN_DATE_META_KEY;
					$data['begin_timestamp'] = $begin_timestamp;
					$data['end_timestamp'] = $end_timestamp;
					$data['view'] = $active_view;
					$data['uid'] = $user_ID;
					break;
				case 'kbviewsmonthly':
					//check_ajax_referer('monthlyViewsChart','nonce');

					$monthly_kb_views_query = "SELECT count(*) as count, DATE_FORMAT(datetime,'%M') as month, YEAR(datetime) as year 
												FROM {$wpdb->prefix}hkb_visits
												WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
												GROUP BY month, year 
												ORDER BY datetime
												";
					//monthly searches
					$stats = $wpdb->get_results($monthly_kb_views_query);
					$labels = array();
					$values = array();
					foreach($stats as $stat) {
					  array_push($labels, $stat->month);
					  array_push($values, $stat->count);
					}

					$data = array('labels'=>$labels, 'values'=>$values);
					break;
				case 'kboverviewmonthly':
					
					//check_ajax_referer('monthlyKBOverviewChart','nonce');

					$monthly_kb_searches_vs_query =   " SELECT 
															count(*) AS exits, 
															temp.searches AS searches, 
															temp.month as month, 
															temp.year as year
														FROM {$wpdb->prefix}hkb_exits  
														RIGHT JOIN
															(   SELECT count(*) AS searches, 
																{$wpdb->prefix}hkb_analytics_search_atomic.datetime AS datetime, 
																DATE_FORMAT({$wpdb->prefix}hkb_analytics_search_atomic.datetime,'%M') as month, 
																YEAR({$wpdb->prefix}hkb_analytics_search_atomic.datetime) as year 
																FROM {$wpdb->prefix}hkb_analytics_search_atomic 
																WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}' GROUP BY month, year ORDER BY datetime
															) AS temp 
														ON 
															temp.month = DATE_FORMAT({$wpdb->prefix}hkb_exits.datetime,'%M') 
															AND temp.year = YEAR({$wpdb->prefix}hkb_exits.datetime) 
														GROUP BY 
															month, year 
														ORDER BY temp.datetime
													"; 

					$date_kb_searches_vs_query =   " SELECT 
															count(*) AS exits, 
															temp.searches AS searches, 
															temp.dom AS dom
														FROM {$wpdb->prefix}hkb_exits  
														RIGHT JOIN
															(   SELECT count(*) AS searches, 
																{$wpdb->prefix}hkb_analytics_search_atomic.datetime AS datetime,
																DATE_FORMAT({$wpdb->prefix}hkb_analytics_search_atomic.datetime,'%d %b') as dom, 
																YEAR({$wpdb->prefix}hkb_analytics_search_atomic.datetime) as year 
																FROM {$wpdb->prefix}hkb_analytics_search_atomic 
																WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}' GROUP BY dom ORDER BY datetime
															) AS temp 
														ON 
															temp.dom = DATE_FORMAT({$wpdb->prefix}hkb_exits.datetime,'%d %b') 
														GROUP BY 
															dom
														ORDER BY temp.datetime
													";                   
					  

					if(intval($days_difference) < 35){
						//daily stats
						$view_stats = $wpdb->get_results($date_kb_searches_vs_query);
						$labels = array();
						$searches = array();
						$values_transfers = array();
						foreach($view_stats as $view_stat) {
						  array_push($labels, $view_stat->dom);
						  array_push($searches, $view_stat->searches);
						  array_push($values_transfers, $view_stat->exits);
						}
					} else {
						//monthly stats
						$view_stats = $wpdb->get_results($monthly_kb_searches_vs_query);
						$labels = array();
						$searches = array();
						$values_transfers = array();
						foreach($view_stats as $view_stat) {
						  array_push($labels, $view_stat->month);
						  array_push($searches, $view_stat->searches);
						  array_push($values_transfers, $view_stat->exits);
						}
					}                            
					

					$data = array(      'labels' => $labels,
										'datasets' => [
											[	'label' => __('Total Searches', 'ht-knowledge-base'),
												'data' => $searches,
											],
											[	'label' => __('Total Transfers', 'ht-knowledge-base'),
												'data' => $values_transfers,
											],

										], 
										'days_difference' => $days_difference
								);
					break;


				case 'newarticlescount':
					//check_ajax_referer('newArticleStats','nonce');
					
					$begin_query = "SELECT COUNT(*) as beginTotal FROM {$wpdb->prefix}posts
										  WHERE post_date < '{$begin_sql}' AND post_type = 'ht_kb' 
										  ORDER BY post_date";
					$begin_stats = $wpdb->get_results($begin_query);
					$begin_count = $begin_stats[0]->beginTotal;
					$data['begin_count'] = $begin_count;

					$end_query = "SELECT COUNT(*) as endTotal FROM {$wpdb->prefix}posts
										  WHERE post_date < '{$end_sql}'  AND post_type = 'ht_kb' 
										  ORDER BY post_date";
					$end_stats = $wpdb->get_results($end_query);
					$end_count = $end_stats[0]->endTotal;
					$data['end_count'] = $end_count;

					$delta = $end_count-$begin_count;
					$data['count'] = $delta;
					$data['label'] = sprintf(__('Articles published between %s and %s', 'ht-knowledge-base'), $begin_user_format, $end_user_format);
					break;

				case 'totalarticles':
					//check_ajax_referer('totalArticlesStats','nonce');
					$total_articles_query = "SELECT COUNT(*) as articleTotal FROM {$wpdb->prefix}posts
										  WHERE post_date < '{$end_sql}' AND post_type = 'ht_kb' 
										  ORDER BY post_date";
					$article_stats = $wpdb->get_results($total_articles_query);
					$article_total = $article_stats[0]->articleTotal;
					$data['count'] = $article_total;
					$data['label'] = sprintf(__('Articles published before %s', 'ht-knowledge-base'), $end_user_format);
					break;

				case 'articlesperiod':
					//check_ajax_referer('articlesPeriodStats','nonce');
					$articles_in_period = "SELECT COUNT(*) as articleTotal FROM {$wpdb->prefix}posts
										  WHERE post_date > '{$begin_sql}'  AND post_date < '{$end_sql}'  AND post_type = 'ht_kb' 
										  ORDER BY post_date";
					$article_stats = $wpdb->get_results($articles_in_period);
					$article_period = $article_stats[0]->articleTotal;
					$data['count'] = $article_period;
					$data['label'] = sprintf(__('Articles published in this period between %s and %s', 'ht-knowledge-base'), $begin_user_format, $end_user_format);
					break;

				case 'articlevisits':
					//check_ajax_referer('articleViewsStats','nonce');
					
					$total_visits_query = "SELECT
											  COUNT(*) as totalVisits
											 FROM {$wpdb->prefix}hkb_visits
											 WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
											 AND object_type = 'ht_kb_article'
											";
					
					//Article views
					$stats = $wpdb->get_results($total_visits_query);
					$data['count'] = $stats[0]->totalVisits;
					$data['label'] = sprintf(__('Article views between %s and %s', 'ht-knowledge-base'), $begin_user_format, $end_user_format);
					break;

				case 'feedbackoverview':
					//check_ajax_referer('feedbackOverview','nonce');
					$feedback_responses_query = "SELECT COUNT(*) AS totalResponses,
												SUM(CASE WHEN {$wpdb->prefix}" . HT_VOTING_TABLE  .".magnitude > 0 THEN 1 ELSE 0 END) AS totalUp,
												SUM(CASE WHEN {$wpdb->prefix}" . HT_VOTING_TABLE  .".magnitude = 0 THEN 1 ELSE 0 END) AS totalDown
												FROM {$wpdb->prefix}" . HT_VOTING_TABLE  .
												" WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
												";
					//feedback overview
					$stats = $wpdb->get_results($feedback_responses_query);
					$data = $stats[0];

					$data->feedbackArticleSuccess = ((int)$data->totalResponses > 0) ? round( ( (int)$data->totalUp / (int)$data->totalResponses )*100 ) : 100;

					//now hard set the variables
					$data->totalUp = (isset($data->totalUp)) ? number_format_i18n( $data->totalUp ) : '-';
					$data->totalDown = (isset($data->totalDown)) ? number_format_i18n( $data->totalDown ) : '-';

					
					break;

				case 'searchesoverview':
					//check_ajax_referer('searchesOverview','nonce');

					$total_searches_query = "SELECT
											 COUNT(*) as totalSearches,
											 SUM(CASE WHEN {$wpdb->prefix}hkb_analytics_search_atomic.hits > 0 THEN 1 ELSE 0 END) AS totalSuccess,
											 SUM(CASE WHEN {$wpdb->prefix}hkb_analytics_search_atomic.hits = 0 THEN 1 ELSE 0 END) AS totalNull
											 FROM {$wpdb->prefix}hkb_analytics_search_atomic
											 WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
											";
					//total number of searches
					$stats = $wpdb->get_results($total_searches_query);

					$data = $stats[0];

					$data->feedbackSuccess = ((int)$data->totalSearches > 0) ? round( ( (int)$data->totalSuccess / (int)$data->totalSearches )*100 ) : 100;

					//now hard set the variables
					$data->totalSuccess = (isset($data->totalSuccess)) ? number_format_i18n( $data->totalSuccess ) : '-';
					$data->totalNull = (isset($data->totalNull)) ? number_format_i18n( $data->totalNull ) : '-';
					
					break;

				case 'newarticles':
					//check_ajax_referer('articleCount','nonce');
					
					$begin_query = "SELECT COUNT(*) as beginTotal FROM {$wpdb->prefix}posts
										  WHERE post_date < '{$begin_sql}' AND post_type = 'ht_kb' 
										  ORDER BY post_date";
					//begining total
					$begin_stats = $wpdb->get_results($begin_query);
					$begin_count = $begin_stats[0]->beginTotal;
					$data['begin_count'] = $begin_count;

					$end_query = "SELECT COUNT(*) as endTotal FROM {$wpdb->prefix}posts
										  WHERE post_date < '{$end_sql}'  AND post_type = 'ht_kb' 
										  ORDER BY post_date";
					//end total
					$end_stats = $wpdb->get_results($end_query);
					$end_count = $end_stats[0]->endTotal;
					$data['end_count'] = $end_count;

					$delta = $end_count-$begin_count;
					$data['delta'] = $delta;
					$delta_abs = abs($delta);
					$data['delta_abs'] = $delta_abs;
					$delta_direction = ($delta < 0) ? __('down', 'ht-knowledge-base', 'ht-knowledge-base') : __('up', 'ht-knowledge-base', 'ht-knowledge-base');
					$data['delta_direction'] = $delta_direction;
					$percentage_diff = ($begin_count>0) ? $delta_abs / $begin_count: 0;
					$data['percentage_diff'] = number_format($percentage_diff*100, 1);                
					break;

				case 'totalsearches':
					//check_ajax_referer('searchDonut','nonce');

					$total_searches_query = "SELECT datetime,
											  SUM(CASE WHEN {$wpdb->prefix}hkb_analytics_search_atomic.hits > 0 THEN 1 ELSE 0 END) AS totalPopulated,
											  SUM(CASE WHEN {$wpdb->prefix}hkb_analytics_search_atomic.hits = 0 THEN 1 ELSE 0 END) AS totalNULL,
											  COUNT(*) as totalSearches
											 FROM {$wpdb->prefix}hkb_analytics_search_atomic
											 WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
											";
					//total number of searches
					$stats = $wpdb->get_results($total_searches_query);

					$results = $stats[0];

					$data = array( 		'labels' => [ __('Returned Results', 'ht-knowledge-base'), __('No Results', 'ht-knowledge-base') ],
										'datasets' => [ [
											'label' => __('# of Searches', 'ht-knowledge-base'),
											'data' => [ $results->totalNULL, $results->totalPopulated ],
										],
										],
								);
					break;

				case 'articleviewsdetail':
					//check_ajax_referer('articleViewsDetail','nonce');
				   
					$article_views_query = "SELECT *
												FROM {$wpdb->prefix}hkb_visits
												WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
												AND object_type = 'ht_kb_article'
												ORDER BY datetime";
					$stats = $wpdb->get_results($article_views_query);
					$rows = array();
					foreach($stats as $stat) {
						$row = array();
						//article
						$id = $stat->object_id;
						$article_column = '' . get_the_title($id) . ' ' . sprintf('(<a href="%s">%s</a>)', get_permalink($id), __('View', 'ht-knowledge-base', 'ht-knowledge-base')) . ' ' . sprintf('(<a href="%s">%s</a>)', get_edit_post_link($id), __('Edit', 'ht-knowledge-base', 'ht-knowledge-base'));
						array_push($row, $article_column);
						//user
						$user_id = $stat->user_id;
						if($user_id>0){
							//link to user
							$user_info = get_userdata( $user_id );
							$user_ip_column =  sprintf( '<a href="%s">%s</a>', get_edit_user_link($user_id), $user_info->user_nicename );
						} else {
							//ip
							$user_ip_column = $stat->user_ip;
						
						}
						array_push($row, $user_ip_column);
						//duration
						array_push($row, $stat->duration);
						array_push($rows, $row);
					}

					$data['data'] = $rows;
					break;

				case 'searchmonthly':
					//check_ajax_referer('monthlySearchesChart','nonce');

					$monthly_searches_query = "SELECT count(terms) as count, terms, DATE_FORMAT(datetime,'%M') as month, YEAR(datetime) as year 
												FROM {$wpdb->prefix}hkb_analytics_search_atomic
												WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
												GROUP BY month, year 
												ORDER BY datetime
												";
					//monthly searches
					$stats = $wpdb->get_results($monthly_searches_query);
					$labels = array();
					$values = array();
					foreach($stats as $stat) {
					  array_push($labels, $stat->month);
					  array_push($values, $stat->count);
					}

					$data = array( 'labels' => $labels,
										'datasets' => [
											[	'label' => __('Search Volume', 'ht-knowledge-base'),
												'data' => $values
											],
										]
								);

					break;

				case 'nullsearches':
					//check_ajax_referer('nullSearches','nonce');

					$null_searches_query = "SELECT *, COUNT(*) as count 
											FROM {$wpdb->prefix}hkb_analytics_search_atomic 
											WHERE terms != '' AND hits=0 AND datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
											GROUP BY terms 
											ORDER BY count 
											DESC LIMIT 100
											";
					//null searches
					$top_null_results = $wpdb->get_results($null_searches_query);
					$rows = array();
					$counter = 0;
					foreach($top_null_results as $stat) {
						$row = array();
						$row['id'] = $counter;
						$row['searchText'] = htmlentities($stat->terms);
						$row['count'] = intval( $stat->count );
						array_push($rows, $row);
						$counter++;
					}

					$data = $rows;
					break;

				case 'topsearches':
					//check_ajax_referer('topSearches','nonce');

					$top_searches_query = "SELECT *, COUNT(*) as count 
											FROM {$wpdb->prefix}hkb_analytics_search_atomic  
											WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
											GROUP BY terms 
											ORDER BY count 
											DESC LIMIT 100
											";
					//top searches
					$top_searches_results = $wpdb->get_results($top_searches_query);
					$rows = array();
					$counter = 0;
					foreach($top_searches_results as $stat) {
						$row = array();
						$row['id'] = $counter;
						$row['searchText'] = htmlentities($stat->terms);
						$row['count'] = intval( $stat->count );
						array_push($rows, $row);
						$counter++;
					}
					$data = $rows;
					break;

				case 'feedbackresponses':
					//check_ajax_referer('feedbackResponses','nonce');
					
					$feedback_responses_query = "SELECT COUNT(*) AS totalResponses,
												SUM(CASE WHEN {$wpdb->prefix}" . HT_VOTING_TABLE  .".magnitude > 0 THEN 1 ELSE 0 END) AS totalUp,
												SUM(CASE WHEN {$wpdb->prefix}" . HT_VOTING_TABLE  .".magnitude = 0 THEN 1 ELSE 0 END) AS totalDown
												FROM {$wpdb->prefix}" . HT_VOTING_TABLE  .
												" WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
												";
					//feedback responses
					$stats = $wpdb->get_results($feedback_responses_query);
					$results = $stats[0];

					$feedbackGoodWidth = ((int)$results->totalResponses > 0)  ? floor( ( (int)$results->totalUp / (int)$results->totalResponses )*100 ) : 50;
					$feedbackBadWidth = ((int)$results->totalResponses > 0) ? floor( ( (int)$results->totalDown / (int)$results->totalResponses )*100 ) : 50;

					$data['totalVotes'] = number_format_i18n( (int)$results->totalResponses );
					$data['labels'] = array( __( 'Votes', 'ht-knowledge-base' ) );

					$data['rawUp'] = number_format_i18n( (int)$results->totalUp );
					$data['rawDown'] = number_format_i18n( (int)$results->totalDown );

					$data['rawUpPC'] = (int)$feedbackGoodWidth;
					$data['rawDownPC'] = (int)$feedbackBadWidth;

					$data['datasets'] = array (
						array ( 
							'label' => sprintf( __('%s Helpful', 'ht-knowledge-base'), (int)$results->totalUp ),
							'data' => array ( (int)$feedbackGoodWidth )
						),
						array (
							'label' => sprintf( __('%s Unhelpful', 'ht-knowledge-base'), (int)$results->totalDown ),
							'data' => array ( (int)$feedbackBadWidth )
						)
					);

					break;
				
				case 'feedbackitems':
					//check_ajax_referer('feedbackItems','nonce');
					$page = (isset($_REQUEST['page']) && $_REQUEST['page']) ? intval($_REQUEST['page']) : 1;
					//sanitize page
					$page = abs(intval($page));
					$limit = 20;
					$fetch_limit = $limit+1;
					$show = (isset($_REQUEST['show']) && $_REQUEST['show']) ? sanitize_text_field($_REQUEST['show']) : 'all';
					$magnitude_clause = '';
					switch ($show) {
						case 'none': //will show none?
							$magnitude_clause = "magnitude<0";
							break;
						case 'helpful':
							$magnitude_clause = "magnitude>0";
							break;
						case 'unhelpful':
							$magnitude_clause = "magnitude=0";
							break;
						default:
							//default and all
							$magnitude_clause = '1';
							break;
					}

					$comments = (isset($_REQUEST['comments']) && $_REQUEST['comments']) ? $_REQUEST['comments'] : 'all';
					//hard sanitize comments option
					$feedback_clause = ('all' == $comments) ? "1" : "feedback <>  ''" ;

					$timezone_offset = ( get_option( 'gmt_offset' ) ) ? intval( get_option( 'gmt_offset' ) ) * HOUR_IN_SECONDS : 0;

					$order_by =  ( isset($_REQUEST['order_by']) && $_REQUEST['order_by'] ) ? sanitize_text_field($_REQUEST['order_by']) : 'datetime';
					$order =  ( isset($_REQUEST['order']) && 'desc' == $_REQUEST['order'] ) ? 'DESC' : 'ASC';

					$order_by_col = 'datetime';
					switch ($order_by) {
						case 'date':
							$order_by_col = "datetime";
							break;
						case 'rating':
							$order_by_col = "magnitude";
							break;
						case 'article':
							$order_by_col = "post_id";
							break;
						case 'feedback':
							$order_by_col = "feedback";
							break;
						case 'author':
							$order_by_col = "user_id, user_ip";
							break;
						default:
							//default and date
							$order_by_col = 'datetime';
							break;
					}
					

					//order by:- rating, article title, feedback, author, date

					//order DESC or ASC

					//category filter

					//AND datetime > '{$begin_sql}' AND datetime < '{$end_sql}'

					//calculate offset
					$offset = ( $limit * $page ) - $limit;
					$feedback_items_query =    "SELECT * 
												FROM {$wpdb->prefix}" . HT_VOTING_TABLE  .
												" WHERE 1 AND {$feedback_clause} 
												AND {$magnitude_clause}
												AND datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
												ORDER BY {$order_by_col} {$order}
												LIMIT {$fetch_limit} 
												OFFSET {$offset}
												";
					$total_rows_query =    "SELECT count(*) as full_count
												FROM {$wpdb->prefix}" . HT_VOTING_TABLE  .
												" WHERE 1 AND {$feedback_clause} 
												AND {$magnitude_clause}
												AND datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
												ORDER BY {$order_by_col} {$order}
												";
					//recent feedback
					$feedback_items_data = $wpdb->get_results($feedback_items_query);
					$total_rows = 0;
					$items = array();
					foreach($feedback_items_data as $vote_row) {
						$item =  new stdClass();
						$item->rating = ($vote_row->magnitude > 0 ) ?  'helpful' : 'unhelpful';
						$article_id = $vote_row->post_id;
						$item->articleID = $article_id;
						$article_title = get_the_title($article_id);
						$article_post_status = get_post_status($article_id);
						$article_title = ( !$article_post_status ) ? __('No Title or Deleted Article', 'ht-knowledge-base') : get_the_title($article_id);
						$item->articleTitle = $article_title;
						$item->articleEditUrl = get_edit_post_link($article_id);
						$item->articleViewUrl = get_post_permalink($article_id);
						$feedback_body = htmlentities( $vote_row->feedback );
						$truncation_limit = apply_filters( 'hkbr_feedback_truncation_limit', 80 );
						$feedback_snippet = (function_exists('mb_substr')) ? mb_substr($feedback_body, 0, $truncation_limit) : substr($feedback_body, 0, $truncation_limit);
						$item->snippet = esc_html( stripslashes( $feedback_snippet ) );
						$item->fullFeedback = esc_html( stripslashes( $feedback_body ) );
						$item->isTruncated = ($feedback_body!=$feedback_snippet) ? true : false;
						$item->feedbackID = $vote_row->vote_id;
						$feedback_author_id = $vote_row->user_id;
						$item->authorID = $feedback_author_id;
						$feedback_author = get_userdata( $feedback_author_id);
						$item->authorImg = get_avatar( $feedback_author_id, 30 );
						$item->authorName = ($feedback_author) ? $feedback_author->display_name : __('Anonymous', 'ht-knowledge-base');
						$sql_datetime = $vote_row->datetime;
						$datetime_object = new DateTime($sql_datetime);
						//add the WordPress timezone offset
						if($timezone_offset>0){
							$datetime_object->add(new DateInterval('PT'.abs($timezone_offset).'S')); 
						} else {
							$datetime_object->sub(new DateInterval('PT'.abs($timezone_offset).'S')); 
						}                        
						$item->datetime = $datetime_object->format( 'M d Y' )  . ' &middot; ' . $datetime_object->format('G:i') ;
						$item->humantime = sprintf( __('%s ago', 'ht-knowledge-base'), human_time_diff( $datetime_object->format( 'U' ) ) ) ;
						//add item
						array_push($items, $item);
					}

					//total count subquery
					$total_count_data = $wpdb->get_results($total_rows_query);
					if(!$total_rows && is_array($total_count_data) ){
						$total_rows = intval($total_count_data[0]->full_count);    
					}

					//truncate the item list to compute if has_next
					$truncated_items = array_slice($items, 0, $limit);
					$has_next = (count($truncated_items) == count($items)) ? false : true;
					//calculate if has_prev
					$has_prev = ($page==1) ? false : true;
					$data['items'] = $truncated_items;
					$data['totalCount'] = $total_rows;
					$data['page'] = $page;
					$data['pageCount'] = ceil($total_rows/$limit);
					$data['prev'] = $page-1;
					$data['next'] = $page+1;
					$data['hasNext'] = $has_next;
					$data['hasPrev'] = $has_prev;
					break;

				case 'authorstats':
					//currently unused
					//check_ajax_referer('authorStats','nonce');
					$author_stats_query =    "SELECT posts.post_author, 
												COUNT(DISTINCT posts.ID) as articles_published, 
												COUNT(*) as articles_with_votes, 
												SUM(voting.magnitude) as author_score 
												FROM {$wpdb->prefix}posts as posts 
												INNER JOIN  {$wpdb->prefix}" . HT_VOTING_TABLE  .
												" as voting
												ON posts.ID=voting.post_id
												WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
												GROUP BY posts.post_author
												";
					//author stats
					$author_stats_results = $wpdb->get_results($author_stats_query);
					$rows = array();
					foreach($author_stats_results as $author_stats) {
						$row = array();
						//link to user
						$author_id = $author_stats->post_author;
						$author_info = get_userdata( $author_id );
						$author_column =  sprintf( '<a href="%s">%s</a>', get_edit_user_link($author_id), $author_info->user_nicename );
						array_push($row, $author_column);
						array_push($row, $author_stats->articles_published);
						array_push($row, $author_stats->author_score);
						array_push($rows, $row);
					}
					$data['data'] = $rows;
					break;
				//exits table
				case 'exitsoverview':
					//check_ajax_referer('exitsOverview','nonce');
					
					$total_visits_query = "SELECT
											  COUNT(*) as totalVisits
											 FROM {$wpdb->prefix}hkb_visits
											 WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
											";
					$total_exits_query = "SELECT
											  COUNT(*) as totalExits
											 FROM {$wpdb->prefix}hkb_exits
											 WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
											";
					
					//Views
					$stats1 = $wpdb->get_results($total_visits_query);
					//Exits
					$stats2 = $wpdb->get_results($total_exits_query);
					$total_visits = $stats1[0]->totalVisits;
					$total_exits = $stats2[0]->totalExits;
					$exit_percentage = 0;
					//avoid division by 0
					if(is_numeric($total_visits)&&$total_visits>0){
						$exit_percentage = ($total_exits/$total_visits)*100;
						$exit_percentage = round($exit_percentage, 2);
					}
					$data['views'] = number_format_i18n( $total_visits );
					$data['vlabel'] = sprintf(__('Total KB views between %s and %s', 'ht-knowledge-base'), $begin_user_format, $end_user_format);
					$data['exits'] = number_format_i18n( $total_exits );
					$data['elabel'] = sprintf(__('Total KB exits between %s and %s', 'ht-knowledge-base'), $begin_user_format, $end_user_format);
					$data['percentage'] = $exit_percentage;
					$data['plabel'] = sprintf(__('Total KB exits percentage between %s and %s', 'ht-knowledge-base'), $begin_user_format, $end_user_format);
					break;
				case 'exitssplit':
					//check_ajax_referer('exitsDonut','nonce');

					$group_exits_query = " SELECT {$wpdb->prefix}hkb_visits.object_type as objectType, count({$wpdb->prefix}hkb_visits.object_type) AS visits, temp.exits AS exits
													FROM {$wpdb->prefix}hkb_visits
													LEFT JOIN (SELECT object_type, count(*) AS exits FROM {$wpdb->prefix}hkb_exits
													 WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
													 GROUP BY object_type ) AS temp
													ON temp.object_type = {$wpdb->prefix}hkb_visits.object_type
													WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
													AND {$wpdb->prefix}hkb_visits.object_type != 'undefined' 
													GROUP BY {$wpdb->prefix}hkb_visits.object_type
													ORDER BY visits DESC";
					//exit split
					$stats = $wpdb->get_results($group_exits_query);
					$data = $stats;
					$exit_percentage_total = 0;

					$data_exit_counts = array();
					$data_exit_pc = array();
					$data_item_labels = array();
					$data_item_labels_color = array();
					//var_dump($group_exits_query);
					foreach ($data as $key => $data_item) {
						$visits = isset($data_item->visits) ? $data_item->visits : 0;
						$data_item->visits = $visits;
						$exits = isset($data_item->exits) ? $data_item->exits : 0;
						
						//push the count
						$data_exit_counts[] = $exits;

						$exit_percentage = 0;
						//avoid division by 0
						if(is_numeric($visits)&&$visits>0){
							$exit_percentage = ($exits/$visits)*100;
							$exit_percentage = round($exit_percentage, 2);
							$exit_percentage = sprintf('%0.2f', $exit_percentage);

							//push the percentage
							$data_exit_pc[] = $exit_percentage;
						}
						$data_item->exitPercentage = $exit_percentage; 
						switch ($data_item->objectType) {
							case 'ht_kb_archive':
								$data_item_labels[] = __('Archive Exits', 'ht-knowledge-base');
								$data_item_labels_color[] = '#3aadd9';
								break;
							case 'ht_kb_article':
								$data_item_labels[] = __('Article Exits', 'ht-knowledge-base');
								$data_item_labels_color[] = '#35ba9b';
								break;
							case 'ht_kb_category':
								$data_item_labels[] = __('Category Exits', 'ht-knowledge-base');
								$data_item_labels_color[] = '#9579da';
								break;
							
							default:
								$data_item_labels[] = __('Unclassified Exits', 'ht-knowledge-base');
								$data_item_labels_color[] = '#e8553e';
								break;
						}                        
					}

					$data = array( 		'labels' => $data_item_labels,
										'datasets' => [ [
											'label' => __('Number of Exits', 'ht-knowledge-base') ,
											'data' => $data_exit_counts,
											],
										],
								);

					break;

				case 'exitsfromcats':
					//check_ajax_referer('categoryExits','nonce');

					$transfers_from_cats_query = "SELECT {$wpdb->prefix}hkb_visits.object_type, {$wpdb->prefix}hkb_visits.object_id , count({$wpdb->prefix}hkb_visits.object_id) AS visits, temp.exits AS exits
													FROM {$wpdb->prefix}hkb_visits
													LEFT JOIN (SELECT object_type, object_id, count(*) AS exits FROM {$wpdb->prefix}hkb_exits
													 WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
													 GROUP BY object_type, object_id) AS temp
													ON temp.object_type = {$wpdb->prefix}hkb_visits.object_type
													AND temp.object_id = {$wpdb->prefix}hkb_visits.object_id
													WHERE {$wpdb->prefix}hkb_visits.object_type = 'ht_kb_category'
													AND datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
													GROUP BY {$wpdb->prefix}hkb_visits.object_type, {$wpdb->prefix}hkb_visits.object_id
													ORDER BY visits DESC
													LIMIT 100";
					//exits from categories
					$transfers_from_cats = $wpdb->get_results($transfers_from_cats_query);
					$rows = array();
					$counter = 0;
					foreach($transfers_from_cats as $stat) {
						$row = array();
						$row['id'] = $counter;
						$object_id = $stat->object_id;
						$term_obj = get_term($object_id, 'ht_kb_category');
						$name = __('Unknown term', 'ht-knowledge-base');
						if(!is_wp_error($term_obj) && isset($term_obj)){
							$name = $term_obj->name;
						}
						$row['categoryName'] = $name;
						$visits = isset($stat->visits) ? $stat->visits : 0;
						$row['views'] = intval($visits);
						$exits = isset($stat->exits) ? $stat->exits : 0;
						$row['transfers'] = intval($exits);
						$exit_percentage = 0;
						//avoid division by 0
						if(is_numeric($visits)&&$visits>0){
							$exit_percentage = ($exits/$visits)*100;
							$exit_percentage = round($exit_percentage, 2);
							$exit_percentage = sprintf('%0.2f', $exit_percentage);
						}
						$row['transfersPercentage'] = floatval( $exit_percentage );
						array_push($rows, $row);
						$counter++;
					}
					$data = $rows;
					break;

				 case 'exitsfromarticles':
					//check_ajax_referer('articleExits','nonce');

					$transfers_from_articles_query = "SELECT {$wpdb->prefix}hkb_visits.object_type, {$wpdb->prefix}hkb_visits.object_id , count({$wpdb->prefix}hkb_visits.object_id) AS visits, temp.exits AS exits
													FROM {$wpdb->prefix}hkb_visits
													LEFT JOIN (SELECT object_type, object_id, count(*) AS exits FROM {$wpdb->prefix}hkb_exits
													 WHERE datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
													 GROUP BY object_type, object_id) AS temp
													ON temp.object_type = {$wpdb->prefix}hkb_visits.object_type
													AND temp.object_id = {$wpdb->prefix}hkb_visits.object_id
													WHERE {$wpdb->prefix}hkb_visits.object_type = 'ht_kb_article'
													AND datetime > '{$begin_sql}' AND datetime < '{$end_sql}'
													GROUP BY {$wpdb->prefix}hkb_visits.object_type, {$wpdb->prefix}hkb_visits.object_id
													ORDER BY visits DESC
													LIMIT 100";
					//exits from articles
					$transfers_from_articles = $wpdb->get_results($transfers_from_articles_query);
					$rows = array();
					$counter = 0;
					foreach($transfers_from_articles as $stat) {
						$row = array();
						$row['id'] = $counter;
						$object_id = $stat->object_id;
						$post_obj = get_post($object_id);
						//$post_title = __('Deleted article', 'ht-knowledge-base');
						$post_title = sprintf(__('Deleted article %s', 'ht-knowledge-base'), $object_id);
						if(!is_wp_error($post_obj) && isset($post_obj)){
							$post_title = $post_obj->post_title;
						}
						$row['articleName'] = $post_title;
						$visits = isset($stat->visits) ? $stat->visits : 0;
						$row['views'] = $visits;
						$exits = isset($stat->exits) ? $stat->exits : 0;
						$row['transfers'] = $exits;
						$exit_percentage = 0;
						//avoid division by 0
						if(is_numeric($visits)&&$visits>0){
							$exit_percentage = ($exits/$visits)*100;
							$exit_percentage = round($exit_percentage, 2);
							$exit_percentage = sprintf('%0.2f', $exit_percentage);
						}
						$row['transfersPercentage'] = $exit_percentage;
						array_push($rows, $row);
						$counter++;
					}

					$data = $rows;
					break;

				default:
					//nothing here
					break;
			}


			return $data;


		}


		/**
		 * Possible dynamic actions
		 */
		function hkbr_actions(){
			global $wpdb;
			$data = null;
			$action = (isset($_REQUEST['aq']) && $_REQUEST['aq']) ? sanitize_text_field ( $_REQUEST['aq'] ) : '';

			//switch on action
			switch ($action) {
				case 'deletefeedbackitem':
					check_ajax_referer('deletefeedbackitem','wpnonce');
					$vote_id = (isset($_REQUEST['vid']) && $_REQUEST['vid']) ? intval( $_REQUEST['vid'] ) : 0;
					$post_id = (isset($_REQUEST['pid']) && $_REQUEST['pid']) ? intval( $_REQUEST['pid'] ) : 0;

					if( $vote_id > 0 ){
						ht_voting_delete_vote( $vote_id, $post_id );
						$data['success'] = true;
						$data['message'] = sprintf(__('Successfully deleted feedback ID %s', 'ht-knowledge-base' ), $vote_id);
					} else {
						$data['error'] = __('No feedback ID or Post ID set', 'ht-knowledge-base' );
					}
					break;
				default:
					//nothing here
					break;
			}
			wp_send_json_success($data);
			die;
		} //end get dynamic actions
	}

}

if( class_exists( 'HKB_Stats_Server' )) {
	$ht_hkb_dyn_stats_init = new HKB_Stats_Server();
}