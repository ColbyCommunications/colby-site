<?php
/**
* Dismiss Notices
* Controler for dimiss notices functionality
*/

//exit if accessed directly
if ( ! defined( 'ABSPATH' ) ) exit;

if( !class_exists( 'HT_KB_Dismiss_Notices' ) ){

	//option prefix
	if(!defined( 'HT_KB_DISMISSABLE_NOTICE_OPTION_PREFIX' ) ){
		define( 'HT_KB_DISMISSABLE_NOTICE_OPTION_PREFIX', 'ht-kb-dismiss-');
	}

	class HT_KB_Dismiss_Notices {

		//constructor
		function __construct() {
			//add scripts and styles
			add_action( 'ht_kb_enqueue_dismiss_notices', array( $this, 'enqueue_dismiss_notices' ) );

			//ajax handler
			add_action( 'wp_ajax_ht_kb_ajax_notice_dismiss', array( $this, 'ajax_notice_dismiss' ) );

			//valid notices filter (ensures only registered notices can be dismissing), example function
			add_filter( 'ht_kb_dismissable_notices', array( $this, 'dismissable_notices' ) );

		}

		/**
		 * Enqueue scripts
		 */
		function enqueue_dismiss_notices(){
			$hkb_dismiss_notices_js_src = (HKB_DEBUG_SCRIPTS) ? 'js/hkb-admin-dismiss-notices-js.js' : 'js/hkb-admin-dismiss-notices-js.min.js';
			wp_enqueue_script( 'hkb-admin-dismiss-notices-script', plugins_url( $hkb_dismiss_notices_js_src, dirname( __FILE__ ) ), array('jquery'), HT_KB_VERSION_NUMBER, true );

			$security = wp_create_nonce('ht-kb-admin-dismiss-notices');
			wp_localize_script( 'hkb-admin-dismiss-notices-script', 'hkbDismissNoticesSettings', array( 'security' => $security ) );
		}

		/**
		 * Ajax dismiss notices callback
		 */
		function ajax_notice_dismiss(){
			//check security
			check_ajax_referer( 'ht-kb-admin-dismiss-notices', 'security' );

			//get the notice id
			$notice = sanitize_text_field( $_POST['notice'] );

			//early return if empty notice id
			if( empty( $notice ) ){
				wp_send_json_error( array( 'error'=>'notice_missing', 'notice'=>$notice  ) );
				exit;
			}

			//valid dismissable notices
			$valid_dismissable_notices = apply_filters( 'ht_kb_dismissable_notices', array() );

			//return if notice not registered
			if( !in_array( $notice, $valid_dismissable_notices ) ){
				wp_send_json_error( array( 'error'=>'notice_not_registered', 'notice'=>$notice, 'valid'=>$valid_dismissable_notices ) );
				exit;
			}

			//update option (more flexible than update_user_meta)
			update_option( HT_KB_DISMISSABLE_NOTICE_OPTION_PREFIX . $notice, 1 );

			//send success response
			wp_send_json_success( array( 'message'=>'dismissed', 'notice'=>$notice ) );
			exit;
		}

		/**
		 * Example of how to use the ht_kb_dismissable_notices filter
		 */
		function dismissable_notices( $notices_array ){
			//example application 
			//$notices_array[] = 'my-notices';
			return $notices_array;
		}


	}
}

//run the module
if( class_exists( 'HT_KB_Dismiss_Notices' ) ){
	new HT_KB_Dismiss_Notices();
}