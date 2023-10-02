<?php
/**
 * Welcome Setup page
 *
 * @package     ht-kb
 * @subpackage  Functions
 * @since       3.3.0
 */

// Exit if accessed directly.
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

// page slug
if ( ! defined( 'HT_KB_WELCOME_SETUP_PAGE' ) ) {
	define( 'HT_KB_WELCOME_SETUP_PAGE', 'ht_kb_welcome_setup_page' );
}

// position
if ( ! defined( 'HT_KB_WELCOME_SETUP_PAGE_POSITION' ) ) {
	define( 'HT_KB_WELCOME_SETUP_PAGE_POSITION', 200 );
}

if ( ! defined( 'HT_KB_JUST_INSTALLED_KEY' ) ) {
	define( 'HT_KB_JUST_INSTALLED_KEY', '_ht_kb_just_installed' );
}

require_once dirname( __FILE__ ) . '/tgm-config.php';

/**
 * Setup_Assistant Page Class
 */
class HT_KB_Welcome_Setup_Page {

	private $ht_kb_settings;

	private $plugin_slug;

	private $tgmpa_url = 'edit.php?post_type=ht_kb';
	private $tgmpa_menu_slug = 'tgmpa-install-plugins';

	/**
	 * Constructor
	 */
	public function __construct() {

		// welcome functionality (hooks into plugin activation)
		add_action( 'admin_init', array( $this, 'ht_kb_welcome' ) );

		// setup assistant page.
		add_action( 'admin_menu', array( $this, 'ht_kb_add_welcome_setup_page_to_admin_menu' ) );

		//remove welcome setup page menu
		add_action( 'admin_head', array( $this, 'ht_kb_remove_welcome_setup_page_from_menu' ) );

		//remove plugin installer page menu
		add_action( 'admin_head', array( $this, 'ht_kb_remove_plugin_installer_page_from_menu' ) );

		//update getting started link
		add_filter( 'ht_kb_getting_started_page_link', array( $this, 'ht_kb_getting_started_page_link' ) );

		//enqueue react components
		add_action( 'admin_enqueue_scripts', array( $this, 'ht_kb_welcome_setup_scripts_and_styles' ) );

		//ajax actions
		add_action( 'wp_ajax_ht_kb_ws_activate_plugin_key', array( $this, 'ajax_activate_plugin_key' ) );
		add_action( 'wp_ajax_ht_kb_ws_deactivate_plugin_key', array( $this, 'ajax_deactivate_plugin_key' ) );

		add_action( 'wp_ajax_ht_kb_ws_set_configuration', array( $this, 'ajax_set_configuration' ) );
		add_action( 'wp_ajax_ht_kb_ws_get_complete_setup_variables', array( $this, 'ajax_get_complete_setup_variables' ) );

		add_action( 'wp_ajax_ht_kb_ws_get_plugins', array( $this, 'get_plugins' ) );
		add_action( 'wp_ajax_ht_kb_ws_setup_plugins', array( $this, 'setup_plugins' ) );

		$this->plugin_slug = 'ht_kb';

	}

	/**
	* Welcome functionality
	*/
	function ht_kb_welcome(){
		//check activation
		if ( ! get_transient( HT_KB_JUST_INSTALLED_KEY ) )
			return;

		//delete the transient
		delete_transient( HT_KB_JUST_INSTALLED_KEY );

		//don't run on multisite
		if ( is_network_admin() || isset( $_GET['activate-multi'] ) )
			return;

		//don't run if show_ht_kb_welcome_on_activation disabled (eg by theme)
		if( ! apply_filters('show_ht_kb_welcome_on_activation', true) )
			return;

		//@todo - we can detect previous versions from the option
		$upgrade = false; // get_option( 'ht_kb_previous_version' );

		if( ! $upgrade ) {
			wp_safe_redirect( admin_url( sprintf( 'edit.php?post_type=%s&page=%s', 'ht_kb', HT_KB_WELCOME_SETUP_PAGE ) ) ); 
			exit;
		} else { 
			wp_safe_redirect( admin_url( sprintf( 'edit.php?post_type=%s&page=%s', 'ht_kb', HT_KB_WELCOME_SETUP_PAGE ) ) ); 
			exit;
		}
	}

