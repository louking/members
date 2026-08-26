'''
access_admin - system/access-type reference data and the position-access checklist, see #716
===============================================================================================
'''
# standard

# pypi
from flask import request
from flask_security import current_user

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, Position, System, SystemAccessLevel, AccessType, PositionAccessNotice
from ...model import localinterest_query_params
from .viewhelpers import dtrender, user2localuser
from ...version import __docversion__

from ...roles import ROLE_SYSTEMS_ADMIN

from loutilities.user.roles import ROLE_SUPER_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions

class ParameterError(Exception): pass

debug = False

systemsadmin_roles = [ROLE_SUPER_ADMIN, ROLE_SYSTEMS_ADMIN]
adminguide = 'https://members.readthedocs.io/en/{docversion}/systems-admin-guide.html'.format(
    docversion=__docversion__)

##########################################################################################
# systems endpoint
###########################################################################################

system_dbattrs = 'id,interest_id,name,slug,description,is_active'.split(',')
system_formfields = 'rowid,interest_id,name,slug,description,is_active'.split(',')
system_dbmapping = dict(zip(system_dbattrs, system_formfields))
system_formmapping = dict(zip(system_formfields, system_dbattrs))

system_view = DbCrudApiInterestsRolePermissions(
    roles_accepted=systemsadmin_roles,
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=System,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Systems',
    endpoint='admin.accesssystems',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/accesssystems',
    dbmapping=system_dbmapping,
    formmapping=system_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'name', 'name': 'name', 'label': 'System',
         'className': 'field_req',
         '_unique': True,
         },
        {'data': 'slug', 'name': 'slug', 'label': 'Slug',
         'className': 'field_req',
         '_unique': True,
         'fieldInfo': 'stable identifier used in the bootstrap CSVs (bundles.csv, access-report --actual-csv), e.g. "mailchimp"',
         },
        {'data': 'description', 'name': 'description', 'label': 'Description',
         'type': 'textarea',
         },
        {'data': 'is_active', 'name': 'is_active', 'label': 'Active',
         '_treatment': {'boolean': {'formfield': 'is_active', 'dbfield': 'is_active'}},
         'ed': {'def': 'yes'},
         },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=['create', 'editRefresh', 'remove', 'csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
system_view.register()

##########################################################################################
# systemaccesslevels endpoint
###########################################################################################

systemaccesslevel_dbattrs = 'id,interest_id,system,name,slug,description,is_active'.split(',')
systemaccesslevel_formfields = 'rowid,interest_id,system,name,slug,description,is_active'.split(',')
systemaccesslevel_dbmapping = dict(zip(systemaccesslevel_dbattrs, systemaccesslevel_formfields))
systemaccesslevel_formmapping = dict(zip(systemaccesslevel_formfields, systemaccesslevel_dbattrs))

systemaccesslevel_view = DbCrudApiInterestsRolePermissions(
    roles_accepted=systemsadmin_roles,
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=SystemAccessLevel,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='System Access Levels',
    endpoint='admin.accesssystemlevels',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/accesssystemlevels',
    dbmapping=systemaccesslevel_dbmapping,
    formmapping=systemaccesslevel_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'system', 'name': 'system', 'label': 'System',
         'className': 'field_req',
         '_treatment': {
             'relationship': {'fieldmodel': System, 'labelfield': 'name', 'formfield': 'system',
                              'dbfield': 'system', 'uselist': False,
                              'searchbox': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'name', 'name': 'name', 'label': 'Access Level',
         'className': 'field_req',
         'fieldInfo': 'e.g. "Super Admin"; give every system at least one level, even if just "Access"',
         },
        {'data': 'slug', 'name': 'slug', 'label': 'Slug',
         'className': 'field_req',
         'fieldInfo': 'stable identifier used in the bootstrap CSVs, unique within this system, e.g. "admin"',
         },
        {'data': 'description', 'name': 'description', 'label': 'Description',
         'type': 'textarea',
         },
        {'data': 'is_active', 'name': 'is_active', 'label': 'Active',
         '_treatment': {'boolean': {'formfield': 'is_active', 'dbfield': 'is_active'}},
         'ed': {'def': 'yes'},
         },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=['create', 'editRefresh', 'remove', 'csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
systemaccesslevel_view.register()

##########################################################################################
# accesstypes endpoint
###########################################################################################

accesstype_dbattrs = 'id,interest_id,name,slug,description,is_active,access'.split(',')
accesstype_formfields = 'rowid,interest_id,name,slug,description,is_active,access'.split(',')
accesstype_dbmapping = dict(zip(accesstype_dbattrs, accesstype_formfields))
accesstype_formmapping = dict(zip(accesstype_formfields, accesstype_dbattrs))

accesstype_view = DbCrudApiInterestsRolePermissions(
    roles_accepted=systemsadmin_roles,
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=AccessType,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Access Types',
    endpoint='admin.accesstypes',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/accesstypes',
    dbmapping=accesstype_dbmapping,
    formmapping=accesstype_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'name', 'name': 'name', 'label': 'Access Type',
         'className': 'field_req',
         '_unique': True,
         'fieldInfo': 'named bundle of system access shared by several positions, e.g. "Race Director access"',
         },
        {'data': 'slug', 'name': 'slug', 'label': 'Slug',
         'className': 'field_req',
         '_unique': True,
         'fieldInfo': 'stable identifier used in the bootstrap CSVs (bundles.csv, positions.csv), e.g. "race-director-access"',
         },
        {'data': 'description', 'name': 'description', 'label': 'Description',
         'type': 'textarea',
         },
        {'data': 'is_active', 'name': 'is_active', 'label': 'Active',
         '_treatment': {'boolean': {'formfield': 'is_active', 'dbfield': 'is_active'}},
         'ed': {'def': 'yes'},
         },
        {'data': 'access', 'name': 'access', 'label': 'System Access',
         '_treatment': {
             'relationship': {'fieldmodel': SystemAccessLevel, 'labelfield': 'label', 'formfield': 'access',
                              'dbfield': 'access', 'uselist': True,
                              'searchbox': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=['create', 'editRefresh', 'remove', 'csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
accesstype_view.register()

##########################################################################################
# access checklist endpoint
###########################################################################################

positionaccessnotice_dbattrs = ('id,interest_id,user,system,accesslevel,action,reason_position,'
                                 'effective_date,detected_at,resolved_at,__readonly__').split(',')
positionaccessnotice_formfields = ('rowid,interest_id,user,system,accesslevel,action,reason_position,'
                                    'effective_date,detected_at,resolved_at,resolvedby_display').split(',')
positionaccessnotice_dbmapping = dict(zip(positionaccessnotice_dbattrs, positionaccessnotice_formfields))
positionaccessnotice_formmapping = dict(zip(positionaccessnotice_formfields, positionaccessnotice_dbattrs))

positionaccessnotice_dbmapping['effective_date'] = lambda formrow: dtrender.asc2dt(formrow['effective_date']) \
    if formrow.get('effective_date') else None
positionaccessnotice_formmapping['effective_date'] = lambda dbrow: dtrender.dt2asc(dbrow.effective_date) \
    if dbrow.effective_date else ''
positionaccessnotice_formmapping['detected_at'] = lambda dbrow: dtrender.dt2asc(dbrow.detected_at) \
    if dbrow.detected_at else ''
# resolved_at is the one field an admin edits directly, to mark a checklist item resolved;
# resolved_by is stamped server-side (PositionAccessNoticeView.editor_method_posthook) rather
# than picked on the form, so resolving is a single-field edit
positionaccessnotice_dbmapping['resolved_at'] = lambda formrow: dtrender.asc2dt(formrow['resolved_at']) \
    if formrow.get('resolved_at') else None
positionaccessnotice_formmapping['resolved_at'] = lambda dbrow: dtrender.dt2asc(dbrow.resolved_at) \
    if dbrow.resolved_at else ''
positionaccessnotice_formmapping['resolvedby_display'] = lambda dbrow: dbrow.resolved_by.name \
    if dbrow.resolved_by else ''

class PositionAccessNoticeView(DbCrudApiInterestsRolePermissions):
    def editor_method_prehook(self, form):
        '''
        remember whether this notice was already resolved before the edit, so posthook can
        tell whether this edit is the one that just resolved it

        :param form: form data
        '''
        self._notice_was_resolved = None
        if self.action == 'edit':
            thisid = request.view_args.get('thisid')
            notice = PositionAccessNotice.query.filter_by(id=thisid).one_or_none() if thisid else None
            self._notice_was_resolved = bool(notice.resolved_at) if notice else None

    def editor_method_posthook(self, form):
        '''
        stamp resolved_by when this edit is what just set resolved_at (i.e. the notice
        wasn't already resolved coming in) -- see #716

        :param form: form data
        '''
        if self.action == 'edit' and self._notice_was_resolved is False:
            thisid = request.view_args.get('thisid')
            notice = PositionAccessNotice.query.filter_by(id=thisid).one_or_none() if thisid else None
            if notice and notice.resolved_at and not notice.resolved_by:
                notice.resolved_by = user2localuser(current_user)

positionaccessnotice_view = PositionAccessNoticeView(
    roles_accepted=systemsadmin_roles,
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=PositionAccessNotice,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Access Checklist',
    endpoint='admin.accesschecklist',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/accesschecklist',
    dbmapping=positionaccessnotice_dbmapping,
    formmapping=positionaccessnotice_formmapping,
    checkrequired=False,
    clientcolumns=[
        {'data': 'user', 'name': 'user', 'label': 'Member', 'type': 'readonly',
         '_treatment': {
             'relationship': {'fieldmodel': LocalUser, 'labelfield': 'name', 'formfield': 'user',
                              'dbfield': 'user', 'uselist': False,
                              'searchbox': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'action', 'name': 'action', 'label': 'Action', 'type': 'readonly'},
        {'data': 'system', 'name': 'system', 'label': 'System', 'type': 'readonly',
         '_treatment': {
             'relationship': {'fieldmodel': System, 'labelfield': 'name', 'formfield': 'system',
                              'dbfield': 'system', 'uselist': False,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'accesslevel', 'name': 'accesslevel', 'label': 'Access Level', 'type': 'readonly',
         '_treatment': {
             'relationship': {'fieldmodel': SystemAccessLevel, 'labelfield': 'label', 'formfield': 'accesslevel',
                              'dbfield': 'accesslevel', 'uselist': False,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'reason_position', 'name': 'reason_position', 'label': 'Position', 'type': 'readonly',
         '_treatment': {
             'relationship': {'fieldmodel': Position, 'labelfield': 'position', 'formfield': 'reason_position',
                              'dbfield': 'reason_position', 'uselist': False,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'effective_date', 'name': 'effective_date', 'label': 'Effective Date', 'type': 'readonly'},
        {'data': 'detected_at', 'name': 'detected_at', 'label': 'Detected', 'type': 'readonly'},
        {'data': 'resolved_at', 'name': 'resolved_at', 'label': 'Resolved',
         'type': 'datetime',
         'fieldInfo': 'set to mark this checklist item resolved',
         },
        {'data': 'resolvedby_display', 'name': 'resolvedby_display', 'label': 'Resolved By', 'type': 'readonly'},
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=['editRefresh', 'remove', 'csv'],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
positionaccessnotice_view.register()
