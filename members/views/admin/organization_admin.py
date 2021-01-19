'''
organization_admin - organization administrative handling
===========================================
'''
# standard
from datetime import date, timedelta
from traceback import format_exception_only, format_exc

# pypi
from flask import request, jsonify, g, current_app, url_for
from flask.views import MethodView
from flask_security import current_user
from dominate.tags import div, input, button, dd

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, TaskGroup, AgendaHeading, UserPosition, Position, Tag
from ...model import localinterest_query_params, localinterest_viafilter
from ...helpers import members_active, all_active_members, member_position_active, member_positions
from .viewhelpers import dtrender, localinterest

from loutilities.user.model import User
from loutilities.filters import filtercontainerdiv, filterdiv, yadcfoption
from loutilities.tables import get_request_action, get_request_data, page_url_for
from loutilities.user.roles import ROLE_SUPER_ADMIN
from loutilities.user.roles import ROLE_MEMBERSHIP_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_LEADERSHIP_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions

class ParameterError(Exception): pass

debug = False

organization_roles = [ROLE_SUPER_ADMIN, ROLE_MEMBERSHIP_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_LEADERSHIP_ADMIN]

##########################################################################################
# positions endpoint
###########################################################################################

def position_members(position):
    ondate = request.args.get('ondate', None)
    if not ondate:
        ondate = date.today()
    names = [m.name for m in members_active(position, ondate)]
    names.sort()
    return ', '.join(names)

def position_pretablehtml():
    pretablehtml = div()
    with pretablehtml:
        # hide / show hidden rows
        with filtercontainerdiv(style='margin-bottom: 4px;'):
            datefilter = filterdiv('positiondate-external-filter-startdate', 'In Position On')

            with datefilter:
                input(type='text', id='effective-date', name='effective-date' )
                button('Today', id='todays-date-button')

        # make dom repository for Editor wizard standalone form
        with div(style='display: none;'):
            dd(**{'data-editor-field': 'position_id'})
            dd(**{'data-editor-field': 'effective'})
            dd(**{'data-editor-field': 'members'})

    return pretablehtml.render()

position_dbattrs = 'id,interest_id,position,description,taskgroups,emailgroups,has_status_report,tags,agendaheading,__readonly__'.split(',')
position_formfields = 'rowid,interest_id,position,description,taskgroups,emailgroups,has_status_report,tags,agendaheading,users'.split(',')
position_dbmapping = dict(zip(position_dbattrs, position_formfields))
position_formmapping = dict(zip(position_formfields, position_dbattrs))
position_formmapping['users'] = position_members

