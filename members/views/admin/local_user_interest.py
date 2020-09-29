'''
localinterest - local user and interest attribute views
===========================================================
'''
# standard
from datetime import date
from re import compile

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, Tag, localinterest_query_params
from ...model import all_club_services
from loutilities.user.model import Interest
from loutilities.tables import DbCrudApiRolePermissions
from loutilities.user.roles import ROLE_SUPER_ADMIN

##########################################################################################
# interestattrs endpoint
###########################################################################################

def interestattr_validate(action, formdata):
    results = []

    datepattern = compile('^(19|20)\d\d[-](0[1-9]|1[012])[-](0[1-9]|[12][0-9]|3[01])$')
    if formdata['initial_expiration'] and not datepattern.match(formdata['initial_expiration']):
        results.append({'name': 'initial_expiration', 'status': 'must be formatted as YYYY-MM-DD'})

    return results

interestattr_dbattrs = 'id,__readonly__,initial_expiration,from_email,club_service,service_id,'\
                       'interestmeetingtags,interestmeetingvotetags,'\
                       'gs_agenda_fdr,gs_status_fdr,gs_minutes_fdr'.split(',')
interestattr_formfields = 'rowid,interest,initial_expiration,from_email,club_service,service_id,'\
                          'interestmeetingtags,interestmeetingvotetags,'\
                          'gs_agenda_fdr,gs_status_fdr,gs_minutes_fdr'.split(',')
interestattr_dbmapping = dict(zip(interestattr_dbattrs, interestattr_formfields))
interestattr_formmapping = dict(zip(interestattr_formfields, interestattr_dbattrs))
interestattr_dbmapping['initial_expiration'] = lambda formrow: date(*[int(f) for f in formrow['initial_expiration'].split('-')])
interestattr_formmapping['initial_expiration'] = lambda dbrow: dbrow.initial_expiration.isoformat() if dbrow.initial_expiration else None

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
                    validate = interestattr_validate,
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
                        {'data': 'interestmeetingtags', 'name': 'interestmeetingtags', 'label': 'Meeting Invite Tags',
                         'fieldInfo': 'members who have these tags, either directly or via position, will be invited to the meeting',
                         '_treatment': {
                             'relationship': {'fieldmodel': Tag, 'labelfield': 'tag', 'formfield': 'interestmeetingtags',
                                              'dbfield': 'interestmeetingtags', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'interestmeetingvotetags', 'name': 'interestmeetingvotetags', 'label': 'Meeting Vote Tags',
                         'fieldInfo': 'members who have these tags, either directly or via position, can vote on motions',
                         '_treatment': {
                             'relationship': {'fieldmodel': Tag, 'labelfield': 'tag', 'formfield': 'interestmeetingvotetags',
                                              'dbfield': 'interestmeetingvotetags', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'gs_agenda_fdr', 'name': 'gs_agenda_fdr', 'label': 'GSuite Agenda Folder',
                         # 'type': 'googledoc',
                         'fieldInfo': 'g suite folder id for generated agendas',
                         },
                        {'data': 'gs_status_fdr', 'name': 'gs_status_fdr', 'label': 'GSuite Status Folder',
                         # 'type': 'googledoc',
                         'fieldInfo': 'g suite folder id for generated status reports',
                         },
                        {'data': 'gs_minutes_fdr', 'name': 'gs_minutes_fdr', 'label': 'GSuite Minutes Folder',
                         # 'type': 'googledoc',
                         'fieldInfo': 'g suite folder id for generated minutess',
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