	/**
	 * Add to Admin Menu
	 */
	function ht_kb_add_welcome_setup_page_to_admin_menu() {
		//bypass for theme managed updates
		if( current_theme_supports('ht-kb-theme-managed-updates') &&
			apply_filters( 'ht_kb_disable_welcome_setup_page_on_theme_managed_updates', true )
		){
			return;
		}

		//add the page and callback
		add_submenu_page( 'edit.php?post_type=ht_kb', __( 'Setup Assistant', 'ht-knowledge-base' ), __( '##Setup Assistant', 'ht-knowledge-base' ), apply_filters( 'ht_kb_welcome_setup_page_capability', 'manage_options' ), HT_KB_WELCOME_SETUP_PAGE, array( $this, 'welcome_setup_page_callback' ), HT_KB_WELCOME_SETUP_PAGE_POSITION );
	}

	/**
	* Remove welcome menus
	*/
	public function ht_kb_remove_welcome_setup_page_from_menu() {
		remove_submenu_page( 'edit.php?post_type=ht_kb', HT_KB_WELCOME_SETUP_PAGE );
	}

	/**
	* Remove plugins installer menus
	*/
	public function ht_kb_remove_plugin_installer_page_from_menu() {
		remove_submenu_page( 'edit.php?post_type=ht_kb', $this->tgmpa_menu_slug );
	}

	/**
	 * Filter the getting started page link
	 */
	function ht_kb_getting_started_page_link( $link ){
		return sprintf( 'edit.php?post_type=ht_kb&page=%s', HT_KB_WELCOME_SETUP_PAGE );
	}

	/**
	 * Configuration Page Callback
	 */
	function welcome_setup_page_callback() {
			$can_view = true;
			?>

			<?php if($can_view): ?>
				<?php 
					//enqueue editor scripts and styles
					wp_enqueue_editor();
					do_action( 'enqueue_block_editor_assets' );
				?>
				<div id="ht-kb-welcome-setup-page"><?php _e( 'Setup Assistant loading..', 'ht-knowledge-base' ); ?></div>

			<?php else: ?>

				<div id="ht-kb-welcome-setup__unauthorised"><?php _e( 'You do not have permission to view this page', 'ht-knowledge-base' ); ?></div>
				
			<?php endif;
	}

