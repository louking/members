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
from dominate.tags import div, input_, button, dd

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, TaskGroup, AgendaHeading, UserPosition, Position, Tag
from ...model import localinterest_query_params, localinterest_viafilter
from ...helpers import members_active, member_qualifiers_active, memberqualifierstr, all_active_members
from ...helpers import member_position_active, member_positions, positions_active, members_active_currfuture
from .viewhelpers import dtrender, localinterest
from ...version import __docversion__

from loutilities.user.model import User, Interest, Role
from loutilities.filters import filtercontainerdiv, filterdiv, yadcfoption
from loutilities.tables import get_request_action, get_request_data, page_url_for, SEPARATOR
from loutilities.user.roles import ROLE_SUPER_ADMIN
from loutilities.user.roles import ROLE_MEMBERSHIP_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_LEADERSHIP_ADMIN, ROLE_RACINGTEAM_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions, DteDbOptionsPickerBase

class ParameterError(Exception): pass

debug = False

organization_roles = [ROLE_SUPER_ADMIN, ROLE_MEMBERSHIP_ADMIN, ROLE_MEETINGS_ADMIN, ROLE_LEADERSHIP_ADMIN, ROLE_RACINGTEAM_ADMIN]
adminguide = 'https://members.readthedocs.io/en/{docversion}/organization-admin-guide.html'.format(
    docversion=__docversion__)


##########################################################################################
# positions endpoint
###########################################################################################

def position_members(position):
    ondate = request.args.get('ondate', None)
    if not ondate:
        ondate = date.today()
    names = [memberqualifierstr(m) for m in member_qualifiers_active(position, ondate)]
    names.sort()
    return ', '.join(names)

def position_pretablehtml():
    pretablehtml = div()
    with pretablehtml:
        # hide / show hidden rows
        with filtercontainerdiv(style='margin-bottom: 4px;'):
            datefilter = filterdiv('positiondate-external-filter-startdate', 'In Position On')

            with datefilter:
                input_(type='text', id='effective-date', name='effective-date' )
                button('Today', id='todays-date-button')

        # make dom repository for Editor wizard standalone form
        with div(style='display: none;'):
            dd(**{'data-editor-field': 'position_id'})
            dd(**{'data-editor-field': 'effective'})
            dd(**{'data-editor-field': 'members'})

    return pretablehtml.render()

position_dbattrs = 'id,interest_id,position,description,taskgroups,emailgroups,tags,agendaheading,__readonly__'.split(',')
position_formfields = 'rowid,interest_id,position,description,taskgroups,emailgroups,tags,agendaheading,users'.split(',')
position_dbmapping = dict(zip(position_dbattrs, position_formfields))
position_formmapping = dict(zip(position_formfields, position_dbattrs))
position_formmapping['users'] = position_members

