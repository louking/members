###########################################################################################
# models - database models for application
#
#       Date            Author          Reason
#       ----            ------          ------
#       03/02/20        Lou King        Create
#
#   Copyright 2020 Lou King.  All rights reserved
###########################################################################################

# pypi

# home grown
# need to use a single SQLAlchemy() instance, so pull from loutilities.user.model
from loutilities.user.model import db, ManageLocalUser
from loutilities.user.audit_mixin import AuditMixin

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

class TaskType(Base):
    __tablename__ = 'tasktype'
    id                  = Column(Integer(), primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
    tasktype            = Column(String(TASKTYPE_LEN))
    description         = Column(String(DESCR_LEN))

usertaskgroup_table = Table('user_taskgroup', Base.metadata,
                       Column('user_id', Integer, ForeignKey('localuser.id')),
                       Column('taskgroup_id', Integer, ForeignKey('taskgroup.id')),
                       )

tasktaskgroup_table = Table('task_taskgroup', Base.metadata,
                       Column('task_id', Integer, ForeignKey('task.id')),
                       Column('taskgroup_id', Integer, ForeignKey('taskgroup.id')),
                       )

class LocalUser(Base, AuditMixin):
    __tablename__ = 'localuser'
    id                  = Column(Integer(), primary_key=True)
    user_id             = Column(Integer)
    active              = Column(Boolean)

def update_local_user():
    '''
    keep LocalUser table consistent with external db User table
    '''
    localuser = ManageLocalUser(db, LocalUser)
    localuser.update()
    # # don't try to update before table exists
    # if not db.engine.has_table('localuser'): return
    #
    # # alllocal will be used to determine what LocalUser rows need to be deactivated
    # # this detects deletions in User table
    #
    # alllocal = {}
    # for localuser in LocalUser.query.all():
    #     alllocal[localuser.user_id] = localuser
    # from loutilities.user.model import User
    # for user in User.query.all():
    #     # remove from deactivate list; update active status
    #     if user.id in alllocal:
    #         localuser = alllocal.pop(user.id)
    #         localuser.active = user.active
    #     # needs to be added
    #     else:
    #         newlocal = LocalUser(user_id=user.id, active=user.active)
    #         db.session.add(newlocal)
    # # all remaining in alllocal need to be deactivated
    # for user_id in alllocal:
    #     localuser = LocalUser.query.filter_by(user_id=user_id).one()
    #     localuser.active = False
    # db.session.commit()

# @event.listens_for(User.active, 'set')
# def set_user(target, value, oldvalue, initiator):
#     update_local_user()
#
# @event.listens_for(User.active, 'remove')
# def remove_user(target, value, initiator):
#     update_local_user()
#
# @event.listens_for(User.active, 'modified')
# def modified_user(target, initiator):
#     update_local_user()
#
# @event.listens_for(User.active, 'append')
# def append_user(target, value, initiator):
#     update_local_user()

class Task(Base):
    __tablename__ = 'task'
    id                  = Column(Integer(), primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
    task                = Column(String(TASK_LEN))
    description         = Column(String(DESCR_LEN))
    priority            = Column(Float)
    period              = Column(Interval())

class TaskField(Base):
    __tablename__ = 'taskfield'
    id                  = Column(Integer(), primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
    label               = Column(String(LABEL_LEN))
    # either displayvalue or inputtype should be set, not both
    displayvalue        = Column(String(DISPLAYVALUE_LEN))
    inputtype_id        = Column(Integer, ForeignKey('inputtype.id'))
    inputtype           = relationship('InputType', backref=backref('taskfield', uselist=False))
    fieldinfo           = Column(String(FIELDINFO_LEN))
    priority            = Column(Float)

class InputType(Base):
    __tablename__ = 'inputtype'
    id                  = Column(Integer(), primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
    inputtype           = Column(Enum('textarea', 'shorttext', 'file', 'yesno', 'checkbox'))

class TaskGroup(Base):
    __tablename__ = 'taskgroup'
    id                  = Column(Integer(), primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
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
    user_id             = Column(Integer, ForeignKey('localuser.id'))
    user                = relationship('LocalUser', backref=backref('taskscompleted'))
    task_id             = Column(Integer, ForeignKey('task.id'))
    task                = relationship('Task', backref=backref('userscompleted'))
    completion          = Column(DateTime)

