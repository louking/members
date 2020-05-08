'''
leadership_tasks_admin - administrative task handling
===========================================
'''
# standard
from datetime import timedelta, date
from re import match

# pypi
from flask import g, url_for, current_app, request
from flask_security import current_user
from sqlalchemy import Enum
from dominate.tags import a
from slugify import slugify
from markdown import markdown

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, Task, TaskField, TaskGroup, TaskTaskField, TaskCompletion
from ...model import Position, InputFieldData, Files
from ...model import input_type_all, localinterest_query_params, localinterest_viafilter, gen_fieldname
from ...model import FIELDNAME_ARG, INPUT_TYPE_UPLOAD, INPUT_TYPE_DISPLAY
from ...model import date_unit_all, DATE_UNIT_WEEKS, DATE_UNIT_MONTHS, DATE_UNIT_YEARS
from .viewhelpers import lastcompleted, get_status, get_order, get_expires, localinterest
from .viewhelpers import get_position_taskgroups, get_taskgroup_taskgroups
from .viewhelpers import create_taskcompletion, get_task_completion, user2localuser, localuser2user
from .viewhelpers import get_member_tasks
from .viewhelpers import dtrender, dttimerender
from .viewhelpers import EXPIRES_SOON, PERIOD_WINDOW_DISPLAY, STATUS_DISPLAYORDER

# this is just to pick up list() function
from .leadership_tasks_member import fieldupload

from loutilities.user.model import User
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.tables import DteDbOptionsPickerBase, DteDbRelationship, get_request_action, get_request_data
from loutilities.tables import SEPARATOR, REGEX_ISODATE
from loutilities.filters import filtercontainerdiv, filterdiv, yadcfoption

class ParameterError(Exception): pass

debug = False

##########################################################################################
# tasks endpoint
###########################################################################################

class AssociationSelect(DteDbOptionsPickerBase):
    '''
    AssociationSelect builds on DteDbOptionsPickerBase, allowing use of
    https://docs.sqlalchemy.org/en/13/orm/basic_relationships.html#association-object to
    add an Enum type selector for the relationship

    Additional parameters

    :param associationmodel: model class which contains [association object](https://docs.sqlalchemy.org/en/13/orm/basic_relationships.html#association-object)
    :param associationfields: list of fields in associationmodel used to update the record, must be Enum or subrecord
    :param selectattrs: list of attributes used to build select grouping. list order must match associationfields
            items must be Enum attribute (Enum) (uses Enum values) or table attribute (uses table values)

    Use of associationattr:

        # TODO: we'd like the select tree to look like this, but currently Editor does not support select2 with optgroup tag
        # select tree looks like
        #
        #     associationattr 1
        #         fieldmodel.id 1
        #         fieldmodel.id 2
        #             :
        #     associationattr 2
        #         fieldmodel.id 1
        #         fieldmodel.id 2
        #             :

        # associate task / taskfield tables adding association attribute "need"
        class TaskTaskField(Base):
            __tablename__ = 'task_taskfield'
            task_id             = Column(Integer, ForeignKey('task.id'), primary_key=True)
            taskfield_id        = Column(Integer, ForeignKey('taskfield.id'), primary_key=True)
            need                = Column(Enum('required', 'oneof', 'optional'))
            task                = relationship('Task', backref='fields')
            taskfield           = relationship('TaskField', backref='tasks')

        class Task(Base):
            __tablename__ = 'task'
            id                  = Column(Integer(), primary_key=True)
            interest_id         = Column(Integer, ForeignKey('localinterest.id'))
            interest            = relationship('LocalInterest', backref=backref('tasks'))
            task                = Column(String(TASK_LEN))

        class TaskField(Base):
            __tablename__ = 'taskfield'
            id                  = Column(Integer(), primary_key=True)
            interest_id         = Column(Integer, ForeignKey('localinterest.id'))
            interest            = relationship('LocalInterest', backref=backref('taskfields'))
            taskfield           = Column(String(TASKFIELD_LEN))
            fieldname           = Column(String(TASKFIELDNAME_LEN))

        taskfields = AssociationSelect(tablemodel=Task, fieldmodel=User, labelfield='name', formfield='users', dbfield='users', associationattr=TaskTaskField.need )
                        OR
        in configuration for DbCrudApiInterestsRolePermissions
            {'data': 'fields', 'name': 'fields', 'label': 'Fields',
             '_treatment': {
                 'relationship': {
                     'optionspicker':
                         AssociationSelect(
                             tablemodel=Task,
                             associationmodel=TaskTaskField,
                             associationtablemodelfield='task',
                             associationfields=['need', 'taskfield'],
                             selectattrs=[TaskTaskField.need, TaskField.taskfield],
                             labelfield='fields',
                             formfield='fields',
                             dbfield='fields', uselist=True,
                             queryparams=localinterest_query_params,
                         )
                 }}
             },


    '''
    def __init__(self, **kwargs):
        # the args dict has default values for arguments added by this class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(
            associationmodel=None,
            associationtablemodelfield=None,
            associationfields=[],
            selectattrs=[],
        )
        args.update(kwargs)

        # associationmodel = TaskTaskField,
        # associationfields = ['need', 'taskfield'],
        # selectattrs = [TaskTaskField.need, TaskField.taskfield],

        # this initialization needs to be done before checking any self.xxx attributes
        super().__init__(**args)

        # some of the args are required
        reqdfields = ['associationmodel', 'associationtablemodelfield', 'associationfields', 'selectattrs', 'dbfield']
        for field in reqdfields:
            if not getattr(self, field, None):
                raise ParameterError('{} parameters are all required'.format(', '.join(reqdfields)))
        if len(self.associationfields) != len(self.selectattrs):
            raise ParameterError('length of associationfields and selectattrs must be the same')

        # pick up options for the tree levels
        self.optionlevels = []
        for associationfield, selectattr in zip(self.associationfields, self.selectattrs):
            thislevel = {'associationfield':associationfield, 'selectattr': selectattr}
            if type(selectattr.type) == Enum:
                thislevel['options'] = selectattr.type.enums
                thislevel['ids'] = range(len(selectattr.type.enums))
            else:
                thislevel['model'] = selectattr.class_
                thislevel['key'] = selectattr.key

            self.optionlevels.append(thislevel)

    # def _setid(self, tablemodelitem, id):
    #     theassociation = self.associationmodel(**{self.associationtablemodelfield:tablemodelitem})
    def _setid(self, id):
        if not id: return None

        theassociation = self.associationmodel()
        db.session.add(theassociation)

        idparts = id.split('.')
        for optionlevel,idpart in zip(self.optionlevels,idparts):
            # have to look up the target if this level is a model
            if 'model' in optionlevel:
                thetarget = optionlevel['model'].query.filter_by(id=idpart).one()
            else:
                thetarget = optionlevel['options'][int(idpart)]
            setattr(theassociation, optionlevel['associationfield'], thetarget)
        return theassociation

    def set(self, formrow):
        if self.uselist:
            # accumulate list of database model instances
            items = []

            # return empty list if no items, rather than list with empty item
            # this allows for multiple keys in formrow[self.formfield], but seems like there'd only be one
            itemvalues = []
            for key in formrow[self.formfield]:
                vallist = formrow[self.formfield][key].split(SEPARATOR)
                # empty list is actually null list with one entry
                if len(vallist) == 1 and not vallist[0]: continue
                # loop through nonempty entries -- will we ever see null entry? hope not else exception on .one() call below
                for ndx in range(len(vallist)):
                    if len(itemvalues) < ndx + 1:
                        itemvalues.append(vallist[ndx])
                    else:
                        itemvalues[ndx].update(vallist[ndx])
            if debug: current_app.logger.debug('itemvalues={}'.format(itemvalues))
            for itemvalue in itemvalues:
                thisitem = self._setid(itemvalue)
                items.append(thisitem)
            return items
        else:
            itemvalue = formrow[self.formfield] if formrow[self.formfield] else None
            thisitem = self._setid(itemvalue)
            return thisitem

    def _getlabelvalue(self, theitem):
        thislabel = ''
        thisvalue = ''
        for optionlevel in self.optionlevels:
            # startup case, don't append separators
            if thislabel != '':
                thislabel += '/'
                thisvalue += '.'

            # check if retrieving from the database, otherwise use existing options
            if 'model' in optionlevel:
                # targetid = getattr(theitem, optionlevel['associationfield'])
                # thetarget = optionlevel['model'].query.filter_by(id=targetid).one()
                thetarget = getattr(theitem, optionlevel['associationfield'])
                thislabel += getattr(thetarget, optionlevel['key'])
                thisvalue += str(getattr(thetarget, 'id'))
            else:
                theoptions = optionlevel['options']
                thislabel += getattr(theitem, optionlevel['associationfield'])
                thisvalue += str(theoptions.index(thislabel))

        return thislabel, thisvalue

    def get(self, dbrow_or_id):
        if type(dbrow_or_id) in [int, str]:
            dbrow = self.tablemodel.query().filter_by(id=dbrow_or_id).one()

        else:
            dbrow = dbrow_or_id

        # get from database to form
        if self.uselist:
            items = {}
            labelitems = []
            valueitems = []
            for item in getattr(dbrow, self.dbfield):
                thislabel,thisvalue = self._getlabelvalue(item)

                labelitems.append(thislabel)
                valueitems.append(thisvalue)

            items = {self.labelfield: SEPARATOR.join(labelitems), self.valuefield: SEPARATOR.join(valueitems)}
            return items
        else:
            # get the attribute if specified
            theitem = getattr(dbrow, self.dbfield)
            if theitem:
                thislabel, thisvalue = self._getlabelvalue(theitem)
                item = {self.labelfield: thislabel, self.valuefield: thisvalue}
                return item

            # otherwise return None
            else:
                return {self.labelfield: None, self.valuefield: None}

    def options(self):
        '''
        return sorted list of items in the model, may be overridden for more complex models

        :return: options as expected by optionpicker type,
            e.g., for select2 list of {'label': label, 'value': value} (see https://select2.org/options)
        '''
        queryparams = self.queryparams() if callable(self.queryparams) else self.queryparams
        items = [{'label':'', 'value':''}]

        for optionlevel in self.optionlevels:
            # overwrite options if retrieving from the database, otherwise use existing options
            if 'model' in optionlevel:
                optionsids = [(getattr(r,optionlevel['key']),getattr(r,'id'))
                              for r in optionlevel['model'].query
                                  .filter_by(**queryparams)
                                  .order_by(optionlevel['selectattr'])
                                  .all()]
                optionlevel['options'] = [oi[0] for oi in optionsids]
                optionlevel['ids'] = [oi[1] for oi in optionsids]

            # distribute these options across existing items
            theseitems = []
            for item in items:
                thislabel = item['label']
                thisvalue = item['value']
                # startup case, don't append separators
                if thislabel != '':
                    thislabel += '/'
                    thisvalue += '.'
                for option,id_ in zip(optionlevel['options'],optionlevel['ids']):
                    theseitems.append({'label':thislabel+option, 'value':thisvalue+str(id_)})
            items = theseitems

        if self.nullable:
            items =[{'label': '<none>', 'value': None}] + items

        return items

    def new_plus_options(self):
        '''
        return sorted list of items in the model, with first option being <new>

        :return:
        '''
        items = [{'label': '<new>', 'value': 0}] + self.options()
        return items

    def col_options(self):
        '''
        return additional column options required by the caller

        :return:
        '''
        col = {}
        col['type'] = 'select2'
        col['onFocus'] = 'focus'
        col['opts'] = {'minimumResultsForSearch': 0 if self.searchbox else 'Infinity',
                       'multiple': self.uselist,
                       'placeholder': None if self.uselist else '(select)'}
        if self.uselist:
            col['separator'] = SEPARATOR
        return col

