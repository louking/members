'''
leadership_tasks_superadmin - administrative task handling for superuser
==============================================================================
'''
# standard

# pypi

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, EmailTemplate

from loutilities.user.roles import ROLE_SUPER_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions

class ParameterError(Exception): pass

debug = False


##########################################################################################
# emailtemplates endpoint
###########################################################################################

emailtemplate_dbattrs = 'id,interest_id,templatename,subject,template'.split(',')
emailtemplate_formfields = 'rowid,interest_id,templatename,subject,template'.split(',')
emailtemplate_dbmapping = dict(zip(emailtemplate_dbattrs, emailtemplate_formfields))
emailtemplate_formmapping = dict(zip(emailtemplate_formfields, emailtemplate_dbattrs))

emailtemplate = DbCrudApiInterestsRolePermissions(
    roles_accepted=[ROLE_SUPER_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=EmailTemplate,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/leadership-task-superadmin-guide.html'},
    pagename='Email Templates',
    endpoint='admin.emailtemplates',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/emailtemplates',
    dbmapping=emailtemplate_dbmapping,
    formmapping=emailtemplate_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'templatename', 'name': 'templatename', 'label': 'Template Name',
         'className': 'field_req',
         '_unique': True,
         },
        {'data': 'subject', 'name': 'subject', 'label': 'Subject',
         'className': 'field_req',
         },
        {'data': 'template', 'name': 'template', 'label': 'Template',
         'type': 'textarea',
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
emailtemplate.register()

