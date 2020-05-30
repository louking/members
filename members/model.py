'''
models - database models for application
===========================================
'''

# pypi
from flask import g

# home grown
# need to use a single SQLAlchemy() instance, so pull from loutilities.user.model
from loutilities.user.model import db, ManageLocalTables, EMAIL_LEN
from loutilities.user.tablefiles import FilesMixin

# set up database - SQLAlchemy() must be done after app.config SQLALCHEMY_* assignments
Table = db.Table
Column = db.Column
Integer = db.Integer
Float = db.Float
Boolean = db.Boolean
String = db.String
Text = db.Text
Date = db.Date
Time = db.Time
DateTime = db.DateTime
Sequence = db.Sequence
Enum = db.Enum
Interval = db.Interval
UniqueConstraint = db.UniqueConstraint
ForeignKey = db.ForeignKey
relationship = db.relationship
backref = db.backref
object_mapper = db.object_mapper
Base = db.Model

TASK_LEN = 64
TASKTYPE_LEN = 64
POSITION_LEN = 64
TASKGROUP_LEN = 64
TASKFIELD_LEN = 64
TASKFIELDNAME_LEN = 16
DESCR_LEN = 512
DISPLAYLABEL_LEN = 64
DISPLAYVALUE_LEN = 1024
FIELDINFO_LEN = 128
FIELDOPTIONS_LEN = 2048
URL_LEN = 2047      # https://stackoverflow.com/questions/417142/what-is-the-maximum-length-of-a-url-in-different-browsers
DOY_LEN = 5         # mm-dd
EMAIL_TEMPLATENAME_LEN = 32
EMAIL_SUBJECT_LEN = 128
EMAIL_TEMPLATE_LEN=2048
SERVICE_LEN=32
SERVICE_ID_LEN=32

usertaskgroup_table = Table('user_taskgroup', Base.metadata,
                       Column('user_id', Integer, ForeignKey('localuser.id')),
                       Column('taskgroup_id', Integer, ForeignKey('taskgroup.id')),
                       )

userposition_table = Table('user_position', Base.metadata,
                       Column('user_id', Integer, ForeignKey('localuser.id')),
                       Column('position_id', Integer, ForeignKey('position.id')),
                       )

positiontaskgroup_table = Table('position_taskgroup', Base.metadata,
                       Column('position_id', Integer, ForeignKey('position.id')),
                       Column('taskgroup_id', Integer, ForeignKey('taskgroup.id')),
                       )

positionemailgroup_table = Table('position_emailgroup', Base.metadata,
                       Column('position_id', Integer, ForeignKey('position.id')),
                       Column('taskgroup_id', Integer, ForeignKey('taskgroup.id')),
                       )

tasktaskgroup_table = Table('task_taskgroup', Base.metadata,
                       Column('task_id', Integer, ForeignKey('task.id')),
                       Column('taskgroup_id', Integer, ForeignKey('taskgroup.id')),
                       )

# taskfield_table = Table('task_taskfield', Base.metadata,
#                        Column('task_id', Integer, ForeignKey('task.id')),
#                        Column('taskfield_id', Integer, ForeignKey('taskfield.id')),
#                        )

# associate task / taskfield tables adding necessity attribute
NEED_REQUIRED = 'required'
NEED_ONE_OF   = 'oneof'
NEED_OPTIONAL = 'optional'
needs_all = [NEED_REQUIRED, NEED_ONE_OF, NEED_OPTIONAL]
class TaskTaskField(Base):
    __tablename__ = 'task_taskfield'
    task_id             = Column(Integer, ForeignKey('task.id'), primary_key=True)
    taskfield_id        = Column(Integer, ForeignKey('taskfield.id'), primary_key=True)
    need                = Column(Enum(*needs_all))
    task                = relationship('Task', back_populates='fields')
    taskfield           = relationship('TaskField', back_populates='tasks')

# copied by update_local_tables
class LocalUser(Base):
    __tablename__ = 'localuser'
    id                  = Column(Integer(), primary_key=True)
    user_id             = Column(Integer)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('users'))
    active              = Column(Boolean)

    version_id          = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        'version_id_col' : version_id
    }