position_view = DbCrudApiInterestsRolePermissions(
                    roles_accepted = organization_roles,
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Position,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': adminguide},
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
position_view.register()


##########################################################################################
# positiondates endpoint
###########################################################################################

positiondate_dbattrs = 'id,interest_id,user,position,user.taskgroups,user.tags,startdate,finishdate,qualifier'.split(',')
positiondate_formfields = 'rowid,interest_id,user,position,taskgroups,tags,startdate,finishdate,qualifier'.split(',')
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

positiondate_view = PositionDateView(
    roles_accepted=organization_roles,
    local_interest_model=LocalInterest,
    app=bp,  # use blueprint instead of app
    db=db,
    model=UserPosition,
    version_id_col='version_id',  # optimistic concurrency control
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
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
                              'queryparams': lambda: localinterest_query_params(),
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
        {'data': 'qualifier', 'name': 'qualifier', 'label': 'Qualifier',
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
positiondate_view.register()

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
    templateargs={'adminguide': adminguide},
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
                membersqualifiers = member_qualifiers_active(self.position, effectivedate)
                posmembers = [m['member'].id for m in membersqualifiers]
                
                # for case where there's only one member, there may be a qualifier
                # NOTE: there could potentially be a qualifier if there's more than one member, 
                #       but there's no way to display it
                qualifier = ''
                if len(membersqualifiers) == 1 and membersqualifiers[0]['qualifier']:
                    qualifier = membersqualifiers[0]['qualifier']

            # no effective date yet, leave select empty
            else:
                allmembers = []
                posmembers = []
                qualifier = ''

            return jsonify(options={'members':allmembers}, values={'members': posmembers, 'qualifier': qualifier})

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

            # there may be a qualifier for this position, e.g., "interim"; 
            # normally blank so set to None if so for backwards compatibility with the database after 
            # initial conversion to include qualifier
            qualifier = requestdata['keyless']['qualifier']
            if not qualifier:
                qualifier = None
            
            # get the members which admin wants to be in the position on the effective date
            # separator must match afterdatatables.js else if (location.pathname.includes('/positions'))
            # (if empty string is returned, there were no memberids, so use empty list)
            resultmemberids = []
            if requestdata['keyless']['members']:
                resultmemberids = requestdata['keyless']['members'].split(', ')
            resultmembers = [LocalUser.query.filter_by(id=id).one() for id in resultmemberids]

            # terminate all future user/positions in this position as we're basing our update on effectivedate assertion by admin
            # delete all of these which are strictly in the future
            currfuturemembers = members_active_currfuture(self.position, onorafter=effectivedate)
            for member in currfuturemembers:
                ups = member_positions(member, self.position, onorafter=effectivedate)
                for up in ups:
                    if up.startdate > effectivedatedt:
                        current_app.logger.debug(f'organization_admin.PositionWizardApi.post: deleting {up.user.name} {up.position.position} {up.startdate}')
                        db.session.delete(up)
            db.session.flush()

            # get current members who previously held position on effective date
            currmembers = members_active(self.position, effectivedate)

            # terminate all current members in this position who should not remain in the result set
            # use date one day before effective date for new finish date
            previousdatedt = dtrender.asc2dt(effectivedate).date() - timedelta(1)
            for currmember in currmembers:
                ups = member_position_active(currmember, self.position, effectivedate)
                # more than one returned implies data error, needs to be fixed externally
                if len(ups) > 1:
                    db.session.rollback()
                    cause = 'existing position "{}" date overlap detected for {} on {}. Use ' \
                            '<a href="{}" target=_blank>Position Dates view</a> ' \
                            'to fix before proceeding'.format(self.position.position, currmember.name, effectivedate,
                                                                page_url_for('admin.positiondates', interest=g.interest))
                    return jsonify(error=cause)

                # also if none were returned there is some logic error, should not happen because currmembers pulled
                # in current records
                if not ups:
                    db.session.rollback()
                    cause = f'logic error: {currmember.name} not found for {self.position.position} on {effectivedate}. Please report to administrator'
                    return jsonify(error=cause)
                    
                currup = ups[0]
                
                # if the current member isn't one of the members in the position starting effective date,
                if currmember not in resultmembers:
                    # overwrite finishdate -- maybe this was empty or maybe it had a date in it, either way now finished
                    # day before effective date
                    currup.finishdate = previousdatedt
                    
                    # if the finish date is now before the start date, we can delete this record, to be tidy
                    if currup.finishdate < currup.startdate:
                        db.session.delete(currup)
                        db.session.flush()

            # loop through all members who are to be in the position as of effective date
            for resultmember in resultmembers:
                # check user/positions for this member on or after effective date
                ups = member_positions(resultmember, self.position, onorafter=effectivedate)

                # create new record for all resultmembers not already in the position
                # if the new member has a future record, move date the start of the future record to the effective date
                if resultmember not in currmembers:
                    # normal case is no future records, so create a new record as of effectivedate
                    if len(ups) == 0:
                        thisups = UserPosition(
                            interest=localinterest(),
                            user=resultmember, 
                            position=self.position, 
                            startdate=effectivedatedt,
                            qualifier=qualifier,
                        )
                        db.session.add(thisups)
                        
                # if resultmember is in currmembers, but the qualifier has changed
                # NOTE: ups[0] is the user/position which is active on the effective date
                elif ups and ups[0].qualifier != qualifier:
                    currup = ups[0]
                    if len(ups) > 1:
                        # logic prevents use of futureup if not defined
                        futureup = ups[1]
                        
                    # overwrite finishdate -- maybe this was empty or maybe it had a date in it, either way now finished
                    # day before effective date
                    finishdate = currup.finishdate
                    currup.finishdate = previousdatedt
                    
                    # if the finish date is now before the start date, we can delete this record, to be tidy
                    if currup.finishdate < currup.startdate:
                        db.session.delete(currup)
                        db.session.flush()
                    
                    # normal case there's only one current or future user/position, so create new one to follow this one
                    if len(ups) == 1:
                        thisups = UserPosition(
                            interest=localinterest(),
                            user=resultmember, 
                            position=self.position, 
                            startdate=effectivedatedt,
                            finishdate=None,
                            qualifier=qualifier,
                        )
                        db.session.add(thisups)
                        
                    # if there's a future user/position, and it was right after the current, the qualifier has most likely changed
                    # assuming the qualifer of the future user/position is the new qualifier, move the start date of the future record
                    # NOTE: there should be no future records at this point, so this clause should not get executed
                    elif futureup.qualifier == qualifier and futureup.startdate == finishdate + timedelta(1):
                        futureup.startdate = previousdatedt + timedelta(1)
                
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

##########################################################################################
# distribution endpoint
###########################################################################################

def distribution_pretablehtml():
    pretablehtml = div()
    with pretablehtml:
        # hide / show hidden rows
        with filtercontainerdiv(style='margin-bottom: 4px;'):
            filterdiv('distribution-external-filter-tags', 'Tags')
            filterdiv('distribution-external-filter-positions', 'Positions')
            filterdiv('distribution-external-filter-roles', 'Roles')

            with filterdiv('distribution-external-filter-startdate', 'In Position On'):
                input_(type='text', id='effective-date', name='effective-date', _class='like-select2-sizing' )
                button('Today', id='todays-date-button')

    return pretablehtml.render()

distribution_yadcf_options = [
    yadcfoption('tags.tag:name', 'distribution-external-filter-tags', 'multi_select',
                placeholder='Select tags', width='200px'),
    yadcfoption('positions.position:name', 'distribution-external-filter-positions', 'multi_select',
                placeholder='Select positions', width='200px'),
    yadcfoption('roles.role:name', 'distribution-external-filter-roles', 'multi_select',
                placeholder='Select roles', width='200px'),
]

distribution_dbattrs = 'id,interest_id,name,email,__readonly__,__readonly__,__readonly__'.split(',')
distribution_formfields = 'rowid,interest_id,name,email,positions,tags,roles'.split(',')
distribution_dbmapping = dict(zip(distribution_dbattrs, distribution_formfields))
distribution_formmapping = dict(zip(distribution_formfields, distribution_dbattrs))

class PositionsPicker(DteDbOptionsPickerBase):
    def __init__(self):
        super().__init__(
            labelfield='position',
        )

    def get(self, dbrow_or_id):
        localuser = self.get_dbrow(dbrow_or_id)
        ondate = request.args.get('ondate', date.today())
        positions = positions_active(localuser, ondate)
        positions.sort(key=lambda p: p.position.lower())
        labelitems = [p.position for p in positions]
        valueitems = [str(p.id) for p in positions]
        items = {'position': SEPARATOR.join(labelitems), 'id': SEPARATOR.join(valueitems)}
        return items

    def options(self):
        positions = Position.query.filter_by(interest=localinterest()).all()
        positions.sort(key=lambda p: p.position.lower())
        options = [{'label': p.position, 'value': p.id} for p in positions]
        return options

    def col_options(self):
        col = {}
        col['type'] = 'select2'
        col['onFocus'] = 'focus'
        col['opts'] = {'minimumResultsForSearch': 0 if self.searchbox else 'Infinity',
                       'multiple': True}
        col['separator'] = SEPARATOR
        return col

class TagsPicker(DteDbOptionsPickerBase):
    def __init__(self):
        super().__init__(
            labelfield='tag'
        )

    def get(self, dbrow_or_id):
        localuser = self.get_dbrow(dbrow_or_id)
        ondate = request.args.get('ondate', date.today())
        positions = positions_active(localuser, ondate)
        active_tags = set()
        for p in positions:
            active_tags |= set(p.tags)
        tags = list(active_tags)
        tags.sort(key=lambda t: t.tag.lower())

        labelitems = [t.tag for t in tags]
        valueitems = [str(t.id) for t in tags]
        items = {'tag': SEPARATOR.join(labelitems), 'id': SEPARATOR.join(valueitems)}
        return items

    def options(self):
        tags = Tag.query.filter_by(interest=localinterest()).all()
        tags.sort(key=lambda t: t.tag.lower())
        options = [{'label': t.tag, 'value': t.id} for t in tags]
        return options

    def col_options(self):
        col = {}
        col['type'] = 'select2'
        col['onFocus'] = 'focus'
        col['opts'] = {'minimumResultsForSearch': 0 if self.searchbox else 'Infinity',
                       'multiple': True}
        col['separator'] = SEPARATOR
        return col

class RolesPicker(DteDbOptionsPickerBase):
    def __init__(self):
        super().__init__(
            labelfield='role'
        )

    def get(self, dbrow_or_id):
        localuser = self.get_dbrow(dbrow_or_id)
        user = User.query.filter_by(id=localuser.user_id).one()
        roles = user.roles[:]
        roles.sort(key=lambda r: r.name)

        labelitems = [r.name for r in roles]
        valueitems = [str(r.id) for r in roles]
        items = {'role': SEPARATOR.join(labelitems), 'id': SEPARATOR.join(valueitems)}
        return items

    def options(self):
        interest = Interest.query.filter_by(interest=g.interest).one()
        roles = [r for r in Role.query.all() if g.loutility in r.applications]
        roles.sort(key=lambda r: r.name)
        options = [{'label': r.name, 'value': r.id} for r in roles]
        return options

    def col_options(self):
        col = {}
        col['type'] = 'select2'
        col['onFocus'] = 'focus'
        col['opts'] = {'minimumResultsForSearch': 0 if self.searchbox else 'Infinity',
                       'multiple': True}
        col['separator'] = SEPARATOR
        return col

class DistributionView(DbCrudApiInterestsRolePermissions):
    def beforequery(self):
        # we're only interested in users using the current interest for this view
        self.queryparams = localinterest_query_params()

    def open(self):
        '''
        return the users which have active positions for the indicated date
        '''
        ondate = request.args.get('ondate', date.today())
        allusers = self.model.query.filter_by(**self.queryparams).filter(*self.queryfilters).all()
        activeusers = [u for u in allusers if positions_active(u, ondate)]
        self.rows = iter(activeusers)

distribution_view = DistributionView(
                    roles_accepted = organization_roles,
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = LocalUser,
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': adminguide},
                    pagename = 'Distribution List',
                    endpoint = 'admin.distribution',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/distribution',
                    dbmapping = distribution_dbmapping,
                    formmapping = distribution_formmapping,
                    pretablehtml = distribution_pretablehtml,
                    yadcfoptions=distribution_yadcf_options,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'name', 'name': 'name', 'label': 'Member',
                         },
                        {'data': 'email', 'name': 'email', 'label': 'Email',
                         },
                        {'data': 'tags', 'name': 'tags', 'label': 'Position Tags',
                         '_treatment': {'relationship': { 'optionspicker': TagsPicker() } }
                         },
                        {'data': 'positions', 'name': 'positions', 'label': 'Positions',
                         '_treatment': {'relationship': { 'optionspicker': PositionsPicker() } }
                         },
                        {'data': 'roles', 'name': 'roles', 'label': 'Roles',
                         '_treatment': {'relationship': { 'optionspicker': RolesPicker() } }
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid',
                    buttons = lambda: ['csv'],
                    dtoptions = {
                        'order': [['name:name', 'asc']],
                        'scrollCollapse': True,
                        'scrollX': True,
                        'scrollXInner': "100%",
                        'scrollY': True,
                    },
                    )
distribution_view.register()