	/**
	 * Enqueue scripts and styles
	 */
	function ht_kb_welcome_setup_scripts_and_styles(){
		$screen = get_current_screen();

		//id = ht_kb_page_ht_kb_welcome_setup_page
		//id = admin_page_ht_kb_welcome_setup_page - no ht_kb cpt capabilities

		if( !$screen || !is_a($screen, 'WP_Screen') || 'ht_kb_page_' . HT_KB_WELCOME_SETUP_PAGE != $screen->id  ){
			return;
		}

		//remove notice transient used since 3.7.0
		delete_transient( HT_KB_RUN_SETUP_ASSISTANT_NOTICE_TRANSIENT );

		//main js
		$ht_kb_welcome_setup_page_js_src = ( HKB_DEBUG_SCRIPTS ) ?  'setup/src/js/ht-kb-welcome-setup-page.js' :  'setup/dist/js/ht-kb-welcome-setup-page.min.js';

		wp_enqueue_script( 'ht-knowledge-base-welcome-setup-page-js', plugins_url( $ht_kb_welcome_setup_page_js_src, HT_KB_MAIN_PLUGIN_FILE ), array( 'jquery', 'wp-element', 'wp-editor', 'wp-api', 'wp-blocks', 'wp-components', 'wp-block-library', 'wp-rich-text', 'wp-tinymce', 'wp-i18n', 'wp-util' ), HT_KB_VERSION_NUMBER, true );

		$articles = get_posts('post_type=' . 'ht_kb' . '&posts_per_page=10');
		$articles_count = count($articles); 
		$articles_installed = ($articles_count>0) ? true : false;

		//sample options
		$kb_sample_options = array();
		$kb_sample_options['default'] = __( 'The default knowledge base sample, a small example of basic structure with a few categories and articles.', 'ht-knowledge-base' );
		$kb_sample_options['demo'] = __( 'Replica of the demo knowledge base site at heroickb.herothemes.com, more detailed with realistic looking content.', 'ht-knowledge-base');
		//apply filters
		$kb_sample_options = apply_filters( 'ht_kb_sample_options', $kb_sample_options );

		//localize script
		$settings_array = array(
			'activatePluginSecurity'  => wp_create_nonce( 'ht_kb_activate_plugin_security' ),
			'deactivatePluginSecurity'  => wp_create_nonce( 'ht_kb_deactivate_plugin_security' ),
			'htkbArticlesInstalled' => $articles_installed,
			'htkbArticlesAdminListUrl' => admin_url('edit.php?post_type=ht_kb'),
			'htkbLicenseKey' => get_option( 'ht_kb_license_key' ),
			'htkbLicenseStatus'  => get_option( 'ht_kb_license_status' ),
			'htkbLicenseAnalytics' => apply_filters( 'ht_analytics_functions', false ),
			'htkbLicenseStatusMessage'  => null, //get_option( 'ht_kb_license_status_message' ),
			'setConfigurationSecurity'  => wp_create_nonce( 'ht_kb_set_configuration_security' ),
			'getCompleteSetupSecurity'  => wp_create_nonce( 'ht_kb_get_complete_setup_variables_security' ),
			'setupPluginsSecurity' => wp_create_nonce( 'ht_kb_setup_plugins_security' ),
			'getPluginsSecurity' => wp_create_nonce( 'ht_kb_get_plugins_security' ),
			'htkbSampleOptions' => $kb_sample_options,
		);
		wp_localize_script( 'ht-knowledge-base-welcome-setup-page-js', 'htkbAPISettings', $settings_array );

		//style
		$ht_kb_welcome_setup_page_style_src = 'setup/dist/css/ht-kb-welcome-setup-style.css';
		wp_enqueue_style( 'ht-knowledge-base-welcome-setup-page-style', plugins_url( $ht_kb_welcome_setup_page_style_src, HT_KB_MAIN_PLUGIN_FILE ), array( 'wp-edit-blocks', 'editor-buttons') , HT_KB_VERSION_NUMBER . '-' . HT_KB_MAIN_PLUGIN_FILE );

		//block library styles
		wp_enqueue_style( 'wp-block-library' );
	}

