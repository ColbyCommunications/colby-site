<?php
/**
* Analytics Reporting v2.0
* More advanced analytics output
* @since 3.10
*
*/

//exit if accessed directly
if ( ! defined( 'ABSPATH' ) ) exit;

if( !class_exists( 'HT_KB_Analytics_Reporting' )) {

	if( !defined('HT_KB_ANALYTICS_REPORTING_MENU_POSITION') ){
		define( 'HT_KB_ANALYTICS_REPORTING_MENU_POSITION', 80 );
	}

	if( !defined('HT_KB_ANALYTICS_REPORTING_PAGE_SLUG') ){
		define( 'HT_KB_ANALYTICS_REPORTING_PAGE_SLUG', 'ht-kb-reporting' );
	}

	if( !defined('HT_KB_ANALYTICS_REPORTING_MAIN_FILE') ){
		define( 'HT_KB_ANALYTICS_REPORTING_MAIN_FILE', __FILE__ );
	}

	if(!defined('HT_KB_ANALYTICS_REPORTING_BEGIN_DATE_META_KEY')){
		define('HT_KB_ANALYTICS_REPORTING_BEGIN_DATE_META_KEY', '_ht_kb_analytics_reporting_begin_date');
	}

	if(!defined('HT_KB_ANALYTICS_REPORTING_END_DATE_META_KEY')){
		define('HT_KB_ANALYTICS_REPORTING_END_DATE_META_KEY', '_ht_kb_analytics_reporting_end_date');
	}

	if(!defined('HT_KB_ANALYTICS_REPORTING_ACTIVE_PERIOD_META_KEY')){
		define('HT_KB_ANALYTICS_REPORTING_ACTIVE_PERIOD_META_KEY', '_ht_kb_analytics_reporting_active_period');
	}

	if(!defined('HT_KB_ANALYTICS_REPORTING_ACTIVE_VIEW_META_KEY')){
		define('HT_KB_ANALYTICS_REPORTING_ACTIVE_VIEW_META_KEY', '_ht_kb_analytics_reporting_active_view');
	}

	if(!defined('HT_KB_ANALYTICS_REPORTING_DISMISS_NEW_PAGE_INFO_KEY')){
		define('HT_KB_ANALYTICS_REPORTING_DISMISS_NEW_PAGE_INFO_KEY', '_ht_kb_analytics_reporting_dismiss_new_page_info');
	}

	class HT_KB_Analytics_Reporting {

	
		function __construct() {
			
			//add custom menu page
			add_action( 'admin_menu',  array( $this, 'ht_kb_analytics_reporting_menu_page' ), HT_KB_ANALYTICS_REPORTING_MENU_POSITION );

			//enqueue react components
			add_action( 'admin_enqueue_scripts', array( $this, 'ht_kb_analytics_reporting_page_scripts_and_styles' ) );

			//new analytics page
			add_action( 'admin_notices', array( $this, 'ht_kb_analytics_reporting_page_new_info' ) );

			//include the server
			include_once('stats-server.php');

		}

		/**
		 * Add the menu
		 */
		function ht_kb_analytics_reporting_menu_page(){
			//check analytics features are supported by the theme
			if(apply_filters('hkb_analytics_supported', true)){
				//add analytics menu page
				add_submenu_page( sprintf( 'edit.php?post_type=%s', 'ht_kb' ), 
					__('Heroic Knowledge Base Analytics', 'ht-knowledge-base'), 
					__('Analytics', 'ht-knowledge-base'), 
					apply_filters( 'hkba_analytics_page_capability', 'manage_options' ), 
					HT_KB_ANALYTICS_REPORTING_PAGE_SLUG, 
					array( $this, 'ht_kb_analytics_reporting_page_callback' ) 
				);
			}
		}

		/**
		 * Page callback and checks
		 * @todo - move the analytics-admin-preview to this module
		 */
		function ht_kb_analytics_reporting_page_callback() {

			//check price ID set, else perform license check
			$hkb_license_price_id = trim( get_option( 'hkb_license_price_id', '' ) );
			if( empty($hkb_license_price_id) && apply_filters( 'ht_kb_perform_license_checks', true ) ){
				//try to check license
				do_action('ht_kb_license_check');
			}

			if( !apply_filters( 'ht_analytics_functions', false ) ){
				$dir = plugin_dir_path( HT_KB_ANALYTICS_MAIN_FILE );
				$preview_page = $dir . 'inc/analytics-admin-preview.php';
				$preview_page = apply_filters( 'ht_analytics_preview_page', $preview_page );
				include( $preview_page );
				return;
			}
			//if it has been > 6hours since we last accessed this page, clear the user meta
			$user_ID = get_current_user_id();
			$last_clear_time = get_user_meta( $user_ID, HT_KB_ANALYTICS_CLEAR_DATE_META_KEY, true );
			//clear after 6 hours
			if( empty( $last_clear_time ) ||  ( $last_clear_time + ( 60*60*6 ) > time() ) ){
				//do nothing
			} else {
				//@todo re-implment ht_hkba_expire_user_dates_meta
				//$this->ht_hkba_expire_user_dates_meta();
			}

			$this->ht_kb_analytics_reporting_page_output();
		}

		/**
		 * Page Output
		 */
		function ht_kb_analytics_reporting_page_output(){
			$can_view = true;
			?>

			<?php if($can_view): ?>
				<?php 
					//enqueue editor scripts and styles
					wp_enqueue_editor();
					do_action( 'enqueue_block_editor_assets' );
				?>
				<div id="ht-kb-analytics-reporting"><?php _e( 'Heroic Knowledge Base Analytics Page loading...', 'ht-knowledge-base' ); ?></div>

			<?php else: ?>

				<div id="ht-kb-analytics-reporting__unauthorised"><?php _e( 'You do not have permission to view this page', 'ht-knowledge-base' ); ?></div>
				
			<?php endif;
		}


		/**
		* Reporting page new info
		*/
		function ht_kb_analytics_reporting_page_new_info() {
			if(is_admin() && function_exists('get_current_screen')){  
					//attempt to get/set user meta
					$user_id = get_current_user_id();
					if( !is_int($user_id) || $user_id < 1 ){
						//early exit
						return;
					}
					$user_dismiss_user_messsage = array_key_exists('dismiss_reporting_page_new_info', $_REQUEST) ? true: false;

					if( $user_dismiss_user_messsage ){
						update_user_meta( $user_id, HT_KB_ANALYTICS_REPORTING_DISMISS_NEW_PAGE_INFO_KEY, true );
						//early exit
						return;
					}

					$user_dismiss_value = get_user_meta( $user_id, HT_KB_ANALYTICS_REPORTING_DISMISS_NEW_PAGE_INFO_KEY, true );

					if( true == $user_dismiss_value ){
						//early exit
						return;
					}

					$screen = get_current_screen();
					if( $screen && defined( 'HT_KB_ANALYTICS_REPORTING_PAGE_SLUG' ) && 'ht_kb_page_'.HT_KB_ANALYTICS_REPORTING_PAGE_SLUG===$screen->base && apply_filters( 'ht_kb_analytics_reporting_page_new_info_notice', true ) ):            
					?>
						<div id="hkba-deprecated-warning" class="notice notice-warning">
							<p><?php printf( __( 'This is a new version of Analytics and Reporting for Heroic Knowledge Base, if you experience any issues, you can continue to use the <a href="%s">old analytics pages here</a>.', 'ht-knowledge-base'), admin_url(  'edit.php?post_type=ht_kb&page=' . 'hkb-analytics' ) ); ?>
								
								<a class="ht-kb-analytics-reporting__dismiss_new_info" href="<?php echo admin_url('edit.php?post_type=ht_kb&page=ht-kb-reporting' . '&dismiss_reporting_page_new_info=1') ?>"><?php _e('Dismiss this message', 'ht-knowledge-base') ?></a>
							</p>
						</div>
					<?php
					endif; 
			} 
		}

		/**
		 * Enqueue scripts and styles
		 */
		function ht_kb_analytics_reporting_page_scripts_and_styles(){
			$screen = get_current_screen();


			if( !$screen || !is_a($screen, 'WP_Screen') ||  'ht_kb_page_' . HT_KB_ANALYTICS_REPORTING_PAGE_SLUG != $screen->id  ){
				return;
			}

			//wp_enqueue_style( 'data-tables-style', plugins_url( '/css/datatables.css',  HT_KB_ANALYTICS_MAIN_FILE  ), array(), HT_KB_VERSION_NUMBER  );


			wp_enqueue_style( 'react-datepicker-style', plugins_url( '/css/react-datepicker.css',  HT_KB_ANALYTICS_MAIN_FILE  ), array(), HT_KB_VERSION_NUMBER  );

			wp_enqueue_style( 'jquery-ui-datepicker' );

			//we leverage our own version of jquery-ui styles
			wp_register_style( 'jquery-ui', plugins_url( '/css/jquery-ui.css', HT_KB_ANALYTICS_MAIN_FILE ), array(), HT_KB_VERSION_NUMBER );
			wp_enqueue_style( 'jquery-ui' );

			//wp-edit-post required as dependancy for leveraging @wordpress/components/Modal
			wp_enqueue_style( 'analytics-admin-style', plugins_url( '/css/analytics.css', HT_KB_ANALYTICS_MAIN_FILE ), array( 'wp-edit-post' ), HT_KB_VERSION_NUMBER );

			$ht_kb_analytics_reporting = (HKB_DEBUG_SCRIPTS) ? 'src/js/ht-kb-analytics-reporting-page.js' : 'dist/js/ht-kb-analytics-reporting-page.min.js';

			//wp_enqueue_script( 'ht-desk-conversations-page-js', plugins_url( $ht_desk_conversations_page_js_src, HT_DESK_MAIN_PLUGIN_FILE ), array(  ), HT_DESK_VERSION_NUMBER, true );	

			//wp_enqueue_script( 'ht-kb-analytics-reporting-js', plugins_url( $ht_kb_analytics_reporting, HT_KB_ANALYTICS_REPORTING_MAIN_FILE ), array( 'jquery', 'wp-element', 'wp-editor', 'wp-api', 'wp-blocks', 'wp-components', 'wp-block-library', 'wp-rich-text', 'wp-tinymce', 'wp-i18n', 'wp-util' ), HT_KB_VERSION_NUMBER, true );


			wp_enqueue_script( 'ht-kb-analytics-reporting-js', plugins_url( $ht_kb_analytics_reporting, HT_KB_ANALYTICS_REPORTING_MAIN_FILE ), array( 'jquery', 'wp-element', 'wp-editor', 'wp-api', 'wp-blocks', 'wp-components', 'wp-block-library', 'wp-rich-text', 'wp-tinymce', 'wp-i18n', 'wp-util' ), HT_KB_VERSION_NUMBER, true );

			wp_enqueue_style( 'wp-block-library' );	

			 //create security loop
			wp_localize_script( 'ht-kb-analytics-reporting-js', 
				'hkbAnalyticsSecurityTokens',
				array(
						'updateusermetadates' => wp_create_nonce( 'updateusermetadates' ),
						'kbviewsmonthly' => wp_create_nonce( 'kbviewsmonthly' ),
						'kboverviewmonthly' => wp_create_nonce( 'kboverviewmonthly' ),
						'newarticlescount' => wp_create_nonce( 'newarticlescount' ),
						'totalarticles' => wp_create_nonce( 'totalarticles' ),
						'articlesperiod' => wp_create_nonce( 'articlesperiod' ),
						'articlevisits' => wp_create_nonce( 'articlevisits' ),
						'feedbackoverview' => wp_create_nonce( 'feedbackoverview' ),
						'searchesoverview' => wp_create_nonce( 'searchesoverview' ),
						'newarticles' => wp_create_nonce( 'newarticles' ),
						'totalsearches' => wp_create_nonce( 'totalsearches' ),
						'articleviewsdetail' => wp_create_nonce( 'articleviewsdetail' ),
						'searchmonthly' => wp_create_nonce( 'searchmonthly' ),
						'nullsearches' => wp_create_nonce( 'nullsearches' ),
						'topsearches' => wp_create_nonce( 'topsearches' ),
						'feedbackresponses' => wp_create_nonce( 'feedbackresponses' ),
						'feedbackitems'  => wp_create_nonce( 'feedbackitems' ),
						'exitsoverview' => wp_create_nonce( 'exitsoverview' ),
						'exitssplit' => wp_create_nonce( 'exitssplit' ),
						'exitsfromcats' => wp_create_nonce( 'exitsfromcats' ),
						'exitsfromarticles' => wp_create_nonce( 'exitsfromarticles' ),

						'deletefeedbackitem' => wp_create_nonce( 'deletefeedbackitem' ),
				) 
			);


			$user_ID = get_current_user_id();

			if( $user_ID && is_int($user_ID) && $user_ID > 0 ){
				//usermeta
				wp_localize_script( 'ht-kb-analytics-reporting-js', 
					'hkbAnalyticsUserMeta',
					array(
							'start' => get_user_meta( $user_ID, HT_KB_ANALYTICS_REPORTING_BEGIN_DATE_META_KEY, true ),
							'end' => get_user_meta( $user_ID, HT_KB_ANALYTICS_REPORTING_END_DATE_META_KEY, true ),
							'period' => get_user_meta( $user_ID, HT_KB_ANALYTICS_REPORTING_ACTIVE_PERIOD_META_KEY, true ),
							'view' => get_user_meta( $user_ID, HT_KB_ANALYTICS_REPORTING_ACTIVE_VIEW_META_KEY, true ),
					) 
				);	
			}

			

		}

	}
}


//Run the Plugin
if( class_exists( 'HT_KB_Analytics_Reporting')) {
	new HT_KB_Analytics_Reporting();
}