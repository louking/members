'''
models - database models for application
===========================================
'''

# pypi

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
DESCR_LEN = 512
LABEL_LEN = 64
FIELDINFO_LEN = 128
DISPLAYVALUE_LEN = 1024

usertaskgroup_table = Table('user_taskgroup', Base.metadata,
                       Column('user_id', Integer, ForeignKey('localuser.id')),
                       Column('taskgroup_id', Integer, ForeignKey('taskgroup.id')),
                       )

tasktaskgroup_table = Table('task_taskgroup', Base.metadata,
                       Column('task_id', Integer, ForeignKey('task.id')),
                       Column('taskgroup_id', Integer, ForeignKey('taskgroup.id')),
                       )

# copied by update_local_tables
class LocalUser(Base):
    __tablename__ = 'localuser'
    id                  = Column(Integer(), primary_key=True)
    user_id             = Column(Integer)
    active              = Column(Boolean)

# note update_local_tables only copies Interests for current application (g.loutility)
class LocalInterest(Base):
    __tablename__ = 'localinterest'
    id                  = Column(Integer(), primary_key=True)
    interest_id         = Column(Integer)

class TaskType(Base):
    __tablename__ = 'tasktype'
    id                  = Column(Integer(), primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('tasktypes'))
    tasktype            = Column(String(TASKTYPE_LEN))
    description         = Column(String(DESCR_LEN))

class Task(Base):
    __tablename__ = 'task'
    id                  = Column(Integer(), primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('tasks'))
    task                = Column(String(TASK_LEN))
    description         = Column(String(DESCR_LEN))
    priority            = Column(Float)
    period              = Column(Interval())

class TaskField(Base):
    __tablename__ = 'taskfield'
    id                  = Column(Integer(), primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('taskfields'))
    label               = Column(String(LABEL_LEN))
    # either displayvalue or inputtype should be set, not both
    displayvalue        = Column(String(DISPLAYVALUE_LEN))
    inputtype_id        = Column(Integer, ForeignKey('inputtype.id'))
    inputtype           = relationship('InputType', backref=backref('taskfield', uselist=False))
    fieldinfo           = Column(String(FIELDINFO_LEN))
    priority            = Column(Float)

# note InputType spans across Interests
class InputType(Base):
    __tablename__ = 'inputtype'
    id                  = Column(Integer(), primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
    inputtype           = Column(Enum('textarea', 'shorttext', 'file', 'yesno', 'checkbox'))

class TaskGroup(Base):
    __tablename__ = 'taskgroup'
    id                  = Column(Integer(), primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
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

class UserTaskCompletion(Base):
    __tablename__ = 'usertaskcompletion'
    id                  = Column(Integer(), primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
    interest_id         = Column(Integer, ForeignKey('localinterest.id'))
    interest            = relationship('LocalInterest', backref=backref('usertaskcompletions'))
    user_id             = Column(Integer, ForeignKey('localuser.id'))
    user                = relationship('LocalUser', backref=backref('taskscompleted'))
    task_id             = Column(Integer, ForeignKey('task.id'))
    task                = relationship('Task', backref=backref('userscompleted'))
    completion          = Column(DateTime)

def update_local_tables():
    '''
    keep LocalUser table consistent with external db User table
    '''
    # appname needs to match Application.application
    localtables = ManageLocalTables(db, 'members', LocalUser, LocalInterest)
    localtables.update()