	/**
	* ajax handler for plugin key activation
	*/
	function ajax_activate_plugin_key() {
		if ( 1 !== check_ajax_referer( 'ht_kb_activate_plugin_security', 'wpnonce', false ) ) {
			wp_send_json_error( array( 'error' => 1, 'message' => esc_html__( 'Failed Security', 'ht-knowledge-base' ) ) );
			exit;
		}

		if ( ! get_transient( $this->plugin_slug . '_license_message', false ) ) {
			set_transient( $this->plugin_slug . '_license_message', HT_Knowledge_Base_Updater::ht_kb_check_license(), ( 60 * 60 * 24 ) );
		}


		//parse and filter input, improved PHP 8 compat.
		$key = filter_input( INPUT_POST, 'key', FILTER_UNSAFE_RAW );
		$key = htmlspecialchars( $key );
		$key = trim( $key );

		$attempt = filter_input( INPUT_POST, 'attempt', FILTER_SANITIZE_NUMBER_INT);


		//if the license key has changed, update it and the activation will be performed automatically, else manually invoke
		$current_key = get_option( $this->plugin_slug . '_license_key', '' );
		$current_key = trim( $current_key );
		if( $current_key != $key ){
			update_option( $this->plugin_slug . '_license_key', $key );	
		} else {
			//activate the new license
			HT_Knowledge_Base_Updater::ht_kb_activate_license();
		}

		$status = get_option( $this->plugin_slug . '_license_status', false );

		$retry = false;

		//response license_valid
		$license_valid = false;

		$analytics = apply_filters( 'ht_analytics_functions', false );

		if('valid'==$status){
			$message = esc_html__('Looks good, sit tight...', 'ht-knowledge-base');
			$license_valid = true;
		} else {
			//workaround for when the license is valid, but has not activated correctly, retry upto three times
			if($attempt < 4){
				$message = esc_html__('Validating license with HeroThemes, please stand by', 'ht-knowledge-base') . sprintf(' (%s)', $attempt);
				$retry = true;
			} else {
				$message = esc_html__('There is a problem with the license key, please check your HeroThemes.com account', 'ht-knowledge-base');			
			}				
		}

		//send response
		wp_send_json_success( 	array( 	'done' => 1, 
										'slug'=> $this->plugin_slug, 
										'valid' => $license_valid, 
										'analytics' => $analytics,
										'message' => $message, 
										'retry' => $retry, 
										'attempt' => $attempt+1 
									) 
							);
		//needed on ajax calls to exit cleanly
		exit;
	}

	/**
	* ajax handler for plugin key deactivation
	*/
	function ajax_deactivate_plugin_key() {
		if ( 1 !== check_ajax_referer( 'ht_kb_deactivate_plugin_security', 'wpnonce', false ) ) {
			wp_send_json_error( array( 'error' => 1, 'message' => esc_html__( 'Failed Security', 'ht-knowledge-base' ) ) );
			exit;
		}

		if ( ! get_transient( $this->plugin_slug . '_license_message', false ) ) {
			set_transient( $this->plugin_slug . '_license_message', HT_Knowledge_Base_Updater::ht_kb_check_license(), ( 60 * 60 * 24 ) );
		}

		//parse and filter input, improved PHP 8 compat.
		$key = filter_input( INPUT_POST, 'key', FILTER_UNSAFE_RAW );
		$key = htmlspecialchars( $key );
		$key = trim( $key );
		
		update_option( $this->plugin_slug . '_license_key', $key );	
		
		$deactivate_license = HT_Knowledge_Base_Updater::ht_kb_deactivate_license();

		if( $deactivate_license ){
			$message = esc_html__('License deactivated successfully', 'ht-knowledge-base');
			//send response
			wp_send_json_success( array( 'done' => 1,  'message' => $message  ) );
			//needed on ajax calls to exit cleanly
			exit;
		} else {
			wp_send_json_error( array( 'error' => 1, 'message' => esc_html__( 'Could not deactivate license', 'ht-knowledge-base' ) ) );
			exit;
		}

	}

	/**
	* install sample content and config 
	*/
	function ajax_set_configuration() {
		if ( 1 !== check_ajax_referer( 'ht_kb_set_configuration_security', 'wpnonce', false ) ) {
			wp_send_json_error( array( 'error' => 1, 'message' => esc_html__( 'Failed Security', 'ht-knowledge-base' ) ) );
			exit;
		}

		//call install sample 

		//get form data 
		//call config options

		//get item to install
		$item = sanitize_key( $_POST['item'] );
		//get the sample to install, else use fault
		$sample = isset( $_POST['sample'] ) ? sanitize_key( $_POST['sample'] ) : 'default';

		$data = false;

		switch ($item) {
			case 'htkbinstallsamplecontent':
				//import sample content
				//@todo - pass sample name parameter
				do_action('ht_kb_import_sample', $sample );
				$data = array( 'installed'=> $item, 'done' => true );
				//remove the import sample data tranient, as we don't need it with this flow
				delete_transient('_import_sample_ht_kb_data');
				break;			
			default:
				//do nothing
				break;
		}



		wp_send_json_success( $data );
		//needed on ajax calls to exit cleanly
		exit;

	}

