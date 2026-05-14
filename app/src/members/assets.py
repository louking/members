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
jq_ver = '3.7.1'
jq_ui_ver = '1.14.2'
jq_validate_ver = '1.19.3'

# dataTables
dt_datatables_ver = '2.3.8-pkgs-jqui'

jszip_ver = '2.5.0'

# select2
# NOTE: patch to jquery ui required, see https://github.com/select2/select2/issues/1246#issuecomment-17428249
# currently in datatables.js
s2_ver = '4.0.13'

# smartmenus
sm_ver = '1.1.1'

# yadcf
yadcf_ver = '2.0.1.beta.9.louking.3'
yadcf_suffix = '-2.0'

lodash_ver = '4.17.21'      # lodash.js (see https://lodash.com)

d3_ver = '7.1.1'            # d3js.org (see https://d3js.org/)
d3_tip_ver = '1.1'          # https://github.com/VACLab/d3-tip

fa_ver = '5.13.0'           # https://fontawesome.com/
nunjucks_ver = '3.2.0'      # https://mozilla.github.io/nunjucks/
cke_type='classic'           # https://ckeditor.com/ckeditor-5/
cke_ver='40.2.0-members-issue573' # https://ckeditor.com/ckeditor-5/
materialize_ver='1.0.0'     # https://materializecss.com/
pickadate_ver = '3.6.4'     # https://amsul.ca/pickadate.js/

frontend_common_js = Bundle(
    f'js/jquery-{jq_ver}/jquery-{jq_ver}.js',
    f'js/jquery-ui-{jq_ui_ver}.custom/jquery-ui.js',

    f'js/lodash-{lodash_ver}/lodash.js',

    f'js/smartmenus-{sm_ver}/jquery.smartmenus.js',

    # datatables / yadcf
    f'js/yadcf-{yadcf_ver}/jquery.dataTables.yadcf{yadcf_suffix}.js',

    # select2 is required for use by Editor forms and interest navigation
    f'js/select2-{s2_ver}/js/select2.full.js',
    # the order here is important
    'js/FieldType-Select2/editor.select2-v4.js',

    # d3
    'js/d3-{ver}/d3.js'.format(ver=d3_ver),
    'js/d3-tip-{ver}/d3-tip.js'.format(ver=d3_tip_ver),

    'frontend/beforedatatables.js',
    'admin/layout.js',  # TODO: smartmenus initialization, should be moved to layout.js
    'layout.js',

    'utils.js', # from loutilities

    'mutex-promise.js',                     # from loutilities
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

    filters='rjsmin',
    output='gen/frontendcommon.js',
)

frontend_materialize_js = Bundle(
    f'js/materialize-v{materialize_ver}/materialize/js/materialize.js',
    f'js/jquery-validate-{jq_validate_ver}/jquery.validate.js',
    
    filters='rjsmin',
    output='gen/frontendmaterialize.js',
)

frontend_common_css = Bundle(
    f'js/jquery-ui-{jq_ui_ver}.custom/jquery-ui.css',
    f'js/jquery-ui-{jq_ui_ver}.custom/jquery-ui.structure.css',
    f'js/jquery-ui-{jq_ui_ver}.custom/jquery-ui.theme.css',
    
    f'js/DataTables-{dt_datatables_ver}/datatables.css',

    f'js/select2-{s2_ver}/css/select2.css',
    f'js/yadcf-{yadcf_ver}/jquery.dataTables.yadcf.css',

    f'js/fontawesome-{fa_ver}/css/fontawesome.css', 
    f'js/fontawesome-{fa_ver}/css/solid.css', 

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
    f'js/materialize-v{materialize_ver}/materialize/css/materialize.css',

    filters=['cssrewrite', 'cssmin'],
    output='gen/frontendmaterialize.css',
)

