###########################################################################################
# assets - javascript and css asset handling
#
#       Date            Author          Reason
#       ----            ------          ------
#       03/04/20        Lou King        Create
#
#   Copyright 2020 Lou King.  All rights reserved
#
###########################################################################################

'''
assets - javascript and css asset handling
===================================================
'''

from flask_assets import Bundle, Environment

# jquery
jq_ver = '3.5.1'
jq_ui_ver = '1.12.1'
jq_validate_ver = '1.19.3'

# dataTables
dt_buttons_ver = '1.6.5' # also used for colvis and html5
dt_datatables_ver = '1.10.22'
dt_editor_ver = '1.9.6+discussion-59060'
dt_fixedcolumns_ver = '3.3.1'
dt_responsive_ver = '2.2.6'
dt_rowreorder_ver = '1.2.7'
dt_select_ver = '1.3.1-preXhr-patch'
jszip_ver = '2.5.0'

# select2
# NOTE: patch to jquery ui required, see https://github.com/select2/select2/issues/1246#issuecomment-17428249
# currently in datatables.js
s2_ver = '4.0.12'

# smartmenus
sm_ver = '1.1.0'

# yadcf
yadcf_ver = '0.9.4.beta.45+lk-date_custom_func'

moment_ver = '2.24.0'       # moment.js (see https://momentjs.com/)
lodash_ver = '4.17.15'      # lodash.js (see https://lodash.com)
d3_ver = '7.1.1'            # d3js.org (see https://d3js.org/)
d3_tip_ver = '1.1'          # https://github.com/VACLab/d3-tip
fa_ver = '5.13.0'           # https://fontawesome.com/
nunjucks_ver = '3.2.0'      # https://mozilla.github.io/nunjucks/
cke_type='classic'           # https://ckeditor.com/ckeditor-5/
cke_ver='26.0.0-members-414' # https://ckeditor.com/ckeditor-5/
materialize_ver='1.0.0'     # https://materializecss.com/
pickadate_ver = '3.6.4'     # https://amsul.ca/pickadate.js/

frontend_common_js = Bundle(
    'js/jquery-{ver}/jquery-{ver}.js'.format(ver=jq_ver),
    'js/jquery-ui-{ver}.custom/jquery-ui.js'.format(ver=jq_ui_ver),

    'js/lodash-{ver}/lodash.js'.format(ver=lodash_ver),

    'js/smartmenus-{ver}/jquery.smartmenus.js'.format(ver=sm_ver),

    # datatables / yadcf
    'js/DataTables-{ver}/js/jquery.dataTables.js'.format(ver=dt_datatables_ver),
    'js/DataTables-{ver}/js/dataTables.jqueryui.js'.format(ver=dt_datatables_ver),
    'js/yadcf-{ver}/jquery.dataTables.yadcf.js'.format(ver=yadcf_ver),

    'js/FixedColumns-{ver}/js/dataTables.fixedColumns.js'.format(ver=dt_fixedcolumns_ver),
    'js/Responsive-{ver}/js/dataTables.responsive.js'.format(ver=dt_responsive_ver),
    'js/Responsive-{ver}/js/responsive.jqueryui.js'.format(ver=dt_responsive_ver),

    'js/Editor-{ver}/js/dataTables.editor.js'.format(ver=dt_editor_ver),
    'js/Editor-{ver}/js/editor.jqueryui.js'.format(ver=dt_editor_ver),

    'js/Select-{ver}/js/dataTables.select.js'.format(ver=dt_select_ver),

    # select2 is required for use by Editor forms and interest navigation
    'js/select2-{ver}/js/select2.full.js'.format(ver=s2_ver),
    # the order here is important
    'js/FieldType-Select2/editor.select2.js',

    # date time formatting
    'js/moment-{ver}/moment.js'.format(ver=moment_ver),

    # d3
    'js/d3-{ver}/d3.js'.format(ver=d3_ver),
    'js/d3-tip-{ver}/d3-tip.js'.format(ver=d3_tip_ver),

    'frontend/beforedatatables.js',
    'admin/layout.js',  # TODO: smartmenus initialization, should be moved to layout.js
    'layout.js',

    'utils.js', # from loutilities

    'editor.select2.mymethods.js',          # from loutilities
    'datatables.js',                        # from loutilities
    'datatables.dataRender.ellipsis.js',    # from loutilities
    'datatables.dataRender.datetime.js',    # from loutilities
    'editor.buttons.editrefresh.js',        # from loutilities
    'editor.buttons.editchildrowrefresh.js',# from loutilities
    'filters.js',                           # from loutilities
    'utils.js',                             # from loutilities
    'user/admin/groups.js',                 # from loutilities

    'admin/afterdatatables.js',             # TODO: should move common bits up a level and pieces to frontend/afterdatatables

    filters='jsmin',
    output='gen/frontendcommon.js',
)

