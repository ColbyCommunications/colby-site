<?php
/**
 * @package    TGM-Plugin-Activation
 * @subpackage Example
 * @version    2.6.1 for parent theme Ht Theme
 * @author     Thomas Griffin, Gary Jones, Juliette Reinders Folmer
 * @copyright  Copyright (c) 2011, Thomas Griffin
 * @license    http://opensource.org/licenses/gpl-2.0.php GPL v2 or later
 * @link       https://github.com/TGMPA/TGM-Plugin-Activation
 */

/**
 * Include the TGM_Plugin_Activation class.
 *
 * Depending on your implementation, you may want to change the include call:
 *
 * Parent Theme:
 * require_once get_template_directory() . '/path/to/class-tgm-plugin-activation.php';
 *
 * Child Theme:
 * require_once get_stylesheet_directory() . '/path/to/class-tgm-plugin-activation.php';
 *
 * Plugin:
 * require_once dirname( __FILE__ ) . '/path/to/class-tgm-plugin-activation.php';
 */
require_once dirname( __FILE__ ) . '/tgm/class-tgm-plugin-activation.php';

//@todo query this on hook admin_init vs tgmpa_register (setup assistant doesn't work with tgmpa_register)
add_action( 'admin_init', 'ht_kb_plugin_register_required_plugins', 5 );
add_action( 'tgmpa_register', 'ht_kb_plugin_register_required_plugins', 5 );