frontend_members = Bundle(
    'frontend/membership-stats.js',
    
    filters='rjsmin',
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
        Bundle('js/jquery-{ver}/jquery-{ver}.js'.format(ver=jq_ver), filters='rjsmin'),
        Bundle('js/jquery-ui-{ver}.custom/jquery-ui.js'.format(ver=jq_ui_ver), filters='rjsmin'),

        Bundle('js/smartmenus-{ver}/jquery.smartmenus.js'.format(ver=sm_ver), filters='rjsmin'),
        Bundle('js/lodash-{ver}/lodash.js'.format(ver=lodash_ver), filters='rjsmin'),

        Bundle('js/JSZip-{ver}/jszip.js'.format(ver=jszip_ver), filters='rjsmin'),

        Bundle(f'js/DataTables-{dt_datatables_ver}/datatables.js', filters='rjsmin'),

        # select2 is required for use by Editor forms and interest navigation
        Bundle('js/select2-{ver}/js/select2.full.js'.format(ver=s2_ver), filters='rjsmin'),
        # the order here is important
        Bundle('js/FieldType-Select2/editor.select2-v4.js', filters='rjsmin'),

        Bundle(f'js/yadcf-{yadcf_ver}/jquery.dataTables.yadcf{yadcf_suffix}.js', filters='rjsmin'),

        # d3
        Bundle('js/d3-{ver}/d3.js'.format(ver=d3_ver), filters='rjsmin'),

        # ckeditor (note this is already minimized, and filter through jsmin causes problems)
        'js/ckeditor5-build-{type}-{ver}/build/ckeditor.js'.format(ver=cke_ver, type=cke_type),

        Bundle('admin/layout.js', filters='rjsmin'),
        Bundle('layout.js', filters='rjsmin'),

        # must be before datatables
        Bundle('mutex-promise.js', filters='rjsmin'),                     # from loutilities
        Bundle('editor-saeditor.js', filters='rjsmin'),                   # from loutilities
        Bundle('js/nunjucks-{ver}/nunjucks.js'.format(ver=nunjucks_ver), filters='rjsmin'),
        Bundle('admin/nunjucks/templates.js', filters='rjsmin'),
        Bundle('editor.fieldType.display.js', filters='rjsmin'),          # from loutilities
        Bundle('editor.ckeditor5.js', filters='rjsmin'),                  # from loutilities
        Bundle('admin/beforedatatables.js', filters='rjsmin'),
        Bundle('editor.googledoc.js', filters='rjsmin'),                  # from loutilities
        Bundle('datatables.dataRender.googledoc.js', filters='rjsmin'),   # from loutilities
        Bundle('user/admin/beforedatatables.js', filters='rjsmin'),       # from loutilities
        Bundle('editor.select2.mymethods.js', filters='rjsmin'),          # from loutilities
        Bundle('editor.displayController.onPage.js', filters='rjsmin'),   # from loutilities
        Bundle('datatables-childrow.js', filters='rjsmin'),               # from loutilities

        Bundle('datatables.js', filters='rjsmin'),                        # from loutilities

        # must be after datatables.js
        Bundle('datatables.dataRender.ellipsis.js', filters='rjsmin'),    # from loutilities
        Bundle('datatables.dataRender.datetime.js', filters='rjsmin'),    # from loutilities
        Bundle('editor.buttons.editrefresh.js', filters='rjsmin'),        # from loutilities
        Bundle('editor.buttons.editchildrowrefresh.js', filters='rjsmin'),  # from loutilities
        Bundle('editor.buttons.separator.js', filters='rjsmin'),          # from loutilities
        Bundle('filters.js', filters='rjsmin'),                           # from loutilities
        Bundle('utils.js', filters='rjsmin'),                             # from loutilities
        Bundle('user/admin/groups.js', filters='rjsmin'),                 # from loutilities

        # Bundle('admin/editor.buttons.invites.js', filters='rjsmin'),
        Bundle('admin/afterdatatables.js', filters='rjsmin'),

        output='gen/admin.js',
        ),

    'admin_css': Bundle(
        Bundle(f'js/jquery-ui-{jq_ui_ver}.custom/jquery-ui.css', filters=['cssrewrite', 'cssmin']),
        Bundle(f'js/jquery-ui-{jq_ui_ver}.custom/jquery-ui.structure.css', filters=['cssrewrite', 'cssmin']),
        Bundle(f'js/jquery-ui-{jq_ui_ver}.custom/jquery-ui.theme.css', filters=['cssrewrite', 'cssmin']),

        Bundle(f'js/DataTables-{dt_datatables_ver}/datatables.css', filters=['cssrewrite', 'cssmin']),

        Bundle(f'js/smartmenus-{sm_ver}/css/sm-core-css.css', filters=['cssrewrite', 'cssmin']),
        Bundle(f'js/smartmenus-{sm_ver}/css/sm-blue/sm-blue.css', filters=['cssrewrite', 'cssmin']),
       
        Bundle('js/select2-{ver}/css/select2.css'.format(ver=s2_ver), filters=['cssrewrite', 'cssmin']),
        Bundle(f'js/yadcf-{yadcf_ver}/jquery.dataTables.yadcf.css', filters=['cssrewrite', 'cssmin']),

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
