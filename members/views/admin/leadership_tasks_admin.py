'''
leadership_tasks_admin - administrative task handling
===========================================
'''
# standard
from datetime import timedelta

# pypi
from flask import g, url_for, current_app
from sqlalchemy import Enum
from dominate.tags import a

# homegrown
from . import bp
from ...model import db
from ...model import LocalInterest, LocalUser, Task, TaskField, TaskGroup, TaskTaskField, TaskCompletion
from ...model import InputFieldData, Files
from ...model import input_type_all, localinterest_query_params, localinterest_viafilter, gen_fieldname
from ...model import FIELDNAME_ARG, INPUT_TYPE_UPLOAD

from loutilities.user.model import User
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.tables import DteDbOptionsPickerBase, DteDbRelationship, get_request_action, get_request_data
from loutilities.tables import SEPARATOR
from loutilities.filters import filtercontainerdiv, filterdiv, yadcfoption
from .viewhelpers import lastcompleted, get_status, get_order, get_expires, user2localuser

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


task_dbattrs = 'id,interest_id,task,description,priority,period,isoptional,fields'.split(',')
task_formfields = 'rowid,interest_id,task,description,priority,period,isoptional,fields'.split(',')
task_dbmapping = dict(zip(task_dbattrs, task_formfields))
task_formmapping = dict(zip(task_formfields, task_dbattrs))
DAYS_PER_PERIOD = 7
task_dbmapping['period'] = lambda formrow: timedelta(int(formrow['period'])*DAYS_PER_PERIOD) if formrow['period'] else None
task_formmapping['period'] = lambda dbrow: dbrow.period.days // DAYS_PER_PERIOD if dbrow.period else None