class AssociationCrudApi(DbCrudApiInterestsRolePermissions):
    '''
    AssociationCrudApi MUST be used with AssociationSelect. This allows DbCrudApi... to update
    the association with the self.model instance, which isn't visible to AssociationSelect

    Additional parameters

    :param assnmodelfield: field in Association definition which points to the self.model dbrow being edited
    :param assnlistfield: field in self.model which has association record list or association record
    '''
    def __init__(self, **kwargs):

        # the args dict has default values for arguments added by this derived class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(
            assnlistfield=None,
            assnmodelfield=None,
        )
        args.update(kwargs)

        # this initialization needs to be done before checking any self.xxx attributes
        super().__init__(**args)

        # Caller should use roles_accepted OR roles_required but not both
        reqdfields = ['assnlistfield', 'assnmodelfield']
        for field in reqdfields:
            if not getattr(self, field, None):
                raise ParameterError('{} are all required'.format(reqdfields))

    def updaterow(self, thisid, formdata):
        '''
        update assnlistfield in self.model, and assnmodelfield in AssociationSelect.associationmodel
        '''
        dbrow = self.model.query.filter_by(id=thisid).one()

        # get handy access to the association list field
        assnfield = getattr(dbrow, self.assnlistfield)

        # first delete all the items in assnlistfield
        for i in range(len(assnfield)):
            assnrow = assnfield.pop(0)
            db.session.delete(assnrow)

        # this adds the current fields list
        notused = super().updaterow(thisid, formdata)

        # now need to add this task to the tasktaskfield associations
        for assnrow in assnfield:
            setattr(assnrow, self.assnmodelfield, dbrow)

        return self.dte.get_response_data(dbrow)

    def editor_method_posthook(self, form):
        '''
        do validation after editor method because we want all processing to have taken place before
        we try to read thistask.fields
        '''
        action = get_request_action(form)

        # we only have to worry about create and edit functions
        if action == 'create':
            thisid = self.created_id
        elif action in ['edit', 'editRefresh']:
            # kludge to get task.id
            # NOTE: this is only called from 'edit' / put function, and there will be only one id
            thisid = list(get_request_data(form).keys())[0]
        else:
            return

        thistask = Task.query.filter_by(id=thisid).one()

        # build sets of duplicated fields
        duplicated = set()
        found = set()

        for tasktaskfield in thistask.fields:
            taskfield = tasktaskfield.taskfield
            if taskfield.fieldname in found:
                duplicated.add(taskfield.fieldname)
            found.add(taskfield.fieldname)

        # indicate error for any fields which were duplicated
        if duplicated:
            dupnames = [TaskField.query.filter_by(fieldname=fn).one().taskfield for fn in list(duplicated)]
            self._fielderrors = [{'name': 'fields.id', 'get_status': '{} fields were found in more than one category'.format(dupnames)}]
            raise ParameterError

