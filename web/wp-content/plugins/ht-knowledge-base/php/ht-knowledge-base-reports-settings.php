<?php
/**
* Heroic Knowledge Base Reports settings
*/

//exit if accessed directly
if ( ! defined( 'ABSPATH' ) ) exit;

if( !class_exists( 'HT_KB_Reports_Settings' ) ){
	class HT_KB_Reports_Settings {

		//constructor
		function __construct() {
			
			//settings action (OK?)
			add_action( 'add_ht_kb_settings_page_additional_settings', array( $this, 'ht_kb_reports_settings_section_fields' ) );

			add_action( 'ht_kb_settings_display_additional_sections', array( $this, 'ht_kb_reports_settings_section_display' ) ); 

			//add reports tab
			add_action( 'ht_kb_settings_display_tabs', array( $this, 'ht_kb_reports_settings_tab' ), 4 );

			//add filter
			add_filter( 'ht_knowledge_base_settings_validate', array( $this, 'ht_kb_reports_settings_validate'), 10, 2);

			//settings filters
			add_filter( 'kb_reports_enable', array( $this, 'kb_get_reports_enable'), 10, 1);
			add_filter( 'kb_reports_recipients', array( $this, 'kb_get_reports_recipients'), 10, 1);
			add_filter( 'kb_reports_html', array( $this, 'kb_get_reports_html'), 10, 1);

			//maybe update reports cron based on setting update
			add_action( 'updated_option', array( $this, 'ht_kb_maybe_update_reports_cron' ), 10, 3 );
		}

		/*
		* Test if reports functionality is enabled
		*/
		function ht_kb_display_report_settings_section(){
			//don't run if display disabled
			$ht_kb_license_valid = $this->kb_settings_is_license_status_valid() ? true : false;
			//can be overriden manually, or by theme
			return apply_filters( 'ht_kb_display_report_settings_section', $ht_kb_license_valid );
		}

		function ht_kb_reports_settings_validate($output, $input){
			global $ht_knowledge_base_settings;

			$display_report_settings_section = $this->ht_kb_display_report_settings_section();

			//only permit changes if security field set, otherwise use previous settings

			if( ! isset( $_POST['_ht_kb_reports_settings_security'] ) ||
				! wp_verify_nonce( $_POST['_ht_kb_reports_settings_security'], 'ht_kb_settings_reports_settings_security' ) 
			) {
				//keep previous settings
				$output['kb-reports-enable'] = $ht_knowledge_base_settings['kb-reports-enable'];
				$output['kb-reports-recipients'] = $ht_knowledge_base_settings['kb-reports-recipients'];
				$output['kb-reports-html'] = $ht_knowledge_base_settings['kb-reports-html'];

				return $output;
			} else { 
				//continue
			}

			//kb-reports-enable
			$value =  isset($input['kb-reports-enable']) ? 1 : 0;
			$output['kb-reports-enable'] = $value;

			$old_email_recipients = $ht_knowledge_base_settings['kb-reports-recipients'];
			$new_email_recipients = $input['kb-reports-recipients'];

			//kb-reports-recipients
			if(empty($new_email_recipients)){
				$output['kb-reports-recipients'] = $old_email_recipients;
			} else {
				$santized_email_recipients_string = '';
				$use_old = false;
				$address_array = explode(',', $new_email_recipients );
				foreach ($address_array as $key => $address) {
					$address = trim( $address );
					if( is_email($address) ){
						$santized_email_recipients_string .= $address . ', ';
					} else {
						$use_old = true;
						break;
					}
				}
				if($use_old){
					$output['kb-reports-recipients'] = $old_email_recipients;
				} else {
					$output['kb-reports-recipients'] = $santized_email_recipients_string;
				}
			}

			//kb-reports-html
			$value =  isset($input['kb-reports-html']) ? 1 : 0;
			$output['kb-reports-html'] = $value;

			return $output;
		}

		function ht_kb_reports_settings_section_fields(){

			$display_report_settings_section = $this->ht_kb_display_report_settings_section();			

			if( $display_report_settings_section ){
				add_settings_section('ht_knowledge_base_reports_settings', __('Email Reports', 'ht-knowledge-base'), array($this, 'ht_kb_settings_reports_section_description'), 'ht_kb_settings_reports_section');
				add_settings_field('kb-reports-enable', __('Enable Email Reports', 'ht-knowledge-base'), array($this, 'reports_enable_option_render'), 'ht_kb_settings_reports_section', 'ht_knowledge_base_reports_settings');
				add_settings_field('kb-reports-recipients', __('Report Recipients', 'ht-knowledge-base'), array($this, 'reports_recipients_option_render'), 'ht_kb_settings_reports_section', 'ht_knowledge_base_reports_settings');
				add_settings_field('kb-reports-html', __('Enable HTML Reports', 'ht-knowledge-base'), array($this, 'reports_enable_html'), 'ht_kb_settings_reports_section', 'ht_knowledge_base_reports_settings');
				add_settings_field('kb-reports-preview-dummy', __('Preview Report', 'ht-knowledge-base'), array($this, 'reports_preview'), 'ht_kb_settings_reports_section', 'ht_knowledge_base_reports_settings');
			} 
			do_action( 'ht_kb_settings_set_default', 'kb-reports-enable', false );
			do_action( 'ht_kb_settings_set_default', 'kb-reports-recipients', false );
			do_action( 'ht_kb_settings_set_default', 'kb-reports-html', true );	

		
		}

		function ht_kb_reports_settings_tab(){
			if(apply_filters('hkb_add_reports_settings_section', true)): ?>
				<a href="#reports-section" id="reports-section-link" data-section="reports"><?php _e('Email Reports', 'ht-knowledge-base'); ?></a>
			<?php endif;
		}

		function ht_kb_reports_settings_section_display(){
			if( apply_filters('hkb_add_reports_settings_section', true) ): ?>
				<?php
					/* JS enqueues */

					$display_report_settings_section = $this->ht_kb_display_report_settings_section();
					$suppress_license_disabled_warning = apply_filters( 'ht_kb_reports_suppress_license_warning', false );
				?>   
				<div id="reports-section" class="hkb-settings-section" style="display:none;">
					<?php 
						if( $display_report_settings_section ){
							//no warning required
						} else {
							if( !$suppress_license_disabled_warning ){
								$this->ht_kb_settings_reports_license_disabled_message();
							} else {
								//do nothing?
							}
						}
						do_settings_sections('ht_kb_settings_reports_section');						
					?>   
				</div>
			<?php endif; 
		}


		function ht_kb_settings_reports_section_description(){
			?>
				<div class="hkb-settings-reports-section-start"></div>	

			<?php
				/* important - add field to enable validation */
				wp_nonce_field( 'ht_kb_settings_reports_settings_security', '_ht_kb_reports_settings_security' );
				
		}

		function ht_kb_settings_reports_license_disabled_message(){
			$licenses_and_updates_url = apply_filters( 'ht_kb_display_report_settings_license_entry_link', admin_url( 'edit.php?post_type=ht_kb&page=ht_knowledge_base_settings_page#license-section' ) );

			$license_entry_message = sprintf( __('You must activate your license to enable the reports functionality, please enter and activate your license from the <a href="%s">Licenses and Updates section</a> now.', 'ht-knowledge-base' ), $licenses_and_updates_url );

			echo apply_filters( 'ht_kb_settings_reports_license_disabled_message', $license_entry_message );
			
		}

		function reports_enable_option_render(){
			global $ht_knowledge_base_settings;



			$reports_enable = isset($ht_knowledge_base_settings['kb-reports-enable']) ? $ht_knowledge_base_settings['kb-reports-enable'] : 0; 
			if(!apply_filters('ht_kb_reports_enable_option_render', true)){
				echo apply_filters(
					'ht_kb_reports_enable_option_render',
					esc_attr__( '-', 'ht-knowledge-base' )
				);
				return;
			} ?>
				<input type="checkbox" class="ht-knowledge-base-settings-kb-reports-enable__input"  name="ht_knowledge_base_settings[kb-reports-enable]" value="1" <?php checked( $reports_enable, 1 ); ?> />
				<span class="hkb_setting_desc hkb_setting_desc--inline"><?php _e('Send weekly reports', 'ht-knowledge-base'); ?></span>                
			<?php
		}

		function reports_recipients_option_render(){
			global $ht_knowledge_base_settings;
			$reports_recipients = isset($ht_knowledge_base_settings['kb-reports-recipients']) ? $ht_knowledge_base_settings['kb-reports-recipients'] : ''; 
			if(!apply_filters('ht_kb_reports_recipients_option_render', true)){
				echo apply_filters(
					'ht_kb_reports_recipients_option_render_false',
					esc_attr__( '-', 'ht-knowledge-base' )
				);
				return;
			} ?>
				<input type="text" class="ht-knowledge-base-settings-kb-reports-recipients__input" name="ht_knowledge_base_settings[kb-reports-recipients]" value="<?php esc_attr_e($reports_recipients, 'ht-knowledge-base'); ?>" placeholder="name@example.com"></input>
				<span class="hkb_setting_desc"><?php _e('Email Addresses of recipients, separate multiple addresses with a comma', 'ht-knowledge-base'); ?></span>   
			<?php
		}

		function reports_enable_html(){
			global $ht_knowledge_base_settings;

			$reports_enable = isset($ht_knowledge_base_settings['kb-reports-html']) ? $ht_knowledge_base_settings['kb-reports-html'] : 0;

			if(!apply_filters('ht_kb_reports_enable_option_render', true)){
				echo apply_filters(
					'ht_kb_reports_enable_option_render',
					esc_attr__( '-', 'ht-knowledge-base' )
				);
				return;
			} ?>
				<input type="checkbox" class="ht-knowledge-base-settings-kb-reports-html__input"  name="ht_knowledge_base_settings[kb-reports-html]" value="1" <?php checked( $reports_enable, 1 ); ?> />
				<span class="hkb_setting_desc hkb_setting_desc--inline"><?php _e('Enable HTML format (recommended)', 'ht-knowledge-base'); ?></span>                
			<?php
		}

		function reports_preview(){
			?>
				<a class="button button-primary" href="<?php echo apply_filters( 'ht_kb_reports_preview_page_url', '') ; ?>" target="_blank"><?php _e('Preview Report', 'ht-knowledge-base'); ?></a>
			<?php
		}

		function get_current_page_uri(){
			$uri = isset( $_SERVER['REQUEST_URI'] ) ? esc_url_raw( wp_unslash( $_SERVER['REQUEST_URI'] ) ) : '';
  			$uri = preg_replace( '|^.*/wp-admin/|i', '', $uri );
  			if ( ! $uri ) {
			  return '';
			}

			return remove_query_arg( array( '_wpnonce' ), admin_url( $uri ) );

		}

		function kb_get_reports_enable( $bool ){
			global $ht_knowledge_base_settings;
			$kb_reports_enable = isset($ht_knowledge_base_settings['kb-reports-enable']) ? $ht_knowledge_base_settings['kb-reports-enable'] : 0;

			//hook later to kb_get_reports_enable to override
			//nb. in this implementation we use a filter in kb_settings_is_license_status_valid to override the valid boolean
			$kb_reports_enable = $this->kb_settings_is_license_status_valid() ? $kb_reports_enable : false;

			return (bool) $kb_reports_enable;
		}

		function kb_get_reports_recipients( $string ){
			global $ht_knowledge_base_settings;
			$kb_reports_recipients = isset($ht_knowledge_base_settings['kb-reports-recipients']) ? $ht_knowledge_base_settings['kb-reports-recipients'] : '';

			return (String) $kb_reports_recipients;
		}

		function kb_get_reports_html( $bool ){
			global $ht_knowledge_base_settings;
			$kb_reports_html = isset($ht_knowledge_base_settings['kb-reports-html']) ? $ht_knowledge_base_settings['kb-reports-html'] : 0;

			return (bool) $kb_reports_html;
		}

		function ht_kb_maybe_update_reports_cron( $option_name, $old_value, $option_value  ){

			//this needs additional review to check behaviour
			//this can be filtered to check for any named license key status change
			$license_check_key_name = apply_filters( 'ht_kb_reports_license_status_key_name', 'ht_kb_license_status' );
			if( $license_check_key_name == $option_name ){
				if( $old_value != $option_value ){
					//reset cron
					do_action('ht_kb_setup_reports_cron');
				}
			}

			//setup reports cron action when reports enable value changes
			$kb_settings_key_name = apply_filters( 'ht_kb_reports_settings_key_name', 'ht_knowledge_base_settings' );
			if( $kb_settings_key_name == $option_name ){
				if( array_key_exists('kb-reports-enable', $option_value) || array_key_exists('kb-reports-enable', $old_value) ){
					//if old and new value do not match, reset the reports cron
					if( ( !array_key_exists('kb-reports-enable', $option_value) && array_key_exists('kb-reports-enable', $old_value) ) ||
						( array_key_exists('kb-reports-enable', $option_value) && !array_key_exists('kb-reports-enable', $old_value) ) ||
						( $option_value['kb-reports-enable'] != $old_value['kb-reports-enable'] ) 
					){
						//reset cron
						do_action('ht_kb_setup_reports_cron');
					}
				}
			} 

		}

		function kb_settings_is_license_status_valid(){
			$ht_kb_license_status = get_option('ht_kb_license_status');
			$ht_kb_license_valid = ( 'valid'==$ht_kb_license_status ) ? true : false;
			return apply_filters( 'ht_kb_settings_is_license_status_valid', $ht_kb_license_valid );
		}

	}
}

//run the module
if( class_exists( 'HT_KB_Reports_Settings' ) ){
	new HT_KB_Reports_Settings();
}