/**
* Register the required plugins for this theme.
*
*
* This function is hooked into tgmpa_init, which is fired within the
* TGM_Plugin_Activation class constructor.
*/
function ht_kb_plugin_register_required_plugins() {

    /*
     * Array of plugin arrays. Required keys are name and slug.
     * If the source is NOT from the .org repo, then source is also required.
     */
    $plugins = array();


    //Blocks
    if( apply_filters( 'ht_kb_plugin_allow_heroic_blocks_install', true ) ){
      $plugins[] = array(
                    'name'               => 'Heroic Blocks', 
                    'slug'               => 'heroic-blocks', 
                    'description'        => __('Enhance your knowledge base articles presentation with a selection of blocks', 'ht-knowledge-base'),
                    'source'             => dirname( __FILE__ ) . '/tgm/plugins/heroic-blocks-v1.2.3.0.zip', 
                    'required'           => false, 
                    'version'            => '1.2.3', 
                    'force_activation'   => apply_filters( 'ht_heroic_blocks_plugin_force_activation', false ), 
                    'force_deactivation' => apply_filters( 'ht_heroic_blocks_plugin_force_deactivation', false ), 
                    'external_url'       => '', 
                    'is_callable'        => '',
                    'order'              => 1, 
                  );
    }

    //Integrations (pro only)
    if( apply_filters( 'ht_kb_plugin_allow_integrations_install', false ) ){
      $plugins[] = array(
                    'name'               => 'Heroic Knowledge Base Integrations', 
                    'slug'               => 'ht-kb-integrations', 
                    'description'        => __('Required for knowledge base integrations functionality', 'ht-knowledge-base'),
                    'source'             => dirname( __FILE__ ) . '/tgm/plugins/ht-kb-integrations-v1.1.2.0.zip', 
                    'required'           => false, 
                    'version'            => '1.1.2', 
                    'force_activation'   => apply_filters( 'ht_kb_integrations_plugin_force_activation', false ), 
                    'force_deactivation' => apply_filters( 'ht_kb_integrations_plugin_force_deactivation', false ), 
                    'external_url'       => '', 
                    'is_callable'        => '', 
                    'order'              => 2,
                  );
    }

    //Analytics (@todo - move analytics switch to independant plugin? plus and pro only)
    if( apply_filters( 'ht_kb_plugin_allow_analytics_plugin_install', false ) ){
      $plugins[] = array(
                    'name'               => 'Heroic Knowledge Base Analytics Pro', 
                    'slug'               => 'ht-kb-analytics-pro', 
                    'description'        => __('Required for the analytics module', 'ht-knowledge-base'),
                    'source'             => dirname( __FILE__ ) . '/tgm/plugins/ht-kb-analytics-pro-v1.0.0.0.zip', 
                    'required'           => true, 
                    'version'            => '1.0.0', 
                    'force_activation'   => apply_filters( 'ht_kb_analytics_plugin_force_activation', true ), 
                    'force_deactivation' => apply_filters( 'ht_kb_analytics_plugin_force_deactivation', false ), 
                    'external_url'       => '', 
                    'is_callable'        => '', 
                    'order'              => 3,
                  );
    }    


    //Heroic Glossary
    if( apply_filters( 'ht_kb_plugin_allow_heroic_glossary_install', true ) ){
      $plugins[] = array(
                    'name'               => 'Heroic Glossary', 
                    'slug'               => 'heroic-glossary', 
                    'description'        => __('Add a glossary block to your articles or other content', 'ht-knowledge-base'),
                    'required'           => false, 
                    'version'            => '1.1.0', 
                    'force_activation'   => apply_filters( 'ht_glossary_plugin_force_activation', false ), 
                    'force_deactivation' => apply_filters( 'ht_glossary_plugin_force_deactivation', false ), 
                    'external_url'       => '', 
                    'is_callable'        => '', 
                    'order'              => 5,
                  );
    }

    //Heroic ToC
    if( apply_filters( 'ht_kb_plugin_allow_heroic_toc_install', true ) ){
      $plugins[] = array(
                    'name'               => 'Heroic Table of Contents', 
                    'slug'               => 'heroic-table-of-contents',
                    'description'        => __('Add a Table of Contents as a block to your articles', 'ht-knowledge-base'), 
                    'required'           => false, 
                    'version'            => '1.0.2', 
                    'force_activation'   => apply_filters( 'ht_toc_plugin_force_activation', false ), 
                    'force_deactivation' => apply_filters( 'ht_toc_plugin_force_deactivation', false ), 
                    'external_url'       => '', 
                    'is_callable'        => '',
                    'order'              => 6, 
                  );
    } 

    //Hello Dolly Test
    /*
    if( apply_filters( 'ht_kb_plugin_allow_heroic_hello_dolly_install', true ) ){
      $plugins[] = array(
                    'name'               => 'Hello Dolly', 
                    'slug'               => 'hello-dolly', 
                    'description'        => __('The Hello Dolly Plugin, this is just a test so does not need installation', 'ht-knowledge-base'),
                    'source'             => dirname( __FILE__ ) . '/tgm/plugins/hello-dolly.1.7.2.0.zip', 
                    'required'           => false, 
                    'version'            => '1.7.2', 
                    'force_activation'   => apply_filters( 'ht_hello_dolly_plugin_force_activation', false ), 
                    'force_deactivation' => apply_filters( 'ht_hello_dolly_plugin_force_deactivation', false ), 
                    'external_url'       => '', 
                    'is_callable'        => '',
                    'order'              => 7, 
                  );
    }
    */    

  /*
   * Array of configuration settings. Amend each line as needed.
   *
   * TGMPA will start providing localized text strings soon. If you already have translations of our standard
   * strings available, please help us make TGMPA even better by giving us access to these translations or by
   * sending in a pull-request with .po file(s) with the translations.
   *
   * Only uncomment the strings in the config array if you want to customize the strings.
   */
  $config = array(
    'id'           => 'ht-knowledge-base',                 // Unique ID for hashing notices for multiple instances of TGMPA.
    'default_path' => '',                      // Default absolute path to bundled plugins.
    'menu'         => 'tgmpa-install-plugins', // Menu slug.
    'parent_slug'  => 'edit.php?post_type=ht_kb',            // Parent menu slug.
    'capability'   => 'manage_options',    // Capability needed to view plugin install page, should be a capability associated with the parent menu used.
    'has_notices'  => false,                    // Show admin notices or not.
    'dismissable'  => true,                    // If false, a user cannot dismiss the nag message.
    'dismiss_msg'  => '',                      // If 'dismissable' is false, this message will be output at top of nag.
    'is_automatic' => false,                   // Automatically activate plugins after installation or not.
    'message'      => '',                      // Message to output right before the plugins table.

    /*
    'strings'      => array(
      'page_title'                      => __( 'Install Required Plugins', 'knowall' ),
      'menu_title'                      => __( 'Install Plugins', 'knowall' ),
      /* translators: %s: plugin name. * /
      'installing'                      => __( 'Installing Plugin: %s', 'knowall' ),
      /* translators: %s: plugin name. * /
      'updating'                        => __( 'Updating Plugin: %s', 'knowall' ),
      'oops'                            => __( 'Something went wrong with the plugin API.', 'knowall' ),
      'notice_can_install_required'     => _n_noop(
        /* translators: 1: plugin name(s). * /
        'This theme requires the following plugin: %1$s.',
        'This theme requires the following plugins: %1$s.',
        'knowall'
      ),
      'notice_can_install_recommended'  => _n_noop(
        /* translators: 1: plugin name(s). * /
        'This theme recommends the following plugin: %1$s.',
        'This theme recommends the following plugins: %1$s.',
        'knowall'
      ),
      'notice_ask_to_update'            => _n_noop(
        /* translators: 1: plugin name(s). * /
        'The following plugin needs to be updated to its latest version to ensure maximum compatibility with this theme: %1$s.',
        'The following plugins need to be updated to their latest version to ensure maximum compatibility with this theme: %1$s.',
        'knowall'
      ),
      'notice_ask_to_update_maybe'      => _n_noop(
        /* translators: 1: plugin name(s). * /
        'There is an update available for: %1$s.',
        'There are updates available for the following plugins: %1$s.',
        'knowall'
      ),
      'notice_can_activate_required'    => _n_noop(
        /* translators: 1: plugin name(s). * /
        'The following required plugin is currently inactive: %1$s.',
        'The following required plugins are currently inactive: %1$s.',
        'knowall'
      ),
      'notice_can_activate_recommended' => _n_noop(
        /* translators: 1: plugin name(s). * /
        'The following recommended plugin is currently inactive: %1$s.',
        'The following recommended plugins are currently inactive: %1$s.',
        'knowall'
      ),
      'install_link'                    => _n_noop(
        'Begin installing plugin',
        'Begin installing plugins',
        'knowall'
      ),
      'update_link'             => _n_noop(
        'Begin updating plugin',
        'Begin updating plugins',
        'knowall'
      ),
      'activate_link'                   => _n_noop(
        'Begin activating plugin',
        'Begin activating plugins',
        'knowall'
      ),
      'return'                          => __( 'Return to Required Plugins Installer', 'knowall' ),
      'plugin_activated'                => __( 'Plugin activated successfully.', 'knowall' ),
      'activated_successfully'          => __( 'The following plugin was activated successfully:', 'knowall' ),
      /* translators: 1: plugin name. * /
      'plugin_already_active'           => __( 'No action taken. Plugin %1$s was already active.', 'knowall' ),
      /* translators: 1: plugin name. * /
      'plugin_needs_higher_version'     => __( 'Plugin not activated. A higher version of %s is needed for this theme. Please update the plugin.', 'knowall' ),
      /* translators: 1: dashboard link. * /
      'complete'                        => __( 'All plugins installed and activated successfully. %1$s', 'knowall' ),
      'dismiss'                         => __( 'Dismiss this notice', 'knowall' ),
      'notice_cannot_install_activate'  => __( 'There are one or more required or recommended plugins to install, update or activate.', 'knowall' ),
      'contact_admin'                   => __( 'Please contact the administrator of this site for help.', 'knowall' ),

      'nag_type'                        => '', // Determines admin notice type - can only be one of the typical WP notice classes, such as 'updated', 'update-nag', 'notice-warning', 'notice-info' or 'error'. Some of which may not work as expected in older WP versions.
    ),
    */
  );

    tgmpa( $plugins, $config );

}


