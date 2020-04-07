'''
localinterest - local user and interest attribute views
===========================================================
'''

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest
from loutilities.user.model import Interest
from loutilities.tables import DbCrudApiRolePermissions
from loutilities.user.roles import ROLE_SUPER_ADMIN

##########################################################################################
# interestattrs endpoint
###########################################################################################

interestattr_dbattrs = 'id,__readonly__,initial_expiration'.split(',')
interestattr_formfields = 'rowid,interest,initial_expiration'.split(',')
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