frontend_materialize_js = Bundle(
    f'https://cdnjs.cloudflare.com/ajax/libs/materialize/{materialize_ver}/js/materialize.js',
    f'https://cdnjs.cloudflare.com/ajax/libs/jquery-validate/{jq_validate_ver}/jquery.validate.js',
    
    filters='jsmin',
    output='gen/frontendmaterialize.js',
)

frontend_common_css = Bundle(
    'js/jquery-ui-{ver}.custom/jquery-ui.css'.format(ver=jq_ui_ver),
    'js/jquery-ui-{ver}.custom/jquery-ui.structure.css'.format(ver=jq_ui_ver),
    'js/jquery-ui-{ver}.custom/jquery-ui.theme.css'.format(ver=jq_ui_ver),
    'js/DataTables-{ver}/css/dataTables.jqueryui.css'.format(ver=dt_datatables_ver),
    'js/Buttons-{ver}/css/buttons.jqueryui.css'.format(ver=dt_buttons_ver),
    'js/FixedColumns-{ver}/css/fixedColumns.jqueryui.css'.format(ver=dt_fixedcolumns_ver),
    'js/Responsive-{ver}/css/responsive.dataTables.css'.format(ver=dt_responsive_ver),
    'js/Responsive-{ver}/css/responsive.jqueryui.css'.format(ver=dt_responsive_ver),
    'js/Select-{ver}/css/select.jqueryui.css'.format(ver=dt_select_ver),
    'js/select2-{ver}/css/select2.css'.format(ver=s2_ver),
    'js/yadcf-{ver}/jquery.dataTables.yadcf.css'.format(ver=yadcf_ver),

    'js/fontawesome-{ver}/css/fontawesome.css'.format(ver=fa_ver), 
    'js/fontawesome-{ver}/css/solid.css'.format(ver=fa_ver), 

    'datatables.css',  # from loutilities
    'editor.css',  # from loutilities
    'filters.css',  # from loutilities
    'branding.css',  # from loutilities

    'js/smartmenus-{ver}/css/sm-core-css.css'.format(ver=sm_ver),
    'js/smartmenus-{ver}/css/sm-blue/sm-blue.css'.format(ver=sm_ver),

    'style.css',
    'admin/style.css',      # TODO: some of this is for smartmenus, should be in style.css

    filters=['cssrewrite', 'cssmin'],
    output='gen/frontendcommon.css',
)

frontend_materialize_css = Bundle(
    f'https://cdnjs.cloudflare.com/ajax/libs/materialize/{materialize_ver}/css/materialize.css',

    filters='jsmin',
    output='gen/frontendmaterialize.css',
)

frontend_members = Bundle(
    'frontend/membership-stats.js',
    
    filters='jsmin',
    output='gen/frontendmembers.js',
)