	/**
	* ajax handler get complete setup variables 
	*/
	function ajax_get_complete_setup_variables() {
		if ( 1 !== check_ajax_referer( 'ht_kb_get_complete_setup_variables_security', 'wpnonce', false ) ) {
			wp_send_json_error( array( 'error' => 1, 'message' => esc_html__( 'Failed Security', 'ht-knowledge-base' ) ) );
			exit;
		}

		$articles = get_posts('post_type=ht_kb&posts_per_page=10');
		$article_count = count($articles);
		$has_articles = $article_count > 0;

		$data = array(
			'defaultKBArchiveUrl' => get_permalink( ht_kb_get_kb_archive_page_id( 'default' ) ),
			'hasArticles' => $has_articles,
			'createKBArticleUrl' => admin_url('post-new.php?post_type=ht_kb'),
			'createKBCategoryUrl' => admin_url('edit-tags.php?taxonomy=ht_kb_category&post_type=ht_kb'),
			'createKBTagUrl' => admin_url('edit-tags.php?taxonomy=ht_kb_tag&post_type=ht_kb'),
			'htKBSettingsPageUrl' => admin_url('edit.php?post_type=ht_kb&page=ht_knowledge_base_settings_page'),
			'searchWordPressHTGuideUrl' => HT_SEARCH_IN_WORDPRESS_GUIDE_URL,
			'htKBIntegrationGuideUrl' => HT_HKB_INTEGRATION_GUIDE_URL,
		);

		wp_send_json_success( $data );
		//needed on ajax calls to exit cleanly
		exit;

	}



	/**
	* ajax handler for plugin installation
	*/
	function setup_plugins() {

		if ( ! check_ajax_referer( 'ht_kb_setup_plugins_security', 'wpnonce' )  ) {
			wp_send_json_error( array( 'error' => 1, 'message' => esc_html__( 'Failed Security', 'ht-knowledge-base' ) ) );
		}

		//current plugin item we are processing
		$plugin_item = isset( $_POST['slug'] ) ? $_POST['slug'] : false;

		if ( empty( $plugin_item ) ) {
			wp_send_json_error( array( 'error' => 1, 'message' => esc_html__( 'Missing plugin slug', 'ht-knowledge-base' ) ) );
		}

		//default json response
		$json = array();
		//get tgm plugin config
		$plugins = $this->get_tgm_config_plugins();
		// what are we doing with this plugin?
		foreach ( $plugins['activate'] as $slug => $plugin ) {
			if ( $plugin_item == $slug ) {
				$json = array(
					'url'           => admin_url( $this->tgmpa_url ),
					'plugin'        => array( $slug ),
					'tgmpa-page'    => $this->tgmpa_menu_slug,
					'plugin_status' => 'all',
					'_wpnonce'      => wp_create_nonce( 'bulk-plugins' ),
					'action'        => 'tgmpa-bulk-activate',
					'action2'       => - 1,
					'message'       => esc_html__( 'Activating Plugin', 'ht-knowledge-base' ),
				);
				break;
			}
		}
		foreach ( $plugins['update'] as $slug => $plugin ) {
			if ( $plugin_item == $slug ) {
				$json = array(
					'url'           => admin_url( $this->tgmpa_url ),
					'plugin'        => array( $slug ),
					'tgmpa-page'    => $this->tgmpa_menu_slug,
					'plugin_status' => 'all',
					'_wpnonce'      => wp_create_nonce( 'bulk-plugins' ),
					'action'        => 'tgmpa-bulk-update',
					'action2'       => - 1,
					'message'       => esc_html__( 'Updating Plugin', 'ht-knowledge-base' ),
				);
				break;
			}
		}
		foreach ( $plugins['install'] as $slug => $plugin ) {
			if ( $plugin_item == $slug ) {
				$json = array(
					'url'           => admin_url( $this->tgmpa_url ),
					'plugin'        => array( $slug ),
					'tgmpa-page'    => $this->tgmpa_menu_slug,
					'plugin_status' => 'all',
					'_wpnonce'      => wp_create_nonce( 'bulk-plugins' ),
					'action'        => 'tgmpa-bulk-install',
					'action2'       => - 1,
					'message'       => esc_html__( 'Installing Plugin', 'ht-knowledge-base' ),
				);
				break;
			}
		}

		if ( !empty($json) ) {
			$json['hash'] = md5( serialize( $json ) ); // used for checking if duplicates happen, move to next plugin
			wp_send_json( $json );
		} else {
			wp_send_json( array( 'done' => 1, 'message' => esc_html__( 'Success', 'ht-knowledge-base' ) ) );
		}
		exit;

	}

