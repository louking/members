'''
models - database models for application
===========================================
'''

# pypi
from flask import g

# home grown
# need to use a single SQLAlchemy() instance, so pull from loutilities.user.model
from loutilities.user.model import db, ManageLocalTables

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
TASKGROUP_LEN = 64
TASKFIELD_LEN = 64
DESCR_LEN = 512
DISPLAYLABEL_LEN = 64
DISPLAYVALUE_LEN = 1024
FIELDINFO_LEN = 128

usertaskgroup_table = Table('user_taskgroup', Base.metadata,
                       Column('user_id', Integer, ForeignKey('localuser.id')),
                       Column('taskgroup_id', Integer, ForeignKey('taskgroup.id')),
                       )

tasktaskgroup_table = Table('task_taskgroup', Base.metadata,
                       Column('task_id', Integer, ForeignKey('task.id')),
                       Column('taskgroup_id', Integer, ForeignKey('taskgroup.id')),
                       )

taskfield_table = Table('task_taskfield', Base.metadata,
                       Column('task_id', Integer, ForeignKey('task.id')),
                       Column('taskfield_id', Integer, ForeignKey('taskfield.id')),
                       )

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
class LocalInterest(Base):
    __tablename__ = 'localinterest'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer)

class Task(Base):
    __tablename__ = 'task'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('tasks'))
    task                = Column(String(TASK_LEN))
    description         = Column(String(DESCR_LEN))
    priority            = Column(Float)
    period              = Column(Interval())
    fields              = relationship('TaskField',
                                       secondary=taskfield_table,
                                       backref=backref('tasks'))

    version_id          = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        'version_id_col' : version_id
    }

# note InputType spans across Interests
# entries must be coordinated with code which supports each type
INPUT_TYPE_TEXTAREA = 'textarea'
INPUT_TYPE_SHORTTEXT = 'shorttext'
INPUT_TYPE_FILE = 'file'
INPUT_TYPE_SELECT = 'select'
INPUT_TYPE_CHECKBOX = 'checkbox'
INPUT_TYPE_RADIOBUTTON = 'radiobutton'
input_type_all = (INPUT_TYPE_CHECKBOX, INPUT_TYPE_FILE, INPUT_TYPE_RADIOBUTTON, INPUT_TYPE_SELECT,
                  INPUT_TYPE_SHORTTEXT, INPUT_TYPE_TEXTAREA)

class TaskField(Base):
    __tablename__ = 'taskfield'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('taskfields'))
    taskfield           = Column(String(TASKFIELD_LEN))
    displaylabel        = Column(String(DISPLAYLABEL_LEN))
    # either displayvalue or inputtype should be set, not both
    displayvalue        = Column(String(DISPLAYVALUE_LEN))
    inputtype           = Column(Enum(*input_type_all), nullable=True)
    fieldinfo           = Column(String(FIELDINFO_LEN))
    priority            = Column(Float)

    version_id          = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        'version_id_col' : version_id
    }

class TaskGroup(Base):
    __tablename__ = 'taskgroup'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('taskgroups'))
    taskgroup           = Column(String(TASKGROUP_LEN))
    description         = Column(String(DESCR_LEN))
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


class UserTaskCompletion(Base):
    __tablename__ = 'usertaskcompletion'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('usertaskcompletions'))
    user_id             = Column(Integer, ForeignKey('localuser.id'))
    user                = relationship('LocalUser', backref=backref('taskscompleted'))
    task_id             = Column(Integer, ForeignKey('task.id'))
    task                = relationship('Task', backref=backref('userscompleted'))
    completion          = Column(DateTime)

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