# note update_local_tables only copies Interests for current application (g.loutility)
CLUB_SERVICE_RUNSIGNUP = 'runsignup'
all_club_services = [CLUB_SERVICE_RUNSIGNUP]
class LocalInterest(Base):
    __tablename__ = 'localinterest'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer)
    initial_expiration  = Column(Date)
    from_email          = Column(String(EMAIL_LEN))
    club_service        = Column(String(SERVICE_LEN))
    service_id          = Column(String(SERVICE_ID_LEN))

    version_id          = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        'version_id_col' : version_id
    }

DATE_UNIT_WEEKS = 'weeks'
DATE_UNIT_MONTHS = 'months'
DATE_UNIT_YEARS = 'years'
date_unit_all = (DATE_UNIT_WEEKS, DATE_UNIT_MONTHS, DATE_UNIT_YEARS)

class Task(Base):
    __tablename__ = 'task'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('tasks'))
    task                = Column(String(TASK_LEN))
    description         = Column(String(DESCR_LEN))
    priority            = Column(Float)
    expirysoon          = Column(Integer)
    expirysoon_units    = Column(Enum(*date_unit_all), nullable=True)
    period              = Column(Integer)          # period or dateofyear, not both
    period_units        = Column(Enum(*date_unit_all), nullable=True)
    dateofyear          = Column(String(DOY_LEN))   # mm-dd
    expirystarts        = Column(Integer)          # only used if dateofyear specified
    expirystarts_units  = Column(Enum(*date_unit_all), nullable=True)
    isoptional          = Column(Boolean)
    fields              = relationship('TaskTaskField',
                                       back_populates='task')

    version_id          = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        'version_id_col' : version_id
    }

# note InputType spans across Interests
# entries must be coordinated with code which supports each type
# types must be defined by editor as field type, e.g., see https://editor.datatables.net/reference/field/
# NOTE: if the text for any of these change or new ones are added, may need to update /static/admin/afterdatatables.js
INPUT_TYPE_CHECKBOX = 'checkbox'
INPUT_TYPE_RADIO = 'radio'
INPUT_TYPE_SELECT2 = 'select2'
INPUT_TYPE_TEXT = 'text'
INPUT_TYPE_TEXTAREA = 'textarea'
INPUT_TYPE_UPLOAD = 'upload'
INPUT_TYPE_DATE = 'datetime'
INPUT_TYPE_DISPLAY = 'display'
input_type_all = (INPUT_TYPE_CHECKBOX, INPUT_TYPE_RADIO, INPUT_TYPE_SELECT2,
                  INPUT_TYPE_TEXT, INPUT_TYPE_TEXTAREA, INPUT_TYPE_UPLOAD,
                  INPUT_TYPE_DATE, INPUT_TYPE_DISPLAY)
INPUT_VALUE_LEN = 4096
FIELDNAME_ARG = 'fieldname'

class TaskField(Base):
    __tablename__ = 'taskfield'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('taskfields'))
    taskfield           = Column(String(TASKFIELD_LEN))
    fieldname           = Column(String(TASKFIELDNAME_LEN))
    displaylabel        = Column(String(DISPLAYLABEL_LEN))
    inputtype           = Column(Enum(*input_type_all), nullable=True)
    # if inputtype == 'display' displayvalue must be set
    displayvalue        = Column(String(DISPLAYVALUE_LEN))
    fieldinfo           = Column(String(FIELDINFO_LEN))
    fieldoptions        = Column(String(FIELDOPTIONS_LEN))
    uploadurl           = Column(String(URL_LEN)) # (upload)
    priority            = Column(Float)
    override_completion = Column(Boolean) # (datetime) True means override TaskCompletion.completion
    tasks               = relationship('TaskTaskField',
                                       back_populates='taskfield')

    version_id          = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        'version_id_col' : version_id
    }


# https://blog.ramosly.com/sqlalchemy-orm-setting-up-self-referential-many-to-many-relationships-866c97d9308b
taskgroup_taskgroup_table = Table(
    'taskgroup_taskgroup', Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('parent_id', Integer, ForeignKey('taskgroup.id')),
    Column('child_id', Integer, ForeignKey('taskgroup.id')),
)