def task_validate(action, formdata):
    results = []

    # TODO: remove this when #51 fixed
    from re import compile
    # datepattern = '^(19|20)\d\d[-](0[1-9]|1[012])[-](0[1-9]|[12][0-9]|3[01])$'
    datepattern = compile('^(0[1-9]|1[012])[-](0[1-9]|[12][0-9]|3[01])$')
    if formdata['dateofyear'] and not datepattern.match(formdata['dateofyear']):
        results.append({'name': 'dateofyear', 'status': 'must be formatted as MM-DD'})

    # if both of these are set, they will conflict with each other
    if formdata['period'] and formdata['dateofyear']:
        results.append({'name': 'period', 'status': 'only one of these should be supplied'})
        results.append({'name': 'dateofyear', 'status': 'only one of these should be supplied'})

    # expirysoon is needed for nonoptional tasks which have a period or dateofyear
    if formdata['isoptional'] != 'yes' and (formdata['period'] or formdata['dateofyear']):
        if not formdata['expirysoon']:
            results.append({'name': 'expirysoon', 'status': 'please supply'})

    return results

task_dbattrs = 'id,interest_id,task,description,priority,expirysoon,expirysoon_units,period,period_units,dateofyear,expirystarts,expirystarts_units,isoptional,taskgroups,fields'.split(',')
task_formfields = 'rowid,interest_id,task,description,priority,expirysoon,expirysoon_units,period,period_units,dateofyear,expirystarts,expirystarts_units,isoptional,taskgroups,fields'.split(',')
task_dbmapping = dict(zip(task_dbattrs, task_formfields))
task_formmapping = dict(zip(task_formfields, task_dbattrs))
# only take mm-dd portion of date into database
# TODO: uncommend these when #51 fixed
# task_dbmapping['dateofyear'] = lambda formrow: formrow['dateofyear'][-5:] if formrow['dateofyear'] else None
# task_formmapping['dateofyear'] = lambda dbrow: '{}-{}'.format(date.today().year, dbrow.dateofyear) if dbrow.dateofyear else None

