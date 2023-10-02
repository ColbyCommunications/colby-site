<?php
/**
* Knowledge Base Sample Importer
*/

//exit if accessed directly
if ( ! defined( 'ABSPATH' ) ) exit;

if (!class_exists('HT_Knowledge_Base_Sample_Importer')) {

	class HT_Knowledge_Base_Sample_Importer {

		private $media_installed;
		private $categories_installed_count;
		private $articles_installed_count;
		private $settings_installed_count;

		private $settings_cache;

		private $install_errors;

		//constructor
		function __construct(){
			//@todo to review - multisite compatibility?
			add_action( 'admin_head', array( $this, 'ht_kb_installer_actions' ) );
			add_action( 'admin_notices', array( $this, 'admin_notices' ) );

			//independant action hook, so we can install content via ajax callback
			add_action( 'ht_kb_import_sample', array( $this, 'ht_kb_import_sample' ) );

			//ht_kb_sample_media_url action (param - key)
			add_action( 'ht_kb_sample_media_url', array( $this, 'ht_kb_sample_media_url'), 10, 1 );

			//set install counts
			$this->media_installed = array();
			$this->categories_installed_count = 0;
			$this->articles_installed_count = 0;
			$this->settings_installed_count = 0;

			$this->install_errors = [];
		}

		/**
		* Admin notices
		* Displays sample data import information and any error information
		*/
		function admin_notices(){
			if('removed_ht_kb_data' == get_transient('_removed_ht_kb_data')){
				 delete_transient('_removed_ht_kb_data');
				 ?>
					<div class="notice notice-info">
						<p><?php _e( 'Knowldge Base Data Removed', 'ht-knowledge-base' ); ?></p>
					</div>
				<?php
			}
			if('import_sample_ht_kb_data' == get_transient('_import_sample_ht_kb_data')){
				 delete_transient('_import_sample_ht_kb_data');
				 ?>
					<div class="notice notice-info">
						<p><?php printf( __( 'Knowldge Base Sample Data Imported (%d Categories and %d Articles added)', 'ht-knowledge-base' ), $this->categories_installed_count, $this->articles_installed_count ); ?></p>
					</div>
				<?php

				//loop any errors
				foreach ($this->install_errors as $key => $error ):
				?>
					<div class="notice notice-error">
						<p><strong><?php _e( 'KB Import Error:', 'ht-knowledge-base' ); ?></strong> <?php echo $error->get_error_message(); ?></p>
					</div>
				<?php

				endforeach;

			}
		}

		/**
		* Main actions
		*/
		function ht_kb_installer_actions(){
			//@todo - add security
			if($_GET && is_array($_GET) && array_key_exists( 'ht_kb_importer', $_GET )){
				if($_GET['ht_kb_importer'] == 'delete_kb_data'){
					//check security
					check_admin_referer( 'delete-ht-kb-data' );
					//remove all knowledge base data
					$this->remove_all_ht_kb_data();
					//set transient to display message that data removed
					set_transient('_removed_ht_kb_data', 'removed_ht_kb_data');
				}
				//install sample - eg, https://develop.local/wp-admin/edit.php?post_type=ht_kb&ht_kb_importer=import_sample
				if($_GET['ht_kb_importer'] == 'import_sample'){
					//check security
					check_admin_referer( 'import-sample-ht-kb-data' );
					$sample_name = 'default';
					//$sample_name = 'demo';
					$this->ht_kb_import_sample( $sample_name );
				}
			}
		}

		/**
		 * Action hook installer
		 */
		function ht_kb_import_sample( $sample_name = 'default' ){
			//security is handled by the either the setup assistant before the ht_kb_import_sample action, or prior to the functional call.

			//check we're not handed an empty sample_name, otherwise reset to default
			$sample_name = empty( $sample_name ) ? 'default' : $sample_name;
			
			$folder_json_path = dirname( HT_KB_MAIN_PLUGIN_FILE ) . DIRECTORY_SEPARATOR . 'samples' . DIRECTORY_SEPARATOR . $sample_name . DIRECTORY_SEPARATOR;

			//apply filters
			$folder_json_path = apply_filters( 'ht_kb_import_sample_folder_json_path', $folder_json_path, $sample_name );

			//check folder exits or return error
			$folder_exists = file_exists( $folder_json_path );

			//media
			$this->ht_kb_install_media( $folder_json_path );

			//categories
			$this->ht_kb_install_categories( $folder_json_path );

			//articles
			$this->ht_kb_install_articles( $folder_json_path );

			//settings
			$this->ht_kb_install_settings( $folder_json_path );

			//set transient to display message that sample was import
			set_transient( '_import_sample_ht_kb_data', 'import_sample_ht_kb_data' );
		}

		function ht_kb_install_media( $folder_json_path ){
			$media_json_path = $folder_json_path . 'media.json';

			//apply filters
			$media_json_path = apply_filters( 'ht_kb_install_media_media_json_path', $media_json_path );

			if( !file_exists( $media_json_path ) ){
				$error_message = sprintf( __( 'Media JSON file %s not found', 'ht-knowledge-base' ), $media_json_path );
				$this->install_errors[] = new WP_Error( 'file_not_found', $error_message );
				return false;	
			}			

			//get the json file contents			
			$media_json = file_get_contents( $media_json_path );
 
 			//decode json contents
			$media_decoded_json = json_decode( $media_json, false );

			//if media_decoded_json returns null, it's not proper json and should return error
			if( empty( $media_decoded_json) ){
				//throw new WP_Error, json format invalid
				$error_message = sprintf( __( 'JSON format of %s is invalid', 'ht-knowledge-base' ), $media_json_path );
				$this->install_errors[] = new WP_Error( 'invalid_json', $error_message );
				return false;
			}

			//check the media property exists
			$media = property_exists( $media_decoded_json, 'media') ? $media_decoded_json->media : [];
			if( empty( $media ) ){
				//no media, return error
				$error_message =  __( 'No media found in media.json', 'ht-knowledge-base' );
				$this->install_errors[] = new WP_Error( 'invalid_json', $error_message );
				return false;
			}

			//loop media 
			foreach ( $media_decoded_json->media as $key => $media ) {
				//install media and increment counter, or append to errors
				$install_media_result = $this->ht_kb_install_media_item( $media, $folder_json_path );
				if( is_a( $install_media_result, 'WP_Error' ) ){
					$this->install_errors[] = $install_media_result;
				} elseif ( true == $install_media_result ) {
					//$this->media_installed_count += 1;
					//no action required
				}
			}
		}

		/**
		 * $media
		 * Upload a media item 
		 * @return attachment_id || WP_Error
		 */
		function ht_kb_install_media_item( $media, $path ){

			$key = $media->key;

			//slug defaults to the sanitize_title value, but this is filterable with ht_kb_install_media_slug
			$key = apply_filters( 'ht_kb_install_media_key', sanitize_title( $key ), $media );

			$source = property_exists( $media, 'source') ? $media->source : '';


			$attachment_id = 0; 
			if( 'file' == $source ){

				$file = property_exists( $media, 'file') ? $media->file : false;

				if( $file ){

					$file = $path . apply_filters( 'ht_kb_install_media_relative_path', 'media', $media, $path ) . DIRECTORY_SEPARATOR . $file;

					//apply filters
					$file = apply_filters( 'ht_kb_install_media_file', $file, $media, $path );

					$attachment_id = $this->import_image_to_wp_library ( $file );
					//@todo - add caption

					if( is_a( $attachment_id, 'WP_Error' ) ){
						//this is handled by the calling function above
					} else {
						//add the key to media installed with the attachment id
						$this->media_installed[ $key ] = $attachment_id;
						return true;
					}

				}
			}

			return $attachment_id;

		}

		/**
		 * Helper Function for media 
		 * @param key - Media key
		 * @return true if echoed sucessfully
		 */
		function ht_kb_sample_get_media_url( $key = false ){
			if( empty($key) ){
				//@todo - add warning if key is empty
				return false;
			}

			if( array_key_exists( $key, $this->media_installed ) ){
				$attachment_id = $this->media_installed[ $key ];
				$attachment_url = wp_get_attachment_url( $attachment_id );

				if( empty($attachment_url ) ){
					//@todo - add warning if the attachment url is empty
				} else {
					return $attachment_url;
				}
			} else {
				//@todo - add warning if key doesn't exist
			}
		}

		/**
		* Use do_action ht_kb_sample_media( $key )
		*/
		function ht_kb_sample_media_url( $key ){
			echo $this->ht_kb_sample_get_media_url( $key );
		}

		function ht_kb_install_categories( $folder_json_path ){
			$categories_json_path = $folder_json_path . 'ht-kb-categories.json';

			//apply filters
			$categories_json_path = apply_filters( 'ht_kb_install_categories_categories_json_path', $categories_json_path );

			//get the json file contents			
			$categories_json = file_get_contents( $categories_json_path );
 
 			//decode json contents
			$category_decoded_json = json_decode( $categories_json, false );

			//if category_decoded_json returns null, it's not proper json and should return error
			if( empty( $category_decoded_json) ){
				//throw new WP_Error, json format invalid
				$error_message = sprintf( __( 'JSON format of %s is invalid', 'ht-knowledge-base' ), $categories_json_path );
				$this->install_errors[] = new WP_Error( 'invalid_json', $error_message );
				return false;
			}

			//check the categories property exists
			$categories = property_exists( $category_decoded_json, 'categories') ? $category_decoded_json->categories : [];
			if( empty( $categories ) ){
				//no categories, return error
				$error_message =  __( 'No categories found in ht-kb-categories.json', 'ht-knowledge-base' );
				$this->install_errors[] = new WP_Error( 'invalid_json', $error_message );
				return false;
			}

			//loop categories 
			foreach ( $category_decoded_json->categories as $key => $category ) {
				//install category and increment counter, or append to errors
				$install_category_result = $this->ht_kb_install_category( $category, $folder_json_path );
				if( is_a( $install_category_result, 'WP_Error' ) ){
					$this->install_errors[] = $install_category_result;
				} elseif ( true == $install_category_result ) {
					$this->categories_installed_count += 1;
				}
			}
		}

		/**
		 * $category
		 * @return Boolean || WP_Error
		 */
		function ht_kb_install_category( $category, $path ){

			$name = $category->name;

			//slug defaults to the sanitize_title value, but this is filterable with ht_kb_install_category_slug
			$slug = apply_filters( 'ht_kb_install_category_slug', sanitize_title( $name ), $category );

			$description = property_exists( $category, 'description') ? $category->description : '';

			$icon = property_exists( $category, 'icon') ? $category->icon : false;

			//$parent = property_exists( $category, 'parent') ? intval ( $category->parent ) : 0;
			$parent = property_exists( $category, 'parent') ? sanitize_title( $category->parent )  : 0;

			//parent specified, fetch term_id
			if( !empty($parent) ){
				//get the parent term by its slug
				$term = get_term_by( 'slug', $parent, 'ht_kb_category' );
				//set or reset the parent ID
				$parent = is_a( $term , 'WP_Term' ) ? $term->term_id : 0;
			}
			

			$category_args = array(
				'slug' => $slug,
				'description' => $description,
				'parent' => $parent
			);

			$name = sanitize_text_field( $name );

			$new_term = wp_insert_term( $name, 'ht_kb_category', $category_args );

			if( is_a( $new_term, 'WP_Error' ) ){
				//check if term_exists error - it's likely we can ignore this error and just return false
				if( 'term_exists' == $new_term->get_error_code() ){
					return false;
				}
				//default to return the error
				return $new_term;
			}

			$new_term_id = $new_term['term_id'];

			$term_order = property_exists( $category, 'term_order') ? $category->term_order : false;

			if( $term_order ){
				update_term_meta( $new_term_id, 'term_order', intval( $term_order ) );
			}

			$icon = property_exists( $category, 'icon') ? $category->icon : '';

			if( !empty( $icon ) ){
				$icon_path = plugin_dir_path( HT_KB_MAIN_PLUGIN_FILE ) . 'hkb-icons' . DIRECTORY_SEPARATOR . $icon . '.svg';
				
				//apply filters
				$icon_path = apply_filters( 'ht_kb_install_category_icon_path', $icon_path, $category );

				//error if unable to locate icon svg
				if( !file_exists( $icon_path ) ){
					$error_message = sprintf( __( 'Unable to locate icon %s', 'ht-knowledge-base' ), $icon );
					$this->install_errors[] = new WP_Error( 'category_icon_not_found', $error_message );
					return false;
				}

				//import the icon and set meta_svg
				$icon_svg = file_get_contents( $icon_path );

				//apply filters
				$icon_svg = apply_filters( 'ht_kb_install_category_icon_svg', $icon_svg, $category );

				//set the icon svg
				update_term_meta( $new_term_id, 'meta_svg', $icon_svg );

				//set the color
				$icon_color = property_exists( $category, 'icon_color') ? $category->icon_color : '#000';

				//apply filters
				$icon_color = apply_filters( 'ht_kb_install_category_icon_color', $icon_color, $category );

				//sanitize
				$sanitized_icon_color = sanitize_hex_color( $icon_color );

				//error on empty hex color
				if( empty( $sanitized_icon_color ) ){
					$error_message = sprintf( __( 'Hex color invalid %s', 'ht-knowledge-base' ), $icon_color );
					$this->install_errors[] = new WP_Error( 'category_icon_not_found', $error_message );
					return false;
				} 

				//add style="stroke: $icon_color;" to class="hkbiconsvg-stroke" 

				//add style="fill: $icon_color;" to class="hkbiconsvg-fill"

				//update the icon to manually fill in the stroke and fill colours
				$colored_icon_svg = $icon_svg;

				$colored_icon_svg = str_replace( 'class="hkbiconsvg-stroke"' , 'class="hkbiconsvg-stroke"' . ' ' . 'add style="stroke: ' . $sanitized_icon_color . ';"', $colored_icon_svg );

				$colored_icon_svg = str_replace( 'class="hkbiconsvg-fill"' , 'class="hkbiconsvg-fill"' . ' ' . 'add style="fill: ' . $sanitized_icon_color . ';"', $colored_icon_svg );

				//meta svg update with the color
				update_term_meta( $new_term_id, 'meta_svg', $colored_icon_svg );

				//update term meta - icon color
				update_term_meta( $new_term_id, 'meta_svg_color', $sanitized_icon_color );
			}
			
			//finally return true to represent sucessful installation of category
			return true;
		}

		function ht_kb_install_articles( $folder_json_path ){
			$articles_json_path = $folder_json_path . 'ht-kb-articles.json';

			//apply filters
			$articles_json_path = apply_filters( 'ht_kb_install_articles_articles_json_path', $articles_json_path );

			//get the json file contents
			$articles_json = file_get_contents( $articles_json_path );
 
 			//decode json contents
			$articles_decoded_json = json_decode( $articles_json, false );

			//if articles_decoded_json returns null, it's not proper json and should return error
			if( empty($articles_decoded_json) ){
				//throw new WP_Error, json format invalid
				$error_message = sprintf( __( 'JSON format of %s is invalid', 'ht-knowledge-base' ), $articles_json_path );
				$this->install_errors[] = new WP_Error( 'invalid_json', $error_message );
				return false;
			}

			//check the articles property exists
			$articles = property_exists( $articles_decoded_json, 'articles') ? $articles_decoded_json->articles : [];
			if( empty( $articles ) ){
				//no articles, return error
				$error_message =  __( 'No articles found in ht-kb-articles.json', 'ht-knowledge-base' );
				$this->install_errors[] = new WP_Error( 'invalid_json', $error_message );
				return false;
			} 

			//loop articles 
			foreach ( $articles_decoded_json->articles as $key => $article ) {
				$install_article_result = $this->ht_kb_install_article( $article, $folder_json_path );
				if( is_a( $install_article_result, 'WP_Error' ) ){
					$this->install_errors[] = $install_article_result;
				} elseif ( true == $install_article_result ) {
					$this->articles_installed_count += 1;
				}
			}
		}

		/**
		 * $articles [] array
		 */
		function ht_kb_install_article( $article, $path ){

			$title = property_exists( $article, 'include') ? $article->title : false;

			if( !$title ){
				//if there's no title, throw article has no title error, or skip article, in any case - return 
				return;
			}

			$source = property_exists( $article, 'source') ? $article->source : 'text';

			$content = '';

			if( 'include' == $source ){

				$include = property_exists( $article, 'include') ? $article->include : false;

				//check we have a valid include set
				if( $include ){
					$include_file = $path . $include . '.php';

					$include_file_exists =  file_exists( $include_file );

					//check the include file exists, then set the content 
					if( $include_file_exists ){
						//$content = file_get_contents( $include_file );

						//using output buffer so we can apply variables in the include file
						ob_start();
						@include( $include_file );
						$content = ob_get_contents();
						ob_end_clean();
					}					
				}				
			} elseif( 'text' == $source ){
				//@todo - implement regular text import
			} else {
				//no content source
			}

			$categories = property_exists( $article, 'categories') ? $article->categories : [];

			//we just use the first category, or leave uncategories
			$category = ( is_array($categories) && count($categories) > 0 ) ? $categories[0] : false;

			$tags = property_exists( $article, 'tags') ? $article->tags : [];

			//@todo - check for plugin dependiencies before we install add this article
			//property "plugin-dependencies": []

			$install_article = $this->add_sample_ht_kb_article($title, $content, $category, $tags );

			return $install_article;
		}

		/**
		* Adds a sample knowledge base article
		* @param $title The title of the article
		* @param $content The content of the article
		* @param $category The category of the article
		* @param $tags An array of tags to assign to the article
		*/
		function add_sample_ht_kb_article($title = '', $content = '', $category = '', $tags = array() ){

			if( empty ( $content ) ){
				$content = $this->sample_content_generator();
			}

			$new_article = array(
				  'post_content'   => $content,
				  'post_name'      => $title,
				  'post_title'     => $title,
				  'post_status'    => 'publish',
				  'post_type'      => 'ht_kb'
				);

			$new_article_id = wp_insert_post($new_article);

			//return wp errors directly
			if( is_a( $new_article_id, 'WP_Error' ) ){
				return $new_article_id;
			}

			if( 0 == $new_article_id ){
				$error_message = sprintf( __('Unable to add article %s', 'ht-knowledge-base' ), $title );
				return new WP_Error( 'post_invalid', $error_message );
			}

			if( $new_article_id > 0 ){
				//ht_kb_categories
				//if category, set the object terms, else leave uncategorized
				if( !empty( $category )){
					$category_slug = sanitize_title($category);
					wp_set_object_terms( $new_article_id, $category_slug, 'ht_kb_category', true );	
				}				

				//ht_kb_tags
				foreach ($tags as $key => $tag) {
					$tag_slug = sanitize_title($tag);
					wp_set_object_terms( $new_article_id, $tag_slug, 'ht_kb_tag', true );
				}

				//return true to represent article install success
				return true;
			}
			
		}

		function ht_kb_install_settings( $folder_json_path ){
			$settings_json_path = $folder_json_path . 'ht-kb-settings.json';

			//apply filters
			$settings_json_path = apply_filters( 'ht_kb_install_settings_settings_json_path', $settings_json_path );

			//get the json file contents			
			$settings_json = file_get_contents( $settings_json_path );
 
 			//decode json contents
			$setting_decoded_json = json_decode( $settings_json, false );

			//if setting_decoded_json returns null, it's not proper json and should return error
			if( empty( $setting_decoded_json) ){
				//throw new WP_Error, json format invalid
				$error_message = sprintf( __( 'JSON format of %s is invalid', 'ht-knowledge-base' ), $settings_json_path );
				$this->install_errors[] = new WP_Error( 'invalid_json', $error_message );
				return false;
			}

			//check the settings property exists
			$settings = property_exists( $setting_decoded_json, 'settings') ? $setting_decoded_json->settings : [];
			if( empty( $settings ) ){
				//no settings, return error
				$error_message =  __( 'No settings found in ht-kb-settings.json', 'ht-knowledge-base' );
				$this->install_errors[] = new WP_Error( 'invalid_json', $error_message );
				return false;
			}

			//load settings cache
			$this->settings_cache = $this->ht_kb_settings = get_option( 'ht_knowledge_base_settings', [] );

			//loop settings 
			foreach ( $setting_decoded_json->settings as $key => $setting ) {
				//install setting and increment counter, or append to errors
				$install_setting_result = $this->ht_kb_install_setting( $setting, $folder_json_path );
				if( is_a( $install_setting_result, 'WP_Error' ) ){
					$this->install_errors[] = $install_setting_result;
				} elseif ( true == $install_setting_result ) {
					$this->settings_installed_count += 1;
				}
			}

			//save settings cache
			update_option( 'ht_knowledge_base_settings', $this->settings_cache );

		}

		/**
		 * $settings
		 * @return Boolean || WP_Error
		 */
		function ht_kb_install_setting( $setting, $path ){

			$key = $setting->key;

			//get the value, note that false can be a valid setting, so still needs setting (if a value is not stated it will be set as false)
			$value = property_exists( $setting, 'value') ? $setting->value : false;

			$this->settings_cache[ $key ] = $value;

			//finally return true to represent sucessful settings
			return true;
		}

		/**
		* Get generic sample content so we don't get a WP_Error for empty content
		* @return (String) Sample content
		*/
		function sample_content_generator(){
			$content = '';
			$content .= __('<h1>Sample Content</h1>', 'ht-knowledge-base');
			$content .= __('Sample content would go here', 'ht-knowledge-base');
			return $content;
		}

		/**
		* Remove all knowledge base data - articles, categories and tags
		*/
		function remove_all_ht_kb_data(){
			//remove articles
			$articles = get_posts( array( 'post_type' => 'ht_kb', 'posts_per_page' => -1) );
			foreach( $articles as $article ) {
				//delete post, bypass trash
				wp_delete_post( $article->ID, true);
			}
			//remove category terms
			$this->remove_terms_from_taxonomy('ht_kb_category');
			//remove tag terms
			$this->remove_terms_from_taxonomy('ht_kb_tag');
		}

		/**
		* Remove  the terms from a particular taxonomy
		*/
		function remove_terms_from_taxonomy($taxonomy){
			$args = array(
					'taxonomy' => $taxonomy,
					'hide_empty' => false,
					//bust cache
					'update_term_meta_cache' => false,
				);  
			$terms = get_terms( $args );
			$count = count($terms);
			if ( $count > 0 ){
				foreach ( $terms as $term ) {
					wp_delete_term( $term->term_id, $taxonomy );
				}
			}
		}

		/** 
		* imports a image from the sample-content/images from the welcome/sample-content/images/ directory
		* @param (String) $file - file to import
		* @return (Int) ID attachment ID
		*/
		function import_image_to_wp_library( $file ){
			$file_to_import = apply_filters( 'ht_kb_import_image_to_wp_library', $file );
			if( file_exists( $file_to_import ) ){
				$id = $this->handle_import_image($file_to_import);
				return $id; 
			} else {
				return new WP_Error( 'error', __('File does not exist', 'ht-knowledge-base') );
			}            
		}

		/**
		* Handle image import
		* @param (File) Image file to import 
		* @return (Int) attachment_id
		*/
		function handle_import_image( $file ) {
			set_time_limit( 0 );

			//current time
			$time = current_time( 'mysql', 1 );

			//test writeable upload dir
			if ( !(($uploads = wp_upload_dir( $time )) && false === $uploads['error']) ) {
				return new WP_Error( 'import_error', $uploads['error'] );
			}

			$wp_filetype = wp_check_filetype( $file, null );

			//extract
			extract( $wp_filetype );

			//generate unique filename
			$filename = wp_unique_filename( $uploads['path'], basename( $file ) );

			//copy the file to the uploads dir
			$new_file = $uploads['path'] . '/' . $filename;
			if ( false === @copy( $file, $new_file ) )
				return new WP_Error( 'import_error', sprintf( __( 'Unable to import %s.', 'ht-knowledge-base' ), $file ) );

			//assign file permissions
			try {
			   $stat = stat( dirname( $new_file ) );
				$perms = $stat['mode'] & 0000666;
				chmod( $new_file, $perms );   
			} catch (Exception $e) {
				//handle permissions errors
			}                             

			//prepare the url
			$url = $uploads['url'] . DIRECTORY_SEPARATOR . $filename;

			//apply upload filters
			$return = apply_filters( 'wp_handle_upload', array( 'file' => $new_file, 'url' => $url, 'type' => $type ) );
			$new_file = $return['file'];
			$url = $return['url'];
			$type = $return['type'];

			$attachment_title = preg_replace( '!\.[^.]+$!', '', basename( $file ) );
			$attachment_content = '';
			$attachment_excerpt = '';

			//use image exif for title and captions
			@require_once( ABSPATH . '/wp-admin/includes/image.php' );
			if ( 0 === strpos( $type, 'image/' ) && $image_meta = @wp_read_image_metadata( $new_file ) ) {
				if ( trim( $image_meta['title'] ) && ! is_numeric( sanitize_title( $image_meta['title'] ) ) ) {
					$attachment_title = $image_meta['title'];
				}
		
				if ( trim( $image_meta['caption'] ) ) {
					$attachment_excerpt = $image_meta['caption'];
				}
			}
			
			$attachment_post_date = current_time( 'mysql' );
			$attachment_post_date_gmt = current_time( 'mysql', 1 );

			//attachment array
			$attachment_data = array(
				'post_mime_type' => $type,
				'guid' => $url,
				'post_parent' => 0,
				'post_title' => $attachment_title,
				'post_name' => $attachment_title,
				'post_content' => $attachment_content,
				'post_excerpt' => $attachment_excerpt,
				'post_date' => $attachment_post_date,
				'post_date_gmt' => $attachment_post_date_gmt
			);

			//wc 4.4 compat
			$new_file = str_replace( ucfirst( wp_normalize_path( $uploads['basedir'] ) ), $uploads['basedir'], $new_file );

			//save
			$id = wp_insert_attachment( $attachment_data, $new_file );
			if ( !is_wp_error( $id ) ) {
				$data = wp_generate_attachment_metadata( $id, $new_file );
				wp_update_attachment_metadata( $id, $data );
			}

			return $id;
		}

		/**
		* Helper function checks if slug is available
		* interface function reserved for future use
		* @param (String) $slug Slug to check
		* @return true
		*/ 
		function is_slug_available($slug){
			return true;
		}


	}

}

if (class_exists('HT_Knowledge_Base_Sample_Importer')) {
	new HT_Knowledge_Base_Sample_Importer();
}