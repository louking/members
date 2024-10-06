"""
scripts - save app and db
==============================
"""
# standard
from functools import wraps
from sys import exit

# pypi
from flask import current_app

class ParameterError(Exception): pass

def catch_errors(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except (ParameterError, RuntimeError) as exc:
            current_app.logger.error('in flask script: ' + str(exc))
            print(str(exc))
            exit(1)
    return wrapped

# homegrown
## put all top level command groups here, also update Members class
from scripts.meetings_cli import meetings
from scripts.membership_cli import membership
from scripts.task_cli import task

class MembersCli():
    # adapted from flask-migrate.Migrate
    def __init__(self, app, db):

        # need this for each command group
        app.cli.add_command(meetings)

class MembershipCli():
    # adapted from flask-migrate.Migrate
    def __init__(self, app, db):

        # need this for each command group
        app.cli.add_command(membership)

class TaskCli():
    # adapted from flask-migrate.Migrate
    def __init__(self, app, db):

        # need this for each command group
        app.cli.add_command(task)