//add filter to check knowall license version and allow selective install of integrations
//note this is deliberately left easy to override with another filter for environments where it is not possible to check the license
add_filter('ht_kb_plugin_allow_integrations_install', 'ht_kb_plugin_allow_integrations_install_check_license_price_id', 10);

function ht_kb_plugin_allow_integrations_install_check_license_price_id($state){
  $hkb_license_price_id = trim( get_option( 'hkb_license_price_id', '' ) );

  $pro_price_ids = array( '12', '15', '16' );

  if( $hkb_license_price_id && in_array( $hkb_license_price_id, $pro_price_ids ) ){
    return true;
  } else {
    return $state;
  }
}


//add filter to check knowall license version and allow selective install of analytics plugin
//note this is deliberately left easy to override with another filter for environments where it is not possible to check the license
add_filter('ht_kb_plugin_allow_analytics_plugin_install', 'ht_kb_plugin_allow_analytics_plugin_install_check_license_price_id', 10);

function ht_kb_plugin_allow_analytics_plugin_install_check_license_price_id($state){
  $hkb_license_price_id = trim( get_option( 'hkb_license_price_id', '' ) );

  $pro_and_plus_price_ids = array( '4', '5', '6', '7', '8', '9', '10', '11', '12', /*'13', */ '14', '15', '16' );

  if( $hkb_license_price_id && in_array( $hkb_license_price_id, $pro_and_plus_price_ids ) ){
    return true;
  } else {
    return $state;
  }
}