class TaskGroup(Base):
    __tablename__ = 'taskgroup'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('taskgroups'))
    taskgroup           = Column(String(TASKGROUP_LEN))
    description         = Column(String(DESCR_LEN))
    parent_id           = Column(Integer, ForeignKey('taskgroup.id'))
    taskgroups          = relationship('TaskGroup',
                                       secondary=taskgroup_taskgroup_table,
                                       primaryjoin=id == taskgroup_taskgroup_table.c.child_id,
                                       secondaryjoin=id == taskgroup_taskgroup_table.c.parent_id,
                                       )

    tasks               = relationship('Task',
                                       secondary=tasktaskgroup_table,
                                       backref=backref('taskgroups'))
    users               = relationship('LocalUser',
                                       secondary=usertaskgroup_table,
                                       backref=backref('taskgroups'))

    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        'version_id_col': version_id
    }

class Position(Base):
    __tablename__ = 'position'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('positions'))
    position            = Column(String(POSITION_LEN))
    description         = Column(String(DESCR_LEN))
    users               = relationship('LocalUser',
                                       secondary=userposition_table,
                                       backref=backref('positions'))
    taskgroups          = relationship('TaskGroup',
                                       secondary=positiontaskgroup_table,
                                       backref=backref('positions'))
    emailgroups         = relationship('TaskGroup',
                                       secondary=positionemailgroup_table,
                                       backref=backref('positionemailgroups'))

    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        'version_id_col': version_id
    }

class InputFieldData(Base):
    __tablename__ = 'inputfielddata'
    id                  = Column(Integer(), primary_key=True)
    field_id            = Column(Integer, ForeignKey('taskfield.id'))
    field               = relationship('TaskField', backref=backref('inputdata'))
    taskcompletion_id   = Column(Integer, ForeignKey('taskcompletion.id'))
    taskcompletion      = relationship('TaskCompletion', backref=backref('inputdata'))
    value               = Column(String(INPUT_VALUE_LEN))

class TaskCompletion(Base):
    __tablename__ = 'taskcompletion'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('taskcompletions'))
    user_id             = Column(Integer, ForeignKey('localuser.id'))
    user                = relationship('LocalUser', backref=backref('taskscompleted'))
    task_id             = Column(Integer, ForeignKey('task.id'))
    task                = relationship('Task', backref=backref('taskcompletions'))
    completion          = Column(DateTime)
    update_time         = Column(DateTime)
    updated_by          = Column(Integer)   # localuser.id

    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        'version_id_col': version_id
    }

class Files(Base, FilesMixin):
    __tablename__ = 'files'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship("LocalInterest")
    taskcompletion_id   = Column(Integer, ForeignKey('taskcompletion.id'))
    taskcompletion      = relationship("TaskCompletion")

class EmailTemplate(Base):
    __tablename__ = 'emailtemplate'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('emailtemplates'))
    templatename        = Column(String(EMAIL_TEMPLATENAME_LEN))
    subject             = Column(String(EMAIL_SUBJECT_LEN))
    template            = Column(String(EMAIL_TEMPLATE_LEN))

    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        'version_id_col': version_id
    }

def update_local_tables():
    '''
    keep LocalUser table consistent with external db User table
    '''
    # appname needs to match Application.application
    localtables = ManageLocalTables(db, 'members', LocalUser, LocalInterest, hasuserinterest=True)
    localtables.update()

def localinterest_query_params():
    from loutilities.user.model import Interest
    interest = Interest.query.filter_by(interest=g.interest).one()
    localinterest = LocalInterest.query.filter_by(interest_id=interest.id).one()
    return {'interest': localinterest}

def localinterest_viafilter():
    from loutilities.user.model import Interest
    interest = Interest.query.filter_by(interest=g.interest).one()
    return {'interest_id': interest.id}

def gen_fieldname():
    # https://www.educative.io/edpresso/how-to-generate-a-random-string-in-python
    from random import choice
    from string import ascii_letters
    return ''.join(choice(ascii_letters) for i in range(TASKFIELDNAME_LEN))