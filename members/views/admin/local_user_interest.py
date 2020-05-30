'''
localinterest - local user and interest attribute views
===========================================================
'''

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest
from ...model import all_club_services
from loutilities.user.model import Interest
from loutilities.tables import DbCrudApiRolePermissions
from loutilities.user.roles import ROLE_SUPER_ADMIN

##########################################################################################
# interestattrs endpoint
###########################################################################################

interestattr_dbattrs = 'id,__readonly__,initial_expiration,from_email,club_service,service_id'.split(',')
interestattr_formfields = 'rowid,interest,initial_expiration,from_email,club_service,service_id'.split(',')
interestattr_dbmapping = dict(zip(interestattr_dbattrs, interestattr_formfields))
interestattr_formmapping = dict(zip(interestattr_formfields, interestattr_dbattrs))

interestattr_formmapping['interest'] = lambda li: Interest.query.filter_by(id=li.interest_id).one().description

interestattr = DbCrudApiRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN],
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = LocalInterest,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/leadership-task-superadmin-guide.html'},
                    pagename = 'Interest Attributes',
                    endpoint = 'admin.interestattrs',
                    rule = '/interestattrs',
                    dbmapping = interestattr_dbmapping,
                    formmapping = interestattr_formmapping,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'interest', 'name': 'interest', 'label': 'Interest',
                         'type': 'readonly',
                         },
                        {'data': 'initial_expiration', 'name': 'initial_expiration', 'label': 'Initial Expiration',
                         'fieldInfo': 'Expiration date displayed when task was never completed',
                         'className': 'field_req',
                         'type': 'datetime',
                         },
                        {'data': 'from_email', 'name': 'from_email', 'label': 'From Email',
                         'fieldInfo': 'Email address from which automated messages are sent',
                         'className': 'field_req',
                         },
                        {'data': 'club_service', 'name': 'club_service', 'label': 'Club Service',
                         'fieldInfo': 'Service from which club member data is downloaded',
                         'className': 'field_req',
                         'type': 'select2',
                         'options': all_club_services,
                         },
                        {'data': 'service_id', 'name': 'service_id', 'label': 'Service ID',
                         'fieldInfo': 'ID which Club Service uses for club member access',
                         'className': 'field_req',
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid',
                    buttons = ['editRefresh'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
interestattr.register()