	/**
	* Get TGM config plugins
	*/
	function get_tgm_config_plugins() {
		$instance = call_user_func( array( get_class( $GLOBALS['tgmpa'] ), 'get_instance' ) );
		$plugins  = array(
			'all'      => array(), // Meaning: all plugins which still have open actions.
			'install'  => array(),
			'update'   => array(),
			'activate' => array(),
		);

		foreach ( $instance->plugins as $slug => $plugin ) {
			if ( $instance->is_plugin_active( $slug ) && false === $instance->does_plugin_have_update( $slug ) ) {
				// No need to display plugins if they are installed, up-to-date and active.
				continue;
			} else {
				$plugins['all'][ $slug ] = $plugin;

				if ( ! $instance->is_plugin_installed( $slug ) ) {
					$plugins['install'][ $slug ] = $plugin;
				} else {
					if ( false !== $instance->does_plugin_have_update( $slug ) ) {
						$plugins['update'][ $slug ] = $plugin;
					}

					if ( $instance->can_plugin_activate( $slug ) ) {
						$plugins['activate'][ $slug ] = $plugin;
					}
				}
			}
		}

		return $plugins;
	}

	/**
	* Get the optional and required plugins
	*/
	function get_plugins() {

		if ( ! check_ajax_referer( 'ht_kb_get_plugins_security', 'wpnonce' )  ) {
			wp_send_json_error( array( 'error' => 1, 'message' => esc_html__( 'Failed Security', 'ht-knowledge-base' ) ) );
		}

		$instance = call_user_func( array( get_class( $GLOBALS['tgmpa'] ), 'get_instance' ) );
		$plugins  = array(
			'all'      => array(),
			'required'  => array(),
			'optional'   => array(),
		);

		foreach ( $instance->plugins as $slug => $plugin ) {
			
			if ( $instance->is_plugin_active( $slug ) && false === $instance->does_plugin_have_update( $slug ) ) {
				//plugin installed, up-to-date and active.
				$plugin['is_installed'] = true;
				$plugin['update_required'] = false;
				$plugin['activation_required'] = false;
				//continue;
			} else {
				if ( ! $instance->is_plugin_installed( $slug ) ) {
					$plugin['is_installed'] = false;
				} else {
					$plugin['is_installed'] = true;
					if ( false !== $instance->does_plugin_have_update( $slug ) ) {
						$plugin['update_required'] = true;
					} else {
						$plugin['update_required'] = false;
					}
					if ( $instance->can_plugin_activate( $slug ) ) {
						$plugin['activation_required'] = true;
					} else {
						$plugin['activation_required'] = false;
					}
				}
			}


			//add to all
			$plugins['all'][] = $plugin;

			if ( true === $plugin['required'] ) {
				$plugins['required'][] = $plugin;
			} else {
				$plugins['optional'][] = $plugin;
			}			
		}

		wp_send_json_success( array ( 'plugins' => $plugins ) );
		exit;
	}



}


if ( class_exists( 'HT_KB_Welcome_Setup_Page' ) ) {
	// run module
	new HT_KB_Welcome_Setup_Page();
}