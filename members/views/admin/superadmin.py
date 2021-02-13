'''
leadership_tasks_superadmin - administrative task handling for superuser
==============================================================================
'''
# standard
from re import match

# pypi

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, EmailTemplate, DocTemplate
from ...version import __docversion__

from loutilities.user.roles import ROLE_SUPER_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.tables import REGEX_EMAIL

class ParameterError(Exception): pass

debug = False

adminguide = 'https://members.readthedocs.io/en/{docversion}/super-admin-guide.html'.format(docversion=__docversion__)

##########################################################################################
# emailtemplates endpoint
###########################################################################################

emailtemplate_dbattrs = 'id,interest_id,templatename,subject,template,from_email'.split(',')
emailtemplate_formfields = 'rowid,interest_id,templatename,subject,template,from_email'.split(',')
emailtemplate_dbmapping = dict(zip(emailtemplate_dbattrs, emailtemplate_formfields))
emailtemplate_formmapping = dict(zip(emailtemplate_formfields, emailtemplate_dbattrs))

def emailtemplate_validate(action, formdata):
    results = []

    field = 'from_email'
    if formdata[field]:
        if not match(REGEX_EMAIL, formdata[field]):
            results.append({'name': field, 'status': 'please specify correct email format'})

    return results

emailtemplate_view = DbCrudApiInterestsRolePermissions(
    roles_accepted=[ROLE_SUPER_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=EmailTemplate,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Email Templates',
    endpoint='admin.emailtemplates',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/emailtemplates',
    dbmapping=emailtemplate_dbmapping,
    formmapping=emailtemplate_formmapping,
    checkrequired=True,
    validate=emailtemplate_validate,
    clientcolumns=[
        {'data': 'templatename', 'name': 'templatename', 'label': 'Template Name',
         'className': 'field_req',
         '_unique': True,
         },
        {'data': 'subject', 'name': 'subject', 'label': 'Subject',
         'className': 'field_req',
         },
        {'data': 'from_email', 'name': 'from_email', 'label': 'From Email',
         'fieldInfo': 'optional from address for this template, if empty uses From Email from Interest Attributes'
         },
        {'data': 'template', 'name': 'template', 'label': 'Template',
         'type': 'textarea',
         'render': '$.fn.dataTable.render.ellipsis( 40 )',
         'className': 'field_req',
         'fieldInfo': 'html with template substitution for text like {{member}}, {{membertasks}}, {{expires}}',
         },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=['create', 'editRefresh', 'csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
emailtemplate_view.register()

##########################################################################################
# doctemplates endpoint
###########################################################################################

doctemplate_dbattrs = 'id,interest_id,templatename,template'.split(',')
doctemplate_formfields = 'rowid,interest_id,templatename,template'.split(',')
doctemplate_dbmapping = dict(zip(doctemplate_dbattrs, doctemplate_formfields))
doctemplate_formmapping = dict(zip(doctemplate_formfields, doctemplate_dbattrs))

doctemplate_view = DbCrudApiInterestsRolePermissions(
    roles_accepted=[ROLE_SUPER_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=DocTemplate,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Document Templates',
    endpoint='admin.doctemplates',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/doctemplates',
    dbmapping=doctemplate_dbmapping,
    formmapping=doctemplate_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'templatename', 'name': 'templatename', 'label': 'Template Name',
         'className': 'field_req',
         '_unique': True,
         },
        {'data': 'template', 'name': 'template', 'label': 'Template',
         'type': 'textarea',
         'render': '$.fn.dataTable.render.ellipsis( 40 )',
         'className': 'field_req',
         'fieldInfo': 'html with template substitution for text like {{member}}, {{membertasks}}, {{expires}}',
         },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=['create', 'editRefresh', 'csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
doctemplate_view.register()

