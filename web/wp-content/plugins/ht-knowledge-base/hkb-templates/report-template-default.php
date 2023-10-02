<?php
/**
* Output for the Knowledge Base template
*/
?>


<!doctype html>
<html>
  <head>
    <meta name="viewport" content="width=device-width">
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <title><?php _e('Your Knowledge Base Report', 'ht-knowledge-base'); ?></title>
  <style>
@media only screen and (max-width: 620px) {
  table[class=body] h1 {
    font-size: 28px !important;
    margin-bottom: 10px !important;
  }

  table[class=body] p,
table[class=body] ul,
table[class=body] ol,
table[class=body] td,
table[class=body] span,
table[class=body] a {
    font-size: 16px !important;
  }

  table[class=body] .wrapper,
table[class=body] .article {
    padding: 10px !important;
  }

  table[class=body] .content {
    padding: 0 !important;
  }

  table[class=body] .container {
    padding: 0 !important;
    width: 100% !important;
  }

  table[class=body] .main {
    border-left-width: 0 !important;
    border-radius: 0 !important;
    border-right-width: 0 !important;
  }

  table[class=body] .btn table {
    width: 100% !important;
  }

  table[class=body] .btn a {
    width: 100% !important;
  }

  table[class=body] .img-responsive {
    height: auto !important;
    max-width: 100% !important;
    width: auto !important;
  }
}
@media all {
  .ExternalClass {
    width: 100%;
  }

  .ExternalClass,
.ExternalClass p,
.ExternalClass span,
.ExternalClass font,
.ExternalClass td,
.ExternalClass div {
    line-height: 100%;
  }

  .apple-link a {
    color: inherit !important;
    font-family: inherit !important;
    font-size: inherit !important;
    font-weight: inherit !important;
    line-height: inherit !important;
    text-decoration: none !important;
  }

  .btn-primary table td:hover {
    background-color: #d5075d !important;
  }

  .btn-primary a:hover {
    background-color: #d5075d !important;
    border-color: #d5075d !important;
  }
}
</style></head>
  <body class style="background-color: #eaebed; font-family: sans-serif; -webkit-font-smoothing: antialiased; font-size: 14px; line-height: 1.4; margin: 0; padding: 0; -ms-text-size-adjust: 100%; -webkit-text-size-adjust: 100%;">

    <table role="presentation" border="0" cellpadding="0" cellspacing="0" class="body" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; min-width: 100%; background-color: #eaebed; width: 100%;" width="100%" bgcolor="#eaebed">
      <tr>
        <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">&nbsp;</td>
        <td class="container" style="font-family: sans-serif; font-size: 14px; vertical-align: top; display: block; max-width: 580px; padding: 10px; width: 500px; Margin: 0 auto;" width="500" valign="top">
          <div class="header" style="padding: 20px 0;">

          </div>
          <div class="content" style="box-sizing: border-box; display: block; Margin: 0 auto; max-width: 580px; padding: 10px;">

            <!-- START CENTERED WHITE CONTAINER -->
            <span class="preheader" style="color: transparent; display: none; height: 0; max-height: 0; max-width: 0; opacity: 0; overflow: hidden; mso-hide: all; visibility: hidden; width: 0;"><?php _e('Your weekly knowledge base report.', 'ht-knowledge-base'); ?></span>
            <table role="presentation" class="main" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; min-width: 100%; background: #ffffff; border-radius: 3px; width: 100%;" width="100%">

              <!-- START MAIN CONTENT AREA -->
              <tr>
                <td class="wrapper" style="font-family: sans-serif; font-size: 14px; vertical-align: top; box-sizing: border-box; padding: 2rem;" valign="top">
                  <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; min-width: 100%; width: 100%;" width="100%">
                    <tr>
                      <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">

                        <!-- HKB Logo -->
                        <img src="<?php echo plugin_dir_url( __DIR__ ); ?>img/hkb-logo.png" alt="" height="60" width="169" style="margin: 0; margin-bottom: 8px" />
                        <!-- /HKB Logo -->
                        
                        <h1 class="hkb-report-heading" style="font-size: 22px; font-weight: 400; margin: 0; margin-bottom: 8px;"><?php _e('Your Knowledge Base Report', 'ht-knowledge-base'); ?></h1>
                        <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 16px; color: #999" class="hkb-report-period"><?php ht_kb_report_start_date(); ?> - <?php ht_kb_report_end_date(); ?></p>
                        <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 2rem;"><?php _e('Here\'s how your knowledge base performed in the past week.', 'ht-knowledge-base'); ?></p>

                        <table cellspacing="0" cellpadding="0" border="0" style="background-color: #fff;">

                            <tr>
                                <td width="250" style="background: #ebf1f4; text-align: center; padding: 1.5rem 1rem;">
                                    <img src="<?php echo plugin_dir_url( __DIR__ ); ?>img/icon-views.png" alt="" height="48" width="48" style="margin: 0; margin-bottom: 8px" />
                                    <div class="hkb-total-views-label" style="font-weight: 600; font-size: 15px; margin: 0; margin-bottom: 8px;"><?php _e('Total Views', 'ht-knowledge-base'); ?></div>
                                    <div class="hkb-total-views-value" style="font-size: 18px; margin: 0; margin-bottom: 16px"><?php ht_kb_report_total_views(); ?></div>
                                    <div class="hkb-total-views-change" style="margin: 0;"><?php ht_kb_report_views_change(); ?></div>
                                    <div class="hkb-total-views-change-label" style="color: #999; font-size: 14px;"><?php _e('vs previous period', 'ht-knowledge-base'); ?></div> 
                                </td>
                                <td width="250" style="background: #ebf1f4; text-align: center; padding: 1.5rem 1rem;">
                                    <img src="<?php echo plugin_dir_url( __DIR__ ); ?>img/icon-rating.png" alt="" height="48" width="48" style="margin: 0; margin-bottom: 8px" />
                                    <div class="hkb-total-helpfulness-label" style="font-weight: 600; font-size: 15px; margin: 0; margin-bottom: 8px"><?php _e('Average Rating', 'ht-knowledge-base'); ?></div>
                                    <div class="hkb-total-helpfulness-value" style="font-size: 18px; margin: 0; margin-bottom: 16px"><?php ht_kb_report_average_helpfulness(); ?></div>
                                    <div class="hkb-total-helpfulness-change" style="margin: 0;"><?php ht_kb_report_average_helpfulness_change() ?></div>
                                    <div class="hkb-total-helpfulness-change-label" style="color: #999; font-size: 14px;"><?php _e('vs previous period', 'ht-knowledge-base'); ?></div>           
                                </td>
                            </tr>


                            <tr>
                                <td width="500" colspan="2" style="padding: 2rem 2rem 0">                                   
                                   <img src="<?php echo plugin_dir_url( __DIR__ ); ?>img/icon-articles.png" alt="" height="48" width="48" style="margin: 0 auto .5rem; display: block;" />
                                    <h3 style="text-align: center; font-size: 18px; font-weight: 400; margin: 0; margin-bottom: 1rem;"><?php _e('Top Articles', 'ht-knowledge-base'); ?></h3> 
                                   <ol>
                                        <?php ht_kb_report_viewed_articles(5); ?>
                                    </ol>
                                    <a href="<?php echo admin_url('edit.php?post_type=ht_kb&page=ht-kb-reporting')?>"><?php _e('View More', 'ht-knowledge-base'); ?></a>
                                </td>
                            </tr>


                            <tr>
                                <td width="500" colspan="2" style="border-bottom: 1px solid #F0F2F4; padding: 3rem 0 0;"></td>
                            </tr>


                            <tr>
                                <td width="500" colspan="2" style="padding: 2rem">                                    
                                    <img src="<?php echo plugin_dir_url( __DIR__ ); ?>img/icon-star.png" alt="" height="48" width="48" style="margin: 0 auto .5rem; display: block;" />
                                    <h3 style="text-align: center; font-size: 18px; font-weight: 400; margin: 0; margin-bottom: 1rem;"><?php _e('Highest Rated Articles', 'ht-knowledge-base'); ?></h3>
                                    <ol>
                                        <?php ht_kb_report_helpful_articles(5); ?>
                                    </ol>
                                    <a href="<?php echo admin_url('edit.php?post_type=ht_kb&page=ht-kb-reporting')?>"><?php _e('View More', 'ht-knowledge-base'); ?></a>
                                </td>
                            </tr>
                            <tr>
                                <td width="500" colspan="2"></td>
                            </tr>
                        </table>

                        <div style="background: #ebf1f4; padding: 2rem;">
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0;"><?php printf( __('What do you think of your new Knowledge Base report? Let us know your <a href="%s">thoughts</a>', 'ht-knowledge-base' ), 'https://herothemes.com/contact/' ); ?>.</p>
                        </div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <?php
                  /* hook for final CTA or further report information */
                  do_action( 'ht_kb_report_pre_table_end' );
              ?>
            <!-- END MAIN CONTENT AREA -->
            </table>

            <?php
                /* hook for final CTA or further report information */
                do_action( 'ht_kb_report_pre_footer' );
            ?>

            <!-- START FOOTER -->
            <div class="footer" style="clear: both; Margin-top: 10px; text-align: center; width: 100%;">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; min-width: 100%; width: 100%;" width="100%">
                <tr>
                  <td class="content-block" style="font-family: sans-serif; vertical-align: top; padding-bottom: 10px; padding-top: 10px; color: #9a9ea6; font-size: 12px; text-align: center;" valign="top" align="center">
                       <?php _e('Don\'t like these emails?', 'ht-knowledge-base'); ?> <a href="<?php echo admin_url('edit.php?post_type=ht_kb&page=ht_knowledge_base_settings_page#reports-section')?>" style="text-decoration: underline; color: #9a9ea6; font-size: 12px; text-align: center;"><?php _e('Unsubscribe', 'ht-knowledge-base'); ?></a>.
                  </td>
                </tr>
                <tr>
                  <td class="content-block powered-by" style="font-family: sans-serif; vertical-align: top; padding-bottom: 10px; padding-top: 10px; color: #9a9ea6; font-size: 12px; text-align: center;" valign="top" align="center">
                    <?php _e('Powered by Heroic Knowledge Base.', 'ht-knowledge-base'); ?>
                  </td>
                </tr>
              </table>
            </div>
            <!-- END FOOTER -->

          <!-- END CENTERED WHITE CONTAINER -->
          </div>
        </td>
        <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">&nbsp;</td>
      </tr>
    </table>
  </body>
</html>