task = AssociationCrudApi(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Task,
                    assnmodelfield='task',
                    assnlistfield='fields',
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'tasks.view.jinja2',
                    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/leadership-task-admin-guide.html'},
                    pagename = 'Tasks',
                    endpoint = 'admin.tasks',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/tasks',
                    dbmapping = task_dbmapping, 
                    formmapping = task_formmapping, 
                    checkrequired = True,
                    validate = task_validate,
                    clientcolumns = [
                        {'data': 'task', 'name': 'task', 'label': 'Task',
                         'className': 'field_req',
                         },
                        {'data': 'priority', 'name': 'priority', 'label': 'Priority',
                         'className': 'field_req',
                         'class': 'TextCenter',
                         },
                        {'data': 'description', 'name': 'description', 'label': 'Display', 'type': 'textarea',
                         'className': 'field_req',
                         'render': {'eval': '$.fn.dataTable.render.ellipsis( 80 )'},
                         'fieldInfo': '<a href=https://daringfireball.net/projects/markdown/syntax target=_blank>Markdown</a>' +
                                      ' can be used. Click link for syntax'
                         },
                        {'data': 'taskgroups', 'name': 'taskgroups', 'label': 'Task Groups',
                         'fieldInfo': 'task groups this task should be associated with',
                         '_treatment': {
                             'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup',
                                              'formfield': 'taskgroups',
                                              'dbfield': 'taskgroups', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'expirysoon', 'name': 'expirysoon', 'label': 'Expires Soon',
                         'class': 'TextCenter',
                         'fieldInfo': 'time before task expires to start indicating "expires soon"',
                         'ed': {'def': EXPIRES_SOON / PERIOD_WINDOW_DISPLAY}
                         },
                        {'data': 'expirysoon_units', 'name': 'expirysoon_units', 'label': '',
                         'type': 'select2',
                         'className': 'inhibitlabel',
                         'options': date_unit_all,
                         'ed' :{
                             'def': DATE_UNIT_WEEKS
                         },
                         },
                        {'data': 'fields', 'name': 'fields', 'label': 'Fields',
                         '_treatment': {
                             'relationship': {
                                 'optionspicker':
                                     AssociationSelect(
                                         tablemodel=Task,
                                         associationtablemodelfield='task',
                                         associationmodel=TaskTaskField,
                                         associationfields=['need', 'taskfield'],
                                         selectattrs=[TaskTaskField.need, TaskField.taskfield],
                                         labelfield='fields',
                                         formfield='fields',
                                         dbfield='fields', uselist=True,
                                         queryparams=localinterest_query_params,
                                     )
                             }}
                         },
                        {'data': 'period', 'name': 'period', 'label': 'Period',
                         'fieldInfo': 'Period or Date of Year may be specified. Leave blank if this task doesn\'t need to be done periodically',
                         'class': 'TextCenter',
                         },
                        {'data': 'period_units', 'name': 'period_units', 'label': '',
                         'type': 'select2',
                         'className': 'inhibitlabel',
                         'options': date_unit_all,
                         'ed' :{
                             'def': DATE_UNIT_YEARS
                         },
                         },
                        {'data': 'dateofyear', 'name': 'dateofyear', 'label': 'Date of Year',
                         # TODO: uncomment these when #51 fixed
                         # 'type': 'datetime',
                         # 'render': {'eval': 'render_month_date'},
                         # 'ed': {'displayFormat': 'MM-DD', 'wireFormat':'YYYY-MM-DD', 'def': None},
                         'fieldInfo': 'Period or Date of Year may be specified. Leave blank if this task doesn\'t need to be done by a particular date',
                         # TODO: remove this when #51 fixed
                         'ed': {'label': 'Date of Year (mm-dd)'},
                         },
                        {'data': 'expirystarts', 'name': 'expirystarts', 'label': 'Overdue Starts',
                         'fieldInfo': 'only used if Date of Year specified. time after task expires to start indicating "overdue"',
                         'class': 'TextCenter',
                         },
                        {'data': 'expirystarts_units', 'name': 'expirystarts_units', 'label': '',
                         'type': 'select2',
                         'className': 'inhibitlabel',
                         'options': date_unit_all,
                         'ed' :{
                             'def': DATE_UNIT_MONTHS
                         },
                         },
                        {'data': 'isoptional', 'name': 'isoptional', 'label': 'Optional Task',
                         'class': 'TextCenter',
                         '_treatment': {'boolean': {'formfield': 'isoptional', 'dbfield': 'isoptional'}},
                         'ed': {'def': 'no'},
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons = ['create', 'editRefresh', 'remove', 'csv'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    edoptions = {
                        'template': '#customForm',
                    }
                    )
task.register()

##########################################################################################
# taskfields endpoint
###########################################################################################

taskfield_dbattrs = 'id,interest_id,taskfield,fieldname,displaylabel,displayvalue,fieldinfo,fieldoptions,inputtype,priority,uploadurl,override_completion'.split(',')
taskfield_formfields = 'rowid,interest_id,taskfield,fieldname,displaylabel,displayvalue,fieldinfo,fieldoptions,inputtype,priority,uploadurl,override_completion'.split(',')
taskfield_dbmapping = dict(zip(taskfield_dbattrs, taskfield_formfields))
taskfield_formmapping = dict(zip(taskfield_formfields, taskfield_dbattrs))

from ...model import INPUT_TYPE_CHECKBOX, INPUT_TYPE_RADIO, INPUT_TYPE_SELECT2
INPUT_TYPE_HASOPTIONS = [INPUT_TYPE_CHECKBOX, INPUT_TYPE_RADIO, INPUT_TYPE_SELECT2]

def get_options(dbrow):
    if not dbrow.fieldoptions:
        return []
    else:
        return dbrow.fieldoptions.split(SEPARATOR)

taskfield_formmapping['fieldoptions'] = get_options

class TaskFieldCrud(DbCrudApiInterestsRolePermissions):
    def createrow(self, formdata):
        taskfieldrow = super().createrow(formdata)
        taskfield = TaskField.query.filter_by(id=self.created_id).one()
        taskfield.fieldname = gen_fieldname()
        if taskfield.inputtype == INPUT_TYPE_UPLOAD:
            taskfield.uploadurl = (url_for('admin.fieldupload', interest=g.interest)
                                          + '?{}={}'.format(FIELDNAME_ARG, taskfield.fieldname))
        return self.dte.get_response_data(taskfield)

taskfield = TaskFieldCrud(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = TaskField,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/leadership-task-admin-guide.html'},
                    pagename = 'Task Fields',
                    endpoint = 'admin.taskfields',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/taskfields',
                    dbmapping = taskfield_dbmapping, 
                    formmapping = taskfield_formmapping, 
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'taskfield', 'name': 'taskfield', 'label': 'Field',
                         'className': 'field_req',
                         '_unique': True,
                         },
                        {'data': 'priority', 'name': 'priority', 'label': 'Priority',
                         'className': 'field_req',
                         },
                        {'data': 'displaylabel', 'name': 'displaylabel', 'label': 'Field Label',
                         'className': 'field_req',
                         },
                        {'data': 'inputtype', 'name': 'inputtype', 'label': 'Input Type',
                         'fieldInfo' : 'if you want the field to collect input, select the input type',
                         'type': 'select2',
                         'options': sorted(input_type_all),
                         'ed' :{
                             'opts' : {
                                 'placeholder' : 'Select input type',
                                 'allowClear' : True
                             }
                         },
                         },
                        {'data': 'fieldoptions', 'name': 'fieldoptions', 'label': 'Options',
                         'type': 'select2', 'separator':SEPARATOR,
                         'options': [],
                         'opts': {
                             'multiple': 'multiple',
                             'tags': True
                         }
                         },
                        {'data': 'fieldinfo', 'name': 'fieldinfo', 'label': 'Field Hint',
                         'fieldInfo': 'this gets displayed under the field to help the user fill in the form'
                         },
                        {'data': 'displayvalue', 'name': 'displayvalue', 'label': 'Field Value', 'type': 'textarea',
                         'render': {'eval': '$.fn.dataTable.render.ellipsis( 80 )'},
                         'fieldInfo': 'text to display for {} Input Type (display-only)'.format(INPUT_TYPE_DISPLAY)},
                        {'data': 'fieldname', 'name': 'fieldname', 'label': 'Field Name', 'type': 'readonly'
                         },
                        {'data': 'uploadurl', 'name': 'uploadurl', 'label': 'Upload URL', 'type': 'readonly'
                         },
                        {'data': 'override_completion', 'name': 'override_completion', 'label': 'Override Completion',
                         '_treatment': {'boolean': {'formfield': 'override_completion', 'dbfield': 'override_completion'}},
                         'fieldInfo': 'if \'yes\' this field overrides date when member marks task completed',
                         'ed': {'def': 'no'},
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons = ['create', 'editRefresh', 'remove', 'csv'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
taskfield.register()

##########################################################################################
# positions endpoint
###########################################################################################

position_dbattrs = 'id,interest_id,position,description,taskgroups,users,emailgroups'.split(',')
position_formfields = 'rowid,interest_id,position,description,taskgroups,users,emailgroups'.split(',')
position_dbmapping = dict(zip(position_dbattrs, position_formfields))
position_formmapping = dict(zip(position_formfields, position_dbattrs))

position = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Position,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/leadership-task-admin-guide.html'},
                    pagename = 'Positions',
                    endpoint = 'admin.positions',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/positions',
                    dbmapping = position_dbmapping, 
                    formmapping = position_formmapping,
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
                         'fieldInfo': 'members who hold this position',
                         '_treatment': {
                             # viadbattr stores the LocalUser id which has user_id=user.id for each of these
                             # and pulls the correct users out of User based on LocalUser table
                             'relationship': {'fieldmodel': User, 'labelfield': 'name',
                                              'formfield': 'users', 'dbfield': 'users',
                                              'viadbattr': LocalUser.user_id,
                                              'viafilter': localinterest_viafilter,
                                              'queryparams': {'active': True},
                                              'uselist': True}}
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
                    buttons = ['create', 'editRefresh', 'remove', 'csv'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
position.register()

##########################################################################################
# taskgroups endpoint
###########################################################################################

def _validate_branch(taskgroup, branchlist):
    '''
    recursively check if this taskgroup in branchlist -- if it is, there's an error

    :param taskgroup: task group to check
    :param branchlist: list of task groups so far in this branch
    :return: results error list
    '''
    results = []
    if taskgroup.id in branchlist:
        branchnames = ', '.join(["'{}'".format(TaskGroup.query.filter_by(id=id).one().taskgroup) for id in branchlist])
        results = [{'name': 'tgtaskgroups.id', 'status': 'task group loop found: \'{}\' repeated following {}'.format(taskgroup.taskgroup, branchnames)}]

    else:
        thisbranch = branchlist + [taskgroup.id]
        for tg in taskgroup.taskgroups:
            results = _validate_branch(tg, thisbranch)
            if results: break

    return results

def _validate_taskgroup(action, formdata):
    results = []

    # NOTE: only using from 'create', 'edit' functions, so assuming there will be only one id
    if action == 'create':
        initialbranch = []
    elif action == 'edit':
        # kludge to get referenced taskgroup.id
        thisid = int(list(get_request_data(request.form).keys())[0])
        initialbranch = [thisid]
    else:
        return results

    # recursively look through all task groups this task group refers to
    # if the any task group is referenced more than once on a branch then we have a loop
    # stop at first problem
    for tgid in formdata['tgtaskgroups']['id'].split(SEPARATOR):
        # if empty string, no ids were supplied
        if tgid == '': break
        taskgroup = TaskGroup.query.filter_by(id=tgid).one()
        results = _validate_branch(taskgroup, initialbranch)
        if results: break

    return results

taskgroup_dbattrs = 'id,interest_id,taskgroup,description,tasks,positions,users,taskgroups'.split(',')
taskgroup_formfields = 'rowid,interest_id,taskgroup,description,tasks,positions,users,tgtaskgroups'.split(',')
taskgroup_dbmapping = dict(zip(taskgroup_dbattrs, taskgroup_formfields))
taskgroup_formmapping = dict(zip(taskgroup_formfields, taskgroup_dbattrs))

taskgroup = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = TaskGroup,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/leadership-task-admin-guide.html'},
                    pagename = 'Task Groups',
                    endpoint = 'admin.taskgroups',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/taskgroups',
                    dbmapping = taskgroup_dbmapping, 
                    formmapping = taskgroup_formmapping,
                    checkrequired = True,
                    validate = _validate_taskgroup,
                    clientcolumns = [
                        {'data': 'taskgroup', 'name': 'taskgroup', 'label': 'Task Group',
                         'className': 'field_req',
                         # TODO: is this unique in the table or within an interest? Needs to be within an interest
                         '_unique': True,
                         },
                        {'data': 'description', 'name': 'description', 'label': 'Description',
                         'className': 'field_req',
                         },
                        # note name tgtaskgroups rather than taskgroups to avoid conflict with name in tasks subform
                        # see also #55
                        {'data': 'tgtaskgroups', 'name': 'tgtaskgroups', 'label': 'Task Groups',
                         '_treatment': {
                             'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup', 'formfield': 'tgtaskgroups',
                                              'dbfield': 'taskgroups', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'tasks', 'name': 'tasks', 'label': 'Tasks',
                         '_treatment': {
                             'relationship': {'fieldmodel': Task, 'labelfield': 'task', 'formfield': 'tasks',
                                              'dbfield': 'tasks', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              'editable' : { 'api' : task },
                                              }}
                         },
                        {'data': 'positions', 'name': 'positions', 'label': 'Positions',
                         '_treatment': {
                             'relationship': {'fieldmodel': Position, 'labelfield': 'position', 'formfield': 'positions',
                                              'dbfield': 'positions', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'users', 'name': 'users', 'label': 'Members',
                         '_treatment': {
                             # viadbattr stores the LocalUser id which has user_id=user.id for each of these
                             # and pulls the correct users out of User based on LocalUser table
                             'relationship': {'fieldmodel': User, 'labelfield': 'name',
                                              'formfield': 'users', 'dbfield': 'users',
                                              'viadbattr': LocalUser.user_id,
                                              'viafilter': localinterest_viafilter,
                                              'queryparams': {'active': True},
                                              'uselist': True}}
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons = ['create', 'editRefresh', 'remove', 'csv'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
taskgroup.register()

##########################################################################################
# assigntasks endpoint
###########################################################################################

def set_bound_user(formrow):
    user = User.query.filter_by(name=formrow['user_id']).one()
    return user.id

def get_bound_user(dbrow):
    user = User.query.filter_by(id=dbrow.user_id).one()
    return user.name
    
assigntask_dbattrs = 'id,user_id,positions,taskgroups'.split(',')
assigntask_formfields = 'rowid,user_id,positions,taskgroups'.split(',')
assigntask_dbmapping = dict(zip(assigntask_dbattrs, assigntask_formfields))
assigntask_formmapping = dict(zip(assigntask_formfields, assigntask_dbattrs))
assigntask_dbmapping['user_id'] = set_bound_user
assigntask_formmapping['user_id'] = get_bound_user

assigntask = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = LocalUser,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    queryparams = {'active': True},
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/leadership-task-admin-guide.html'},
                    pagename = 'Assign Tasks',
                    endpoint = 'admin.assigntasks',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/assigntasks',
                    dbmapping = assigntask_dbmapping, 
                    formmapping = assigntask_formmapping,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'user_id', 'name': 'user_id', 'label': 'Member',
                         'className': 'field_req',
                         '_unique': True,
                         },
                        {'data': 'positions', 'name': 'positions', 'label': 'Positions',
                         'fieldInfo': 'tasks are assigned via position, task groups, or both',
                         '_treatment': {
                             'relationship': {'fieldmodel': Position, 'labelfield': 'position', 'formfield': 'positions',
                                              'dbfield': 'positions', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'taskgroups', 'name': 'taskgroups', 'label': 'Task Groups',
                         'fieldInfo': 'tasks are assigned via position, task groups, or both',
                         '_treatment': {
                             'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup',
                                              'formfield': 'taskgroups',
                                              'dbfield': 'taskgroups', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons = ['editRefresh', 'csv'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
assigntask.register()

##########################################################################################
# taskdetails endpoint
###########################################################################################

def addlfields(task, member):
    taskfields = []
    tc = get_task_completion(task, member)
    for ttf in task.fields:
        f = ttf.taskfield
        thistaskfield = {}
        for key in 'taskfield,fieldname,displayvalue,displaylabel,inputtype,fieldinfo,priority,uploadurl'.split(','):
            thistaskfield[key] = getattr(f, key)
            # displayvalue gets markdown translation
            if key == 'displayvalue' and getattr(f, key):
                thistaskfield[key] = markdown(getattr(f, key), extensions=['md_in_html', 'attr_list'])
        thistaskfield['fieldoptions'] = get_options(f)
        if tc:
            # field may exist now but maybe didn't before
            field = InputFieldData.query.filter_by(field=f, taskcompletion=tc).one_or_none()

            # field was found
            if field:
                value = field.value
                if f.inputtype != INPUT_TYPE_UPLOAD:
                    thistaskfield['value'] = value
                else:
                    file = Files.query.filter_by(fileid=value).one()
                    thistaskfield['value'] = a(file.filename,
                                               href=url_for('admin.file',
                                                            interest=g.interest,
                                                            fileid=value),
                                               target='_blank').render()
                    thistaskfield['fileid'] = value

            # field wasn't found
            else:
                thistaskfield['value'] = None
        else:
            thistaskfield['value'] = None
        taskfields.append(thistaskfield)

    return taskfields

# map id to rowid, retrieve all other required fields
# no dbmapping because this table is read-only
taskdetails_dbattrs = 'id,member,task,lastcompleted,status,order,expires,fields,task_taskgroups,member_taskgroups,member_positions'.split(',')
taskdetails_formfields = 'rowid,member,task,lastcompleted,status,order,expires,fields,task_taskgroups,member_taskgroups,member_positions'.split(',')
taskdetails_dbmapping = dict(zip(taskdetails_dbattrs, taskdetails_formfields))

taskdetails_formmapping = {}
taskdetails_formmapping['rowid'] = 'id'
taskdetails_formmapping['task_taskgroups'] = 'task_taskgroups'
taskdetails_formmapping['member_taskgroups'] = 'member_taskgroups'
taskdetails_formmapping['member_positions'] = 'member_positions'
taskdetails_formmapping['member'] = lambda tu: tu.member.name
taskdetails_formmapping['task'] = lambda tu: tu.task.task
taskdetails_formmapping['lastcompleted'] = lambda tu: lastcompleted(tu.task, tu.member)
taskdetails_formmapping['status'] = lambda tu: get_status(tu.task, tu.member)
taskdetails_formmapping['order'] = lambda tu: get_order(tu.task, tu.member)
taskdetails_formmapping['expires'] = lambda tu: get_expires(tu.task, tu.member)
taskdetails_formmapping['fields'] = lambda tu: 'yes' if tu.task.fields else ''
taskdetails_formmapping['addlfields'] = lambda tu: addlfields(tu.task, tu.member)

class TaskMember():
    '''
    allows creation of "taskuser" object to simulate database behavior
    '''
    def __init__(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])

class TaskDetails(DbCrudApiInterestsRolePermissions):

    def getids(self, id):
        '''
        return split of id into local user id, task id
        :param id: id for each TaskMember entry
        :return: (localuserid, taskid)
        '''
        return tuple([int(usertask) for usertask in id.split(';')])

    def setid(self, userid, taskid):
        '''
        return combined userid, taskid
        :param userid: id for each LocalUser entry
        :param taskid: id for each Task entry
        :return: id
        '''
        return ';'.join([str(userid), str(taskid)])

    def open(self):
        locinterest = localinterest()
        localusersdb = LocalUser.query.filter_by(interest=locinterest).all()

        # collect all the members
        localusers = set()
        for localuser in localusersdb:
            localusers |= {localuser}

        # retrieve member data from localusers
        members = []
        for localuser in iter(localusers):
            members.append({'localuser':localuser, 'member': User.query.filter_by(id=localuser.user_id).one()})

        tasksmembers = []
        for member in members:
            # collect all the tasks which are referenced by positions and taskgroups for this member
            tasks = get_member_tasks(member['localuser'])

            # create/add taskmember to list for all tasks
            for task in iter(tasks):
                membertaskid = self.setid(member['localuser'].id, task.id)
                taskmember = TaskMember(
                    id=membertaskid,
                    task=task, task_taskgroups=task.taskgroups,
                    member = member['member'],
                    member_positions = member['localuser'].positions,
                )

                # drill down to get all the taskgroups
                member_taskgroups = set()
                for position in member['localuser'].positions:
                    get_position_taskgroups(position, member_taskgroups)
                for taskgroup in member['localuser'].taskgroups:
                    get_taskgroup_taskgroups(taskgroup, member_taskgroups)
                taskmember.member_taskgroups = member_taskgroups

                tasksmembers.append(taskmember)

        self.rows = iter(tasksmembers)

    def updaterow(self, thisid, formdata):
        '''
        just update TaskCompletion.completion

        :param thisid:
        :param formdata:
        :return:
        '''
        memberid, taskid = self.getids(thisid)
        luser = LocalUser.query.filter_by(id=memberid).one()
        task = Task.query.filter_by(id=taskid).one()

        # create new TaskCompletion record, update the task completion time and user who made the update
        tc = create_taskcompletion(task, luser, self.localinterest, formdata)
        tc.completion = dtrender.asc2dt(formdata['lastcompleted'])
        tc.updated_by = user2localuser(current_user).id

        member = {'localuser': luser, 'member': User.query.filter_by(id=luser.user_id).one()}

        taskmember = TaskMember(
            id=thisid,
            task=task, task_taskgroups=task.taskgroups,
            member=member['member'],
            member_positions = member['localuser'].positions,
        )

        # drill down to get all the taskgroups
        member_taskgroups = set()
        for position in member['localuser'].positions:
            get_position_taskgroups(position, member_taskgroups)
        for taskgroup in member['localuser'].taskgroups:
            get_taskgroup_taskgroups(taskgroup, member_taskgroups)
        taskmember.member_taskgroups = member_taskgroups

        return self.dte.get_response_data(taskmember)

    def refreshrows(self, ids):
        '''
        refresh row(s) from database

        :param ids: comma separated ids of row to be refreshed
        :rtype: list of returned rows for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        theseids = ids.split(',')
        responsedata = []
        for thisid in theseids:
            # id is made up of localuser.id, task.id
            localuserid, taskid = self.getids(thisid)
            localuser = LocalUser.query.filter_by(id=localuserid).one()
            task = Task.query.filter_by(id=taskid).one()

            member = {'localuser': localuser, 'member': User.query.filter_by(id=localuser.user_id).one()}

            taskuser = TaskMember(
                id=thisid,
                task=task, task_taskgroups=task.taskgroups,
                member=member['member'],
                member_positions=member['localuser'].positions,
                member_taskgroups=member['localuser'].taskgroups,
            )

            responsedata.append(self.dte.get_response_data(taskuser))

        return responsedata

class ReadOnlySelect2(DteDbRelationship):
    def col_options(self):
        col = super().col_options()
        # readonly select2
        col['opts']['disabled'] = True
        return col

def taskdetails_validate(action, formdata):
    results = []

    # kludge to get task.id
    # NOTE: this is only called from 'edit' / put function, and there will be only one id
    thisid = list(get_request_data(request.form).keys())[0]

    # id is made up of localuser.id, task.id
    localuserid, taskid = taskdetails.getids(thisid)
    task = Task.query.filter_by(id=taskid).one()

    # build list of fields which could override completion date (should only be one)
    override_completion = []
    for tasktaskfield in task.fields:
        taskfield = tasktaskfield.taskfield
        if taskfield.override_completion:
            override_completion.append(taskfield.fieldname)

    for field in override_completion:
        if formdata[field] > date.today().isoformat():
            results.append({'name':field, 'status': 'cannot specify date later than today'})

    if not match(REGEX_ISODATE, formdata['lastcompleted']):
        results.append({'name':'lastcompleted', 'status': 'please specify date in yyyy-mm-dd format'})

    elif formdata['lastcompleted'] > date.today().isoformat():
        results.append({'name':'lastcompleted', 'status': 'cannot specify date later than today'})

    return results

taskdetails_filters = filtercontainerdiv()
taskdetails_filters += filterdiv('members-external-filter-members', 'Member')
taskdetails_filters += filterdiv('members-external-filter-positions-by-member', 'Members in Positions')
taskdetails_filters += filterdiv('members-external-filter-taskgroups-by-member', 'Members in Task Groups')
taskdetails_filters += filterdiv('members-external-filter-tasks', 'Task')
taskdetails_filters += filterdiv('members-external-filter-taskgroups-by-task', 'Tasks in Task Groups')
taskdetails_filters += filterdiv('members-external-filter-statuses', 'Status')
taskdetails_filters += filterdiv('members-external-filter-completed', 'Last Completed')
taskdetails_filters += filterdiv('members-external-filter-expires', 'Expiration Date')

taskdetails_yadcf_options = [
    yadcfoption('member:name', 'members-external-filter-members', 'multi_select', placeholder='Select members', width='200px'),
    yadcfoption('task:name', 'members-external-filter-tasks', 'multi_select', placeholder='Select tasks', width='200px'),
    yadcfoption('task_taskgroups.taskgroup:name', 'members-external-filter-taskgroups-by-task', 'multi_select', placeholder='Select task groups', width='200px'),
    yadcfoption('member_positions.position:name', 'members-external-filter-positions-by-member', 'multi_select', placeholder='Select task groups', width='200px'),
    yadcfoption('member_taskgroups.taskgroup:name', 'members-external-filter-taskgroups-by-member', 'multi_select', placeholder='Select task groups', width='200px'),
    yadcfoption('status:name', 'members-external-filter-statuses', 'multi_select', placeholder='Select statuses', width='200px'),
    yadcfoption('lastcompleted:name', 'members-external-filter-completed', 'range_date'),
    yadcfoption('expires:name', 'members-external-filter-expires', 'range_date'),
]

taskdetails = TaskDetails(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Task,
                    template = 'datatables.jinja2',
                    templateargs = {
                        'tablefiles': lambda: fieldupload.list(),
                        'adminguide': 'https://members.readthedocs.io/en/latest/leadership-task-admin-guide.html',
                    },
                    pretablehtml = taskdetails_filters,
                    yadcfoptions = taskdetails_yadcf_options,
                    pagename = 'Task Details',
                    endpoint = 'admin.taskdetails',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/taskdetails',
                    dbmapping = taskdetails_dbmapping,
                    formmapping = taskdetails_formmapping,
                    checkrequired = True,
                    validate = taskdetails_validate,
                    clientcolumns = [
                        {'data': 'member', 'name': 'member', 'label': 'Member',
                         'type': 'readonly',
                         },
                        {'data': 'order', 'name': 'order', 'label': 'Display Order',
                         'type': 'hidden',
                         'className': 'Hidden',
                         },
                        {'data': 'status', 'name': 'status', 'label': 'Status',
                         'type': 'readonly',
                         'className': 'status-field',
                         },
                        {'data': 'task', 'name': 'task', 'label': 'Task',
                         'type': 'readonly',
                         },
                        {'data': 'lastcompleted', 'name': 'lastcompleted', 'label': 'Last Completed',
                         'type': 'datetime',
                         # 'ed': {'opts':{'maxDate':date.today().isoformat()}}
                         },
                        {'data': 'expires', 'name': 'expires', 'label': 'Expiration Date',
                         'type': 'readonly',
                         'className': 'status-field',
                         },
                        {'data': 'member_positions', 'name': 'member_positions', 'label': 'Member Positions',
                         # 'type': 'readonly',
                         '_treatment': {
                             'relationship': {
                                 'optionspicker' : ReadOnlySelect2(
                                    fieldmodel = Position, labelfield = 'position',
                                    formfield = 'member_positions',
                                    dbfield = 'member_positions', uselist = True,
                                    queryparams = localinterest_query_params,
                                 )
                             }}
                         },
                        {'data': 'member_taskgroups', 'name': 'member_taskgroups', 'label': 'Member Task Groups',
                         # 'type': 'readonly',
                         '_treatment': {
                             'relationship': {
                                 'optionspicker' : ReadOnlySelect2(
                                    fieldmodel = TaskGroup, labelfield = 'taskgroup',
                                    formfield = 'member_taskgroups',
                                    dbfield = 'member_taskgroups', uselist = True,
                                    queryparams = localinterest_query_params,
                                 )
                             }}
                         },
                        {'data': 'task_taskgroups', 'name': 'task_taskgroups', 'label': 'Task Task Groups',
                         'type': 'readonly',
                         '_treatment': {
                             'relationship': {
                                 'optionspicker' : ReadOnlySelect2(
                                        fieldmodel = TaskGroup, labelfield = 'taskgroup', formfield = 'task_taskgroups',
                                        dbfield = 'task_taskgroups', uselist = True,
                                        queryparams = localinterest_query_params,
                                 )

                            }}
                         },
                        {'data': 'fields', 'name': 'fields', 'label': 'Add\'l Fields',
                         'type': 'readonly',
                         'dtonly': True,
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons = [
                        {
                            'extend':'editRefresh',
                            'text':'View',
                            'editor': {'eval':'editor'},
                            'formButtons': [
                                {'text': 'Update', 'action': {'eval': 'submit_button'}},
                                {'text': 'Dismiss', 'action': {'eval':'dismiss_button'}}
                            ]
                        },
                        'csv'
                    ],
                    dtoptions = {
                        'scrollCollapse': True,
                        'scrollX': True,
                        'scrollXInner': "100%",
                        'scrollY': True,
                        'rowCallback': {'eval': 'set_cell_status_class'},
                        # note id is column 0 to datatables, col 2 (display order) hidden
                        'order': [[1, 'asc'], [2, 'asc'], [6, 'asc']],
                    },
                    edoptions={
                        'i18n':
                            # "edit" window shows "Task" in title
                            {'edit':
                                {
                                    'title': 'Task',
                                }
                            }
                    },
                )
taskdetails.register()

##########################################################################################
# membersummary endpoint
###########################################################################################

status_slugs = [slugify(s) for s in STATUS_DISPLAYORDER]
slug2status = dict(zip(status_slugs, STATUS_DISPLAYORDER))
status2slug = dict(zip(STATUS_DISPLAYORDER, status_slugs))
membersummary_dbattrs = 'id,interest_id,member,member_positions,member_taskgroups'.split(',') + status_slugs
membersummary_formfields = 'rowid,interest_id,member,member_positions,member_taskgroups'.split(',') + status_slugs
membersummary_dbmapping = dict(zip(membersummary_dbattrs, membersummary_formfields))
membersummary_formmapping = dict(zip(membersummary_formfields, membersummary_dbattrs))

class MemberMember():
    '''
    allows creation of "membermember" object to simulate database behavior
    '''
    def __init__(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])

class MemberSummary(DbCrudApiInterestsRolePermissions):
    def open(self):
        # create another instance of TaskDetails
        taskdetails = TaskDetails(
            app=bp,  # use blueprint instead of app
            db=db,
            model=Task,
            local_interest_model=LocalInterest,
            dbmapping=taskdetails_dbmapping,
            formmapping=taskdetails_formmapping,
            rule='unused',
            clientcolumns=[
                {'data': 'member', 'name': 'member', 'label': 'Member',
                 'type': 'readonly',
                 },
                {'data': 'status', 'name': 'status', 'label': 'Status',
                 'type': 'readonly',
                 'className': 'status-field',
                 },
            ],
        )

        members = {}
        taskdetails.open()
        linterest = localinterest()
        for row in taskdetails.rows:
            thistask = taskdetails.dte.get_response_data(row)
            # add user record
            localuserid, taskid = taskdetails.getids(row.id)
            thistask['User'] = localuser2user(localuserid)
            name = thistask['User'].name

            # add member name to members if not already there
            if name not in members:
                # note taskgroups should be the same for all task records, so ok to set with first for this member
                members[name] = MemberMember(
                    id = localuserid,
                    member = name,
                    member_positions = thistask['member_positions'],
                    member_taskgroups = thistask['member_taskgroups'],
                    interest_id = linterest.id,
                )
                for slug in status_slugs:
                    setattr(members[name], slug, 0)

            # update status for this record
            thisslug = status2slug[thistask['status']]
            count = getattr(members[name], thisslug)
            setattr(members[name], thisslug, count+1)

        # set rows for response
        therows = []
        for name in members:
            for slug in status_slugs:
                if (getattr(members[name],slug) == 0):
                    setattr(members[name],slug,None)
            therows.append(members[name])
        self.rows = iter(therows)

membersummary_filters = filtercontainerdiv()
membersummary_filters += filterdiv('members-external-filter-members', 'Member')
membersummary_filters += filterdiv('members-external-filter-positions-by-member', 'Members in Positions')
membersummary_filters += filterdiv('members-external-filter-taskgroups-by-member', 'Members in Task Groups')

membersummary_yadcf_options = [
    yadcfoption('member:name', 'members-external-filter-members', 'multi_select', placeholder='Select members', width='200px'),
    yadcfoption('member_positions.position:name', 'members-external-filter-positions-by-member', 'multi_select', placeholder='Select task groups', width='200px'),
    yadcfoption('member_taskgroups.taskgroup:name', 'members-external-filter-taskgroups-by-member', 'multi_select', placeholder='Select task groups', width='200px'),
]

membersummary = MemberSummary(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = LocalUser,
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/leadership-task-admin-guide.html'},
                    pretablehtml = membersummary_filters,
                    yadcfoptions = membersummary_yadcf_options,
                    pagename = 'Member Summary',
                    endpoint = 'admin.membersummary',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/membersummary',
                    dbmapping = membersummary_dbmapping,
                    formmapping = membersummary_formmapping,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'member', 'name': 'member', 'label': 'Member',
                         'type':'readonly',
                         },
                    ] + [
                        {'data':slug, 'name':slug,
                         'type':'readonly',
                         'class': 'TextCenter',
                         'label':slug2status[slug]
                         } for slug in status_slugs
                    ] + [
                        {'data': 'member_positions', 'name': 'member_positions', 'label': 'Member Positions',
                         'type': 'readonly',
                         '_treatment': {
                             'relationship': {
                                 'optionspicker' : ReadOnlySelect2(
                                    fieldmodel = Position, labelfield = 'position',
                                    formfield = 'member_positions',
                                    dbfield = 'member_positions', uselist = True,
                                    queryparams = localinterest_query_params,
                                 )
                             }}
                         },
                        {'data': 'member_taskgroups', 'name': 'member_taskgroups', 'label': 'Member Task Groups',
                         'type': 'readonly',
                         '_treatment': {
                             'relationship': {
                                 'optionspicker' : ReadOnlySelect2(
                                    fieldmodel = TaskGroup, labelfield = 'taskgroup',
                                    formfield = 'member_taskgroups',
                                    dbfield = 'member_taskgroups', uselist = True,
                                    queryparams = localinterest_query_params,
                                 )
                             }}
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons=[
                        {
                            'extend': 'edit',
                            'text': 'View Member',
                            'action': {'eval': 'member_details'}
                        },
                        'csv'
                    ],

                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
membersummary.register()

##########################################################################################
# history endpoint
###########################################################################################

history_dbattrs = 'id,interest_id,member,task,completion,update_time,updated_by'.split(',')
history_formfields = 'rowid,interest_id,member,task,completion,update_time,updated_by'.split(',')
history_dbmapping = dict(zip(history_dbattrs, history_formfields))
history_formmapping = dict(zip(history_formfields, history_dbattrs))

history_formmapping['member'] = lambda tc: localuser2user(tc.user_id).name
history_formmapping['task'] = lambda tc: tc.task.task
history_formmapping['completion'] = lambda tc: dtrender.dt2asc(tc.completion)
history_formmapping['update_time'] = lambda tc: dttimerender.dt2asc(tc.update_time)
history_formmapping['updated_by'] = lambda tc: localuser2user(tc.updated_by).name

history_filters = filtercontainerdiv()
history_filters += filterdiv('members-external-filter-update-time', 'Update Time')
history_filters += filterdiv('members-external-filter-updated-by', 'Updated By')
history_filters += filterdiv('members-external-filter-members', 'Member')
history_filters += filterdiv('members-external-filter-tasks', 'Task')
history_filters += filterdiv('members-external-filter-completed', 'Completed')

history_yadcf_options = [
    yadcfoption('update_time:name', 'members-external-filter-update-time', 'range_date'),
    yadcfoption('updated_by:name', 'members-external-filter-updated-by', 'multi_select', placeholder='Select who updated', width='200px'),
    yadcfoption('member:name', 'members-external-filter-members', 'multi_select', placeholder='Select members', width='200px'),
    yadcfoption('task:name', 'members-external-filter-tasks', 'multi_select', placeholder='Select tasks', width='200px'),
    yadcfoption('completion:name', 'members-external-filter-completed', 'range_date'),
]

history = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = TaskCompletion,
                    template = 'datatables.jinja2',
                    templateargs={'adminguide': 'https://members.readthedocs.io/en/latest/leadership-task-admin-guide.html'},
                    pretablehtml = history_filters,
                    yadcfoptions=history_yadcf_options,
                    pagename = 'History',
                    endpoint = 'admin.history',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/history',
                    dbmapping = history_dbmapping, 
                    formmapping = history_formmapping,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'update_time', 'name': 'update_time', 'label': 'Update Time',
                         'type': 'readonly',
                         },
                        {'data': 'updated_by', 'name': 'updated_by', 'label': 'Updated By',
                         'type': 'readonly',
                         },
                        {'data': 'member', 'name': 'member', 'label': 'Member',
                         'type': 'readonly',
                         },
                        {'data': 'task', 'name': 'task', 'label': 'Task',
                         'type': 'readonly',
                         },
                        {'data': 'completion', 'name': 'completion', 'label': 'Date Completed',
                         'type': 'readonly',
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons = [
                        {
                            'extend':'editRefresh',
                            'text':'View',
                            'editor': {'eval':'editor'},
                            'formButtons': [
                                {'text': 'Dismiss', 'action': {'eval':'dismiss_button'}}
                            ]
                        },
                        'csv'
                    ],
                    dtoptions = {
                        'scrollCollapse': True,
                        'scrollX': True,
                        'scrollXInner': "100%",
                        'scrollY': True,
                        'order': [[1, 'desc']],
                    },
                    edoptions={
                        'i18n':
                            # "edit" window shows "Task" in title
                            {'edit':
                                {
                                    'title': 'Task Completion',
                                }
                            }
                    },
                    )
history.register()


