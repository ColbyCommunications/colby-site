<?php
/**
* Heroic Knowledge Base weekly reports
*/

// exit if accessed directly
if ( ! defined( 'ABSPATH' ) ) exit;

// page slug
if ( ! defined( 'HT_KB_REPORTS_PREVIEW_PAGE' ) ) {
	define( 'HT_KB_REPORTS_PREVIEW_PAGE', 'ht_kb_reports_preview_page' );
}

if( !class_exists( 'HT_KB_Reports' ) ){
	class HT_KB_Reports {

		//constructor
		function __construct() {
			//cron setup
			register_activation_hook( HT_KB_MAIN_PLUGIN_FILE, array( $this, 'ht_kb_setup_reports_cron' ) );

			//cron hook
			add_action( 'ht_kb_reports_cron', array( $this, 'send_reports' ) );

			//run hook to send email
			add_action( 'ht_kb_send_reports', array( $this, 'send_reports' ), 10, 1 );

			//preview page
			add_action( 'admin_menu', array( $this, 'ht_kb_reports_preview_page') );

			//preview page url filter
			add_filter( 'ht_kb_reports_preview_page_url', array( $this, 'ht_kb_reports_preview_page_url') );

			//update cron on ht_kb_setup_reports_cron
			add_action( 'ht_kb_setup_reports_cron', array( $this, 'ht_kb_setup_reports_cron' ) );
		}

		function ht_kb_setup_reports_cron(){
			wp_clear_scheduled_hook( 'ht_kb_reports_cron' );
			//add a weekly cron job, note if this is changed, the cron job will need deleting and re-creating with new frequency
			if ( ! wp_next_scheduled( 'ht_kb_reports_cron' ) ) {
				$schedule = apply_filters('ht_kb_reports_cron_frequency', 'weekly');
				wp_schedule_event( time(), $schedule, 'ht_kb_reports_cron' );
			}
		}


		/**
		 * Send Heroic Knowledge Base reports
		 */
		function send_reports(){
			
			$user_kb_reports_enable = apply_filters( 'kb_reports_enable', true );

			$kb_reports_functionality_enabled = apply_filters('ht_kb_reports_functionality_enabled', true );

			$send_reports = $user_kb_reports_enable && $kb_reports_functionality_enabled;

			//if send reports is false, return
			if( !$send_reports ){
				return;
			}

			//html format setting
			$html_format = apply_filters( 'kb_reports_html', true );
			if( $html_format ){
				add_filter( 'wp_mail_content_type', array( $this, 'set_html_format' ) );
			}

			//compute recipients
			$recipients_csv = apply_filters( 'kb_reports_recipients', '' );
			$recipient_array = array();
			$raw_recipients_array = explode( ',',  $recipients_csv );
			foreach ($raw_recipients_array as $key => $receipient_email_raw ) {
				$email = trim( $receipient_email_raw );
				if( is_email( $email ) ){
					$recipient_array[] = $email;
				}
			}
			//if we're left with an empty array, return
			if(sizeof($recipient_array) < 1 ){
				return;
			}
			//set the to field
			$to = apply_filters( 'ht_kb_send_reports_to', $recipient_array );

			//subject
			$default_subject = sprintf ( __('Your Weekly Knowledge Base Report for %s', 'ht-knowledge-base'),  get_bloginfo('name') );
			$subject = apply_filters( 'ht_kb_send_reports_subject', $default_subject );

			//dummy content
			$message = 'Something went wrong fetching the report file template';

			$template_file = hkb_locate_template( apply_filters( 'ht_kb_report_template_file', 'report-template-default' ) );

			//check template file exists
			if( !file_exists( $template_file ) ){
				return;
			}

			ob_start();
			//main content
			@include_once( $template_file );
			//styles
			$this->output_report_styles();
			$message = apply_filters( 'ht_kb_send_reports_message', ob_get_clean() );
			//possible use with CC / BCC?
			$headers = apply_filters( 'ht_kb_send_reports_headers', array() );
			//possible later use with PDF reports?
			$attachments = apply_filters( 'ht_kb_send_reports_recipient_attachments', array() );
			wp_mail( $to, $subject, $message, $headers, $attachments );

			//disable html allow filter
			remove_filter( 'wp_mail_content_type', array( $this, 'set_html_format' ) );
		}

		function set_html_format( $format ){
			return 'text/html';
		}

		function ht_kb_reports_preview_page_url( $url ){
			return sprintf( 'edit.php?post_type=ht_kb&page=%s', HT_KB_REPORTS_PREVIEW_PAGE );
		} 

		function ht_kb_reports_preview_page(){
			//add submenu page
			add_submenu_page( 'edit.php?post_type=ht_kb', __( 'Heroic Knowledge Base Report Preview', 'ht-knowledge-base' ), __( 'Heroic Knowledge Base Report Preview', 'ht-knowledge-base'), apply_filters( 'ht_kb_reports_preview_page_capability', 'manage_options' ), HT_KB_REPORTS_PREVIEW_PAGE, array( $this, 'ht_kb_reports_preview_page_callback' ), 1000 );

			//remove submenu page, passing null as parent slug no longer supported in PHP8 environments
            remove_submenu_page( 'edit.php?post_type=ht_kb', HT_KB_REPORTS_PREVIEW_PAGE );
		}

		function ht_kb_reports_preview_page_callback(){
			?>
				<div class="wrap">
					<h2><?php printf( __('Preview of Knowledge Base Report for %s', 'ht-knowledge-base'), get_bloginfo('name') ) ; ?></h2>
					<?php $this->display_report(); ?>
				</div>
			<?php
		}

		function display_report(){
			$template_file = hkb_locate_template( apply_filters( 'ht_kb_report_template_file', 'report-template-default' ) );

			if( !file_exists( $template_file ) ){
				return;
			}

			include_once( $template_file );

			$this->output_report_styles();
			
		}

		function output_report_styles(){
			$css_file_location = apply_filters( 'ht_kb_reports_css_file_location', dirname(HT_KB_MAIN_PLUGIN_FILE) . DIRECTORY_SEPARATOR . 'css' . DIRECTORY_SEPARATOR . 'hkb-style-reports.css' );

			?>
				<style type="text/css">				 	
					<?php include_once( $css_file_location ); ?>
				</style>
			<?php
		}




	}
}

//run the module
if( class_exists( 'HT_KB_Reports' ) ){
	new HT_KB_Reports();
}