position = DbCrudApiInterestsRolePermissions(
                    roles_accepted = organization_roles,
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Position,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/organization-admin-guide.html'},
                    pagename = 'Positions',
                    endpoint = 'admin.positions',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/positions',
                    dbmapping = position_dbmapping,
                    formmapping = position_formmapping,
                    pretablehtml = position_pretablehtml,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'position', 'name': 'position', 'label': 'Position',
                         'className': 'field_req',
                         '_unique': True,
                         },
                        {'data': 'description', 'name': 'description', 'label': 'Description',
                         'type': 'textarea',
                         },
                        {'data': 'users', 'name': 'users', 'label': 'Members',
                         'fieldInfo': 'members who hold this position on selected position date', 'type': 'readonly'
                         },
                        {'data': 'has_status_report', 'name': 'has_status_report', 'label': 'Has Status Report',
                         'className': 'TextCenter',
                         '_treatment': {'boolean': {'formfield': 'has_status_report', 'dbfield': 'has_status_report'}},
                         'ed': {'def': 'yes'},
                         },
                        {'data': 'tags', 'name': 'tags', 'label': 'Tags',
                         'fieldInfo': 'tags for this position',
                         '_treatment': {
                             'relationship': {'fieldmodel': Tag, 'labelfield': 'tag', 'formfield': 'tags',
                                              'dbfield': 'tags', 'uselist': True,
                                              'searchbox': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'agendaheading', 'name': 'agendaheading', 'label': 'Agenda Heading',
                         'fieldInfo': 'heading under which this position is shown in agenda',
                         '_treatment': {
                             'relationship': {'fieldmodel': AgendaHeading, 'labelfield': 'heading', 'formfield': 'agendaheading',
                                              'dbfield': 'agendaheading', 'uselist': False,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'taskgroups', 'name': 'taskgroups', 'label': 'Task Groups',
                         'fieldInfo': 'members who hold this position must do tasks within these groups',
                         '_treatment': {
                             'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup', 'formfield': 'taskgroups',
                                              'dbfield': 'taskgroups', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'emailgroups', 'name': 'emailgroups', 'label': 'Email Groups',
                         'fieldInfo': 'members holding this position receive summary emails about other members configured with these groups',
                         '_treatment': {
                             'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup',
                                              'formfield': 'emailgroups',
                                              'dbfield': 'emailgroups', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid',
                    buttons = lambda: [
                        'create',
                        'editRefresh',
                        'remove',
                        {
                            'text': 'Position Wizard',
                            'name': 'position-wizard',
                            'editor': {'eval': 'position_wizard_editor'},
                            'url': url_for('admin.positionwizard', interest=g.interest),
                            'action': 'position_wizard("{}")'.format(url_for('admin.positionwizard', interest=g.interest)),
                        },
                        'csv'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
position.register()


##########################################################################################
# positiondates endpoint
###########################################################################################

positiondate_dbattrs = 'id,interest_id,user,position,user.taskgroups,user.tags,startdate,finishdate'.split(',')
positiondate_formfields = 'rowid,interest_id,user,position,taskgroups,tags,startdate,finishdate'.split(',')
positiondate_dbmapping = dict(zip(positiondate_dbattrs, positiondate_formfields))
positiondate_formmapping = dict(zip(positiondate_formfields, positiondate_dbattrs))
# see https://github.com/DataTables/Plugins/commit/eb06604fdc9d5
# see https://datatables.net/forums/discussion/25433
positiondate_dbmapping['startdate'] = lambda formrow: dtrender.asc2dt(formrow['startdate'])
positiondate_formmapping['startdate'] = lambda dbrow: dtrender.dt2asc(dbrow.startdate)
positiondate_dbmapping['finishdate'] = lambda formrow: dtrender.asc2dt(formrow['finishdate']) if formrow['finishdate'] else None
# positiondate_formmapping['finishdate'] = lambda dbrow: dtrender.dt2asc(dbrow.finishdate) if dbrow.finishdate else None
positiondate_formmapping['finishdate'] = lambda dbrow: dtrender.dt2asc(dbrow.finishdate) if dbrow.finishdate else ''

class PositionDateView(DbCrudApiInterestsRolePermissions):
    def editor_method_postcommit(self, formdata):
        '''
        updates to taskgroups and tags affect multiple rows related to the user(s) impacted, so need to update
        self._responsedata to show changes to those rows

        :param formdata: form data
        '''
        super().editor_method_postcommit(formdata)
        action = get_request_action(formdata)
        if action == 'edit':
            userids = set()
            upids = set()
            for row in self._responsedata:
                userids.add(row['user']['id'])
                upids.add(row['rowid'])
            otherrows = []
            for userid in userids:
                ups = UserPosition.query.filter_by(user_id=userid).all()
                otherrows += [self.dte.get_response_data(up) for up in ups if up.id not in upids]
            self._responsedata += otherrows

def positiondate_pretablehtml():
    pretablehtml = div()
    with pretablehtml:
        # hide / show hidden rows
        with filtercontainerdiv(style='margin-bottom: 4px;'):
            filterdiv('positiondate-external-filter-startdate', 'In Position On')

        # with datefilter:
        #     label('In Position On', _for='effective-date')
        #     input(type='text', id='effective-date', name='effective-date', value=dtrender.dt2asc(date.today()))
        #     a('Clear Date', id='clear-date', href='#')
        # filters = div(style='display: none;')
    return pretablehtml.render()

positiondate_yadcf_options = {
    # 'general': {'cumulative_filtering': True},
    'columns': [
        yadcfoption('startdate:name', 'positiondate-external-filter-startdate', 'date_custom_func',
                    custom_func={'eval': 'yadcf_between_dates("startdate", "finishdate")'},
                    filter_reset_button_text='Clear Date',
                    ),
        # yadcfoption('finishdate:name', 'positiondate-external-filter-finishdate', 'range_date'),
    ]
}

positiondate = PositionDateView(
    roles_accepted=organization_roles,
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=UserPosition,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/organization-admin-guide.html'},
    pagename='Position Dates',
    endpoint='admin.positiondates',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/positiondates',
    dbmapping=positiondate_dbmapping,
    formmapping=positiondate_formmapping,
    checkrequired=True,
    pretablehtml=positiondate_pretablehtml,
    yadcfoptions=positiondate_yadcf_options,
    clientcolumns=[
        {'data': 'user', 'name': 'user', 'label': 'Member',
         'className': 'field_req',
         '_treatment': {
             'relationship': {'fieldmodel': LocalUser, 'labelfield': 'name', 'formfield': 'user',
                              'dbfield': 'user', 'uselist': False,
                              'searchbox': True,
                              'queryparams': lambda: dict(**{'active': True}, **localinterest_query_params()),
                              }}
         },
        {'data': 'position', 'name': 'position', 'label': 'Position',
         'className': 'field_req',
         'fieldInfo': 'tasks are assigned via position, task groups, or both',
         '_treatment': {
             'relationship': {'fieldmodel': Position, 'labelfield': 'position', 'formfield': 'position',
                              'dbfield': 'position', 'uselist': False,
                              'searchbox': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'startdate', 'name': 'startdate', 'label': 'Start Date',
         'type': 'datetime',
         'className': 'field_req',
         # 'render': {'eval': 'render_date()'},
         },
        {'data': 'finishdate', 'name': 'finishdate', 'label': 'Finish Date',
         'type': 'datetime',
         # 'render': {'eval': 'render_date()'},
         },
        # {'data': 'taskgroups', 'name': 'taskgroups', 'label': 'Task Groups',
        #  'fieldInfo': 'tasks are generally assigned via position',
        #  '_treatment': {
        #      'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup',
        #                       'viasubrecord': 'user',
        #                       'formfield': 'taskgroups',
        #                       'dbfield': 'taskgroups', 'uselist': True,
        #                       'queryparams': localinterest_query_params,
        #                       }}
        #  },
        # {'data': 'tags', 'name': 'tags', 'label': 'Tags',
        #  'fieldInfo': 'tasks are generally assigned via position',
        #  '_treatment': {
        #      'relationship': {'fieldmodel': Tag, 'labelfield': 'tag',
        #                       'viasubrecord': 'user',
        #                       'formfield': 'tags',
        #                       'dbfield': 'tags', 'uselist': True,
        #                       'queryparams': localinterest_query_params,
        #                       }}
        #  },
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
positiondate.register()

##########################################################################################
# tags endpoint
###########################################################################################

tag_dbattrs = 'id,interest_id,tag,description,positions,users'.split(',')
tag_formfields = 'rowid,interest_id,tag,description,positions,users'.split(',')
tag_dbmapping = dict(zip(tag_dbattrs, tag_formfields))
tag_formmapping = dict(zip(tag_formfields, tag_dbattrs))

tags_view = DbCrudApiInterestsRolePermissions(
    roles_accepted=[ROLE_SUPER_ADMIN, ROLE_MEETINGS_ADMIN],
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=Tag,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/organization-admin-guide.html'},
    pagename='Tags',
    endpoint='admin.tags',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/tags',
    dbmapping=tag_dbmapping,
    formmapping=tag_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'tag', 'name': 'tag', 'label': 'Tag',
         'className': 'field_req',
         '_unique': True,
         },
        {'data': 'description', 'name': 'description', 'label': 'Description',
         'className': 'field_req',
         'type': 'textarea',
         },
        {'data': 'positions', 'name': 'positions', 'label': 'Positions',
         'fieldInfo': 'tags are assigned to positions, members, or both',
         '_treatment': {
             'relationship': {'fieldmodel': Position, 'labelfield': 'position', 'formfield': 'positions',
                              'dbfield': 'positions', 'uselist': True,
                              'searchbox': True,
                              'queryparams': localinterest_query_params,
                              }}
         },
        {'data': 'users', 'name': 'users', 'label': 'Members',
         'fieldInfo': 'tags are assigned to positions, members, or both',
         '_treatment': {
             # viadbattr stores the LocalUser id which has user_id=user.id for each of these
             # and pulls the correct users out of User based on LocalUser table
             'relationship': {'fieldmodel': User, 'labelfield': 'name',
                              'formfield': 'users', 'dbfield': 'users',
                              'viadbattr': LocalUser.user_id,
                              'viafilter': localinterest_viafilter,
                              'searchbox': True,
                              'queryparams': {'active': True},
                              'uselist': True}}
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
tags_view.register()

##########################################################################################
# positionwizard endpoint
###########################################################################################

class PositionWizardApi(MethodView):

    def __init__(self):
        self.roles_accepted = organization_roles

    def permission(self, position_id):
        '''
        determine if current user is permitted to use the view

        :param position_id: position id is passed into permission because it is obtained differently depending on method
        '''
        # adapted from loutilities.tables.DbCrudApiRolePermissions
        allowed = False

        if position_id:
            self.position = Position.query.filter_by(id=position_id, interest=localinterest()).one_or_none()
            if self.position:
                for role in self.roles_accepted:
                    if current_user.has_role(role):
                        allowed = True
                        break

        return allowed

    def get(self):
        try:
            # verify user can write the data, otherwise abort (adapted from loutilities.tables._editormethod)
            if not self.permission(request.args.get('values[position_id]', False)):
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            # if effectivedate set, get all members and members in position on that date
            effectivedate = request.args.get('values[effective]', None)
            if effectivedate:
                # get all members
                allmembers = [{'label': m.name, 'value': m.id} for m in all_active_members()]
                allmembers.sort(key=lambda i: i['label'])

                # get members who hold this position on effective date
                posmembers = [m.id for m in members_active(self.position, effectivedate)]

            # no effective date yet, leave select empty
            else:
                allmembers = []
                posmembers = []

            return jsonify(options={'members':allmembers}, values={'members': posmembers})

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status': 'fail', 'error': 'exception occurred:\n{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

    def post(self):
        try:
            requestdata = get_request_data(request.form)
            # verify user can write the data, otherwise abort (adapted from loutilities.tables._editormethod)
            # there should be one 'id' in this form data, 'keyless'
            if not self.permission(requestdata['keyless']['position_id']):
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            # get current members who previously held position on effective date
            effectivedate = requestdata['keyless']['effective']
            effectivedatedt = dtrender.asc2dt(effectivedate).date()
            currmembers = members_active(self.position, effectivedate)

            # get the members which admin wants to be in the position on the effective date
            # separator must match afterdatatables.js else if (location.pathname.includes('/positions'))
            resultmemberids = requestdata['keyless']['members'].split(', ')
            resultmembers = [LocalUser.query.filter_by(id=id).one() for id in resultmemberids]

            # terminate all current members in this position who should not remain in the result set
            # use date one day before effective date for new finish date
            previousdatedt = dtrender.asc2dt(effectivedate).date() - timedelta(1)
            for currmember in currmembers:
                if currmember not in resultmembers:
                    ups = member_position_active(currmember, self.position, effectivedate)
                    # more than one returned implies data error, needs to be fixed externally
                    if len(ups) > 1:
                        db.session.rollback()
                        cause = 'existing position "{}" date overlap detected for {} on {}. Use ' \
                                '<a href="{}" target=_blank>Position Dates view</a> ' \
                                'to fix before proceeding'.format(self.position.position, currmember.name, effectivedate,
                                                                  page_url_for('admin.positiondates', interest=g.interest))
                        return jsonify(error=cause)
                    # overwrite finishdate -- maybe this was empty or maybe it had a date in it, either way now finished
                    # day before effective date
                    ups[0].finishdate = previousdatedt
                    # note if none were returned there is some logic error, should not happen because currmembers pulled
                    # in current records, so let exception handling play through

            # create new record for all resultmembers not already in the position
            # if the new member has a future record, back date the start
            for resultmember in resultmembers:
                if not resultmember in currmembers:
                    ups = member_positions(resultmember, self.position, onorafter=effectivedate)
                    # normal case is no future records, so create a new one
                    if len(ups) == 0:
                        thisups = UserPosition(interest=localinterest(),
                                               user=resultmember, position=self.position, startdate=effectivedatedt)
                        db.session.add(thisups)
                    # if a future record exists for this member/position, update the start date of the earliest one
                    # to merge the position/user term
                    else:
                        thisups = ups[0]
                        thisups.startdate = effectivedatedt

            # commit all the changes and return success
            # NOTE: in afterdatatables.js else if (location.pathname.includes('/positions'))
            # table is redrawn on submitComplete in case this action caused visible changes
            output_result = {'status' : 'success'}
            db.session.commit()
            return jsonify(output_result)

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status' : 'fail', 'error': 'exception occurred:\n{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

bp.add_url_rule('/<interest>/_positionwizard/rest', view_func=PositionWizardApi.as_view('positionwizard'),
                methods=['GET', 'POST'])