task = AssociationCrudApi(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Task,
                    assnmodelfield='task',
                    assnlistfield='fields',
                    version_id_col = 'version_id',  # optimistic concurrency control
                    template = 'datatables.jinja2',
                    pagename = 'Tasks',
                    endpoint = 'admin.tasks',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/tasks',
                    dbmapping = task_dbmapping, 
                    formmapping = task_formmapping, 
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'task', 'name': 'task', 'label': 'Task',
                         'className': 'field_req',
                         },
                        {'data': 'priority', 'name': 'priority', 'label': 'Priority',
                         'className': 'field_req',
                         },
                        {'data': 'description', 'name': 'description', 'label': 'Display', 'type': 'textarea',
                         'className': 'field_req',
                         'fieldInfo': '<a href=https://daringfireball.net/projects/markdown/syntax target=_blank>Markdown</a>' +
                                      ' can be used. Click link for syntax'
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
                        {'data': 'period', 'name': 'period', 'label': 'Period (weeks)',
                         'fieldInfo': 'leave blank if this task doesn\'t need to be done periodically'
                         },
                        {'data': 'isoptional', 'name': 'isoptional', 'label': 'Optional Task',
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
                    )
task.register()

##########################################################################################
# taskfields endpoint
###########################################################################################

taskfield_dbattrs = 'id,interest_id,taskfield,fieldname,displaylabel,displayvalue,fieldinfo,fieldoptions,inputtype,priority,uploadurl'.split(',')
taskfield_formfields = 'rowid,interest_id,taskfield,fieldname,displaylabel,displayvalue,fieldinfo,fieldoptions,inputtype,priority,uploadurl'.split(',')
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
            taskfield.uploadurl == (url_for('admin.fieldupload', interest=g.interest)
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
                    pagename = 'Task Fields',
                    endpoint = 'admin.taskfields',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/taskfields',
                    dbmapping = taskfield_dbmapping, 
                    formmapping = taskfield_formmapping, 
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'taskfield', 'name': 'taskfield', 'label': 'Field Name',
                         'className': 'field_req',
                         # TODO: is this unique in the table or within an interest? Needs to be within an interest
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
                        {'data': 'displayvalue', 'name': 'displayvalue', 'label': 'Field Value', 'type': 'textarea'},
                        {'data': 'fieldname', 'name': 'fieldname', 'label': 'Field Name', 'type': 'readonly'
                         },
                        {'data': 'uploadurl', 'name': 'uploadurl', 'label': 'Upload URL', 'type': 'readonly'
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
# taskgroups endpoint
###########################################################################################

taskgroup_dbattrs = 'id,interest_id,taskgroup,description,tasks,users'.split(',')
taskgroup_formfields = 'rowid,interest_id,taskgroup,description,tasks,users'.split(',')
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
                    pagename = 'Task Groups',
                    endpoint = 'admin.taskgroups',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/taskgroups',
                    dbmapping = taskgroup_dbmapping, 
                    formmapping = taskgroup_formmapping,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'taskgroup', 'name': 'taskgroup', 'label': 'Task Group',
                         'className': 'field_req',
                         # TODO: is this unique in the table or within an interest? Needs to be within an interest
                         '_unique': True,
                         },
                        {'data': 'description', 'name': 'description', 'label': 'Description',
                         'className': 'field_req',
                         },
                        {'data': 'tasks', 'name': 'tasks', 'label': 'Tasks',
                         '_treatment': {
                             'relationship': {'fieldmodel': Task, 'labelfield': 'task', 'formfield': 'tasks',
                                              'dbfield': 'tasks', 'uselist': True,
                                              'queryparams': localinterest_query_params,
                                              }}
                         },
                        {'data': 'users', 'name': 'users', 'label': 'Users',
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
# usertaskgroups endpoint
###########################################################################################

def set_bound_user(formrow):
    user = User.query.filter_by(name=formrow['user_id']).one()
    return user.id

def get_bound_user(dbrow):
    user = User.query.filter_by(id=dbrow.user_id).one()
    return user.name
    
assigntaskgroup_dbattrs = 'id,user_id,taskgroups'.split(',')
assigntaskgroup_formfields = 'rowid,user_id,taskgroups'.split(',')
assigntaskgroup_dbmapping = dict(zip(assigntaskgroup_dbattrs, assigntaskgroup_formfields))
assigntaskgroup_formmapping = dict(zip(assigntaskgroup_formfields, assigntaskgroup_dbattrs))
assigntaskgroup_dbmapping['user_id'] = set_bound_user
assigntaskgroup_formmapping['user_id'] = get_bound_user

assigntaskgroup = DbCrudApiInterestsRolePermissions(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = LocalUser,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    queryparams = {'active': True},
                    template = 'datatables.jinja2',
                    pagename = 'Assign Task Groups',
                    endpoint = 'admin.assigntaskgroups',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/assigntaskgroups',
                    dbmapping = assigntaskgroup_dbmapping, 
                    formmapping = assigntaskgroup_formmapping,
                    checkrequired = True,
                    clientcolumns = [
                        {'data': 'user_id', 'name': 'user_id', 'label': 'Member',
                         'className': 'field_req',
                         # TODO: is this unique in the table or within an interest? Needs to be within an interest
                         '_unique': True,
                         },
                        {'data': 'taskgroups', 'name': 'taskgroups', 'label': 'Task Groups',
                         '_treatment': {
                             'relationship': {'fieldmodel': TaskGroup, 'labelfield': 'taskgroup', 'formfield': 'taskgroups',
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
assigntaskgroup.register()

##########################################################################################
# tasksummary endpoint
###########################################################################################

def addlfields(task, member):
    taskfields = []
    localuser = user2localuser(member)
    tc = TaskCompletion.query.filter_by(task=task, user=localuser).order_by(TaskCompletion.completion.desc()).first()
    if tc:
        for ttf in task.fields:
            f = ttf.taskfield
            thistaskfield = {}
            for key in 'taskfield,fieldname,displaylabel,displayvalue,inputtype,fieldinfo,priority,uploadurl'.split(','):
                thistaskfield[key] = getattr(f, key)
            thistaskfield['fieldoptions'] = get_options(f)
            value = InputFieldData.query.filter_by(field=f, taskcompletion=tc).one().value
            if f.inputtype != INPUT_TYPE_UPLOAD:
                thistaskfield['value'] = value
            else:
                file = Files.query.filter_by(fileid=value).one()
                thistaskfield['value'] = a(file.filename,
                                           href=url_for('admin.file',
                                                        interest=g.interest,
                                                        fileid=value),
                                           target='_blank').render()
            taskfields.append(thistaskfield)
    return taskfields

# map id to rowid, retrieve all other required fields
# no dbmapping because this table is read-only
tasksummary_dbattrs = 'id,member,task,lastcompleted,status,order,expires,fields,task_taskgroups,member_taskgroups'.split(',')
tasksummary_formfields = 'rowid,member,task,lastcompleted,status,order,expires,fields,task_taskgroups,member_taskgroups'.split(',')
tasksummary_dbmapping = dict(zip(tasksummary_dbattrs, tasksummary_formfields))

tasksummary_formmapping = {}
tasksummary_formmapping['rowid'] = 'id'
tasksummary_formmapping['task_taskgroups'] = 'task_taskgroups'
tasksummary_formmapping['member_taskgroups'] = 'member_taskgroups'
tasksummary_formmapping['member'] = lambda tu: tu.member.name
tasksummary_formmapping['task'] = lambda tu: tu.task.task
tasksummary_formmapping['lastcompleted'] = lambda tu: lastcompleted(tu.task, tu.member)
tasksummary_formmapping['status'] = lambda tu: get_status(tu.task, tu.member)
tasksummary_formmapping['order'] = lambda tu: get_order(tu.task, tu.member)
tasksummary_formmapping['expires'] = lambda tu: get_expires(tu.task, tu.member)
tasksummary_formmapping['fields'] = lambda tu: 'yes' if tu.task.fields else ''
tasksummary_formmapping['addlfields'] = lambda tu: addlfields(tu.task, tu.member)

class TaskUser():
    '''
    allows creation of "taskuser" object to simulate database behavior
    '''
    def __init__(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])

class TaskSummary(DbCrudApiInterestsRolePermissions):
    def _setdata(self):
        taskgroups = TaskGroup.query.all()
        self.data = {}

        # collect all the members which are referenced by taskgroups
        localusers = set()
        for taskgroup in taskgroups:
            for localuser in taskgroup.users:
                localusers |= set([localuser])

        # retrieve member data from localusers
        members = []
        for localuser in iter(localusers):
            members.append({'localuser':localuser, 'member': User.query.filter_by(id=localuser.user_id).one()})

        tasksusers = []
        fakeid = 0
        for member in members:
            # collect all the tasks which are referenced by taskgroups for this member
            tasks = set()
            for taskgroup in member['localuser'].taskgroups:
                for task in taskgroup.tasks:
                    tasks |= set([task])
            for task in iter(tasks):
                fakeid += 1
                taskuser = TaskUser(
                    id=fakeid,
                    task=task, task_taskgroups=task.taskgroups,
                    member=member['member'], member_taskgroups=member['localuser'].taskgroups
                )
                tasksusers.append(taskuser)
                from copy import copy
                self.data[fakeid] = copy(taskuser)

        return tasksusers

    def open(self):
        taskgroups = TaskGroup.query.all()

        # collect all the members which are referenced by taskgroups
        localusers = set()
        for taskgroup in taskgroups:
            for localuser in taskgroup.users:
                localusers |= set([localuser])

        # retrieve member data from localusers
        members = []
        for localuser in iter(localusers):
            members.append({'localuser':localuser, 'member': User.query.filter_by(id=localuser.user_id).one()})

        tasksusers = []
        for member in members:
            # collect all the tasks which are referenced by taskgroups for this member
            tasks = set()
            for taskgroup in member['localuser'].taskgroups:
                for task in taskgroup.tasks:
                    tasks |= set([task])
            for task in iter(tasks):
                usertaskid = '{};{}'.format(member['localuser'].id, task.id)
                taskuser = TaskUser(
                    id=usertaskid,
                    task=task, task_taskgroups=task.taskgroups,
                    member=member['member'], member_taskgroups=member['localuser'].taskgroups
                )
                tasksusers.append(taskuser)
        self.rows = iter(tasksusers)

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
            localuserid, taskid = thisid.split(';')
            localuser = LocalUser.query.filter_by(id=localuserid).one()
            task = Task.query.filter_by(id=taskid).one()

            member = {'localuser': localuser, 'member': User.query.filter_by(id=localuser.user_id).one()}

            taskuser = TaskUser(
                id=thisid,
                task=task, task_taskgroups=task.taskgroups,
                member=member['member'], member_taskgroups=member['localuser'].taskgroups
            )

            responsedata.append(self.dte.get_response_data(taskuser))

        return responsedata

class ReadOnlySelect2(DteDbRelationship):
    def col_options(self):
        col = super().col_options()
        # readonly select2
        col['opts']['disabled'] = True
        return col

filters = filtercontainerdiv()
filters += filterdiv('members-external-filter-members', 'Member')
filters += filterdiv('members-external-filter-tasks', 'Task')
filters += filterdiv('members-external-filter-taskgroups-by-task', 'Tasks in Task Groups')
filters += filterdiv('members-external-filter-taskgroups-by-member', 'Members in Task Groups')
filters += filterdiv('members-external-filter-statuses', 'Status')
filters += filterdiv('members-external-filter-completed', 'Last Completed')
filters += filterdiv('members-external-filter-expires', 'Expires')

membercol = 1
tasksummary_yadcf_options = [
    yadcfoption('member:name', 'members-external-filter-members', 'multi_select', placeholder='Select members', width='150px'),
    yadcfoption('task:name', 'members-external-filter-tasks', 'multi_select', placeholder='Select tasks', width='200px'),
    yadcfoption('task_taskgroups.taskgroup:name', 'members-external-filter-taskgroups-by-task', 'multi_select', placeholder='Select task groups', width='200px'),
    yadcfoption('member_taskgroups.taskgroup:name', 'members-external-filter-taskgroups-by-member', 'multi_select', placeholder='Select task groups', width='200px'),
    yadcfoption('status:name', 'members-external-filter-statuses', 'multi_select', placeholder='Select statuses', width='200px'),
    yadcfoption('lastcompleted:name', 'members-external-filter-completed', 'range_date'),
    yadcfoption('expires:name', 'members-external-filter-expires', 'range_date'),
]

tasksummary = TaskSummary(
                    roles_accepted = [ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN],
                    local_interest_model = LocalInterest,
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Task,
                    template = 'datatables.jinja2',
                    pretablehtml = filters,
                    pagename = 'Task Summary',
                    endpoint = 'admin.tasksummary',
                    endpointvalues={'interest': '<interest>'},
                    rule = '/<interest>/tasksummary',
                    dbmapping = tasksummary_dbmapping,
                    formmapping = tasksummary_formmapping, 
                    checkrequired = True,
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
                         'type': 'readonly',
                         },
                        {'data': 'expires', 'name': 'expires', 'label': 'Expires',
                         'type': 'readonly',
                         'className': 'status-field',
                         },
                        {'data': 'task_taskgroups', 'name': 'task_taskgroups', 'label': 'Task in Task Groups',
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
                        {'data': 'member_taskgroups', 'name': 'member_taskgroups', 'label': 'Member in Task Groups',
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
                        # note id is column 0 to datatables
                        'order': [[1, 'asc'], [2, 'asc']],
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
                    yadcfoptions=tasksummary_yadcf_options,
                )
tasksummary.register()