asset_bundles = {

    'frontend_js': Bundle(
        frontend_common_js,
    ),
    
    'frontendmembers_js': Bundle(
        frontend_common_js,
        frontend_members,
    ),
    
    'frontendmaterialize_js': Bundle(
        frontend_common_js,
        frontend_materialize_js,
       
    ),

    'frontend_css': Bundle(
        frontend_common_css,
        
        output='gen/frontend.css',
        # cssrewrite helps find image files when ASSETS_DEBUG = False
        filters=['cssrewrite', 'cssmin'],
        ),

    'frontendmaterialize_css': Bundle(
        frontend_common_css,
        frontend_materialize_css,
    ),

    'admin_js': Bundle(
        Bundle('js/jquery-{ver}/jquery-{ver}.js'.format(ver=jq_ver), filters='jsmin'),
        Bundle('js/jquery-ui-{ver}.custom/jquery-ui.js'.format(ver=jq_ui_ver), filters='jsmin'),

        Bundle('js/smartmenus-{ver}/jquery.smartmenus.js'.format(ver=sm_ver), filters='jsmin'),
        Bundle('js/lodash-{ver}/lodash.js'.format(ver=lodash_ver), filters='jsmin'),

        Bundle('js/JSZip-{ver}/jszip.js'.format(ver=jszip_ver), filters='jsmin'),
        Bundle('js/DataTables-{ver}/js/jquery.dataTables.js'.format(ver=dt_datatables_ver), filters='jsmin'),
        Bundle('js/DataTables-{ver}/js/dataTables.jqueryui.js'.format(ver=dt_datatables_ver), filters='jsmin'),
        Bundle('js/Editor-{ver}/js/dataTables.editor.js'.format(ver=dt_editor_ver), filters='jsmin'),
        Bundle('js/Editor-{ver}/js/editor.jqueryui.js'.format(ver=dt_editor_ver), filters='jsmin'),
        Bundle('js/Buttons-{ver}/js/dataTables.buttons.js'.format(ver=dt_buttons_ver), filters='jsmin'),
        Bundle('js/Buttons-{ver}/js/buttons.jqueryui.js'.format(ver=dt_buttons_ver), filters='jsmin'),
        Bundle('js/Buttons-{ver}/js/buttons.colVis.js'.format(ver=dt_buttons_ver), filters='jsmin'),
        Bundle('js/Buttons-{ver}/js/buttons.html5.js'.format(ver=dt_buttons_ver), filters='jsmin'),
        Bundle('js/FixedColumns-{ver}/js/dataTables.fixedColumns.js'.format(ver=dt_fixedcolumns_ver), filters='jsmin'),
        Bundle('js/Responsive-{ver}/js/dataTables.responsive.js'.format(ver=dt_responsive_ver), filters='jsmin'),
        Bundle('js/RowReorder-{ver}/js/dataTables.rowReorder.js'.format(ver=dt_rowreorder_ver), filters='jsmin'),
        Bundle('js/Select-{ver}/js/dataTables.select.js'.format(ver=dt_select_ver), filters='jsmin'),

        Bundle('js/yadcf-{ver}/jquery.dataTables.yadcf.js'.format(ver=yadcf_ver), filters='jsmin'),

        # select2 is required for use by Editor forms and interest navigation
        Bundle('js/select2-{ver}/js/select2.full.js'.format(ver=s2_ver), filters='jsmin'),
        # the order here is important
        Bundle('js/FieldType-Select2/editor.select2.js', filters='jsmin'),

        # date time formatting for datatables editor, per https://editor.datatables.net/reference/field/datetime
        Bundle('js/moment-{ver}/moment.js'.format(ver=moment_ver), filters='jsmin'),

        # d3
        Bundle('js/d3-{ver}/d3.js'.format(ver=d3_ver), filters='jsmin'),

        # ckeditor (note this is already minimized, and filter through jsmin causes problems)
        'js/ckeditor5-build-{type}-{ver}/build/ckeditor.js'.format(ver=cke_ver, type=cke_type),

        Bundle('admin/layout.js', filters='jsmin'),
        Bundle('layout.js', filters='jsmin'),

        # must be before datatables
        Bundle('editor-saeditor.js', filters='jsmin'),                   # from loutilities
        Bundle('js/nunjucks-{ver}/nunjucks.js'.format(ver=nunjucks_ver), filters='jsmin'),
        Bundle('admin/nunjucks/templates.js', filters='jsmin'),
        Bundle('editor.fieldType.display.js', filters='jsmin'),          # from loutilities
        Bundle('editor.ckeditor5.js', filters='jsmin'),                  # from loutilities
        Bundle('admin/beforedatatables.js', filters='jsmin'),
        Bundle('editor.googledoc.js', filters='jsmin'),                  # from loutilities
        Bundle('datatables.dataRender.googledoc.js', filters='jsmin'),   # from loutilities
        Bundle('user/admin/beforedatatables.js', filters='jsmin'),       # from loutilities
        Bundle('editor.select2.mymethods.js', filters='jsmin'),          # from loutilities
        Bundle('editor.displayController.onPage.js', filters='jsmin'),   # from loutilities
        Bundle('datatables-childrow.js', filters='jsmin'),               # from loutilities

        Bundle('datatables.js', filters='jsmin'),                        # from loutilities

        # must be after datatables.js
        Bundle('datatables.dataRender.ellipsis.js', filters='jsmin'),    # from loutilities
        Bundle('datatables.dataRender.datetime.js', filters='jsmin'),    # from loutilities
        Bundle('editor.buttons.editrefresh.js', filters='jsmin'),        # from loutilities
        Bundle('editor.buttons.editchildrowrefresh.js', filters='jsmin'),  # from loutilities
        Bundle('editor.buttons.separator.js', filters='jsmin'),          # from loutilities
        Bundle('filters.js', filters='jsmin'),                           # from loutilities
        Bundle('utils.js', filters='jsmin'),                             # from loutilities
        Bundle('user/admin/groups.js', filters='jsmin'),                 # from loutilities

        # Bundle('admin/editor.buttons.invites.js', filters='jsmin'),
        Bundle('admin/afterdatatables.js', filters='jsmin'),

        output='gen/admin.js',
        ),

    'admin_css': Bundle(
        Bundle('js/jquery-ui-{ver}.custom/jquery-ui.css'.format(ver=jq_ui_ver), filters=['cssrewrite', 'cssmin']),
        Bundle('js/jquery-ui-{ver}.custom/jquery-ui.structure.css'.format(ver=jq_ui_ver), filters=['cssrewrite', 'cssmin']),
        Bundle('js/jquery-ui-{ver}.custom/jquery-ui.theme.css'.format(ver=jq_ui_ver), filters=['cssrewrite', 'cssmin']),
        Bundle('js/smartmenus-{ver}/css/sm-core-css.css'.format(ver=sm_ver), filters=['cssrewrite', 'cssmin']),
        Bundle('js/smartmenus-{ver}/css/sm-blue/sm-blue.css'.format(ver=sm_ver), filters=['cssrewrite', 'cssmin']),

        Bundle('js/DataTables-{ver}/css/dataTables.jqueryui.css'.format(ver=dt_datatables_ver), filters=['cssrewrite', 'cssmin']),
        Bundle('js/Editor-{ver}/css/editor.dataTables.css'.format(ver=dt_editor_ver), filters=['cssrewrite', 'cssmin']),
        Bundle('js/Editor-{ver}/css/editor.jqueryui.css'.format(ver=dt_editor_ver), filters=['cssrewrite', 'cssmin']),
        Bundle('js/Buttons-{ver}/css/buttons.jqueryui.css'.format(ver=dt_buttons_ver), filters=['cssrewrite', 'cssmin']),
        Bundle('js/FixedColumns-{ver}/css/fixedColumns.jqueryui.css'.format(ver=dt_fixedcolumns_ver), filters=['cssrewrite', 'cssmin']),
        Bundle('js/Responsive-{ver}/css/responsive.jqueryui.css'.format(ver=dt_responsive_ver), filters=['cssrewrite', 'cssmin']),
        Bundle('js/RowReorder-{ver}/css/rowReorder.jqueryui.css'.format(ver=dt_rowreorder_ver), filters=['cssrewrite', 'cssmin']),
        Bundle('js/Select-{ver}/css/select.jqueryui.css'.format(ver=dt_select_ver), filters=['cssrewrite', 'cssmin']),
        
        Bundle('js/select2-{ver}/css/select2.css'.format(ver=s2_ver), filters=['cssrewrite', 'cssmin']),
        Bundle('js/yadcf-{ver}/jquery.dataTables.yadcf.css'.format(ver=yadcf_ver), filters=['cssrewrite', 'cssmin']),

        Bundle('js/fontawesome-{ver}/css/fontawesome.css'.format(ver=fa_ver), filters=['cssrewrite', 'cssmin']),
        Bundle('js/fontawesome-{ver}/css/solid.css'.format(ver=fa_ver), filters=['cssrewrite', 'cssmin']),

        Bundle('datatables.css', filters=['cssrewrite', 'cssmin']),   # from loutilities
        Bundle('editor.css', filters=['cssrewrite', 'cssmin']),       # from loutilities
        Bundle('filters.css', filters=['cssrewrite', 'cssmin']),      # from loutilities
        Bundle('branding.css', filters=['cssrewrite', 'cssmin']),     # from loutilities

        # this doesn't look like it's needed, was testing for #284
        # Bundle('js/ckeditor5-build-{type}-{ver}/sample/styles.css'.format(ver=cke_ver, type=cke_type),
        #        filters=['cssrewrite', 'cssmin']),
        Bundle('style.css', filters=['cssrewrite', 'cssmin']),
        Bundle('admin/style.css', filters=['cssrewrite', 'cssmin']),

        output='gen/admin.css',
        # cssrewrite helps find image files when ASSETS_DEBUG = False
        # filters=['cssrewrite', 'cssmin'],
        )
}

asset_env = Environment()
