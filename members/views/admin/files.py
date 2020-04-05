###########################################################################################
# files - file administration
#
#       Date            Author          Reason
#       ----            ------          ------
#       12/24/19        Lou King        Create
#
#   Copyright 2019 Lou King.  All rights reserved
###########################################################################################

# standard
from os.path import join, exists

# pypi
from flask import g, current_app, send_from_directory

# homegrown
from . import bp
from ...model import db, Files, LocalInterest
from ..viewhelpers import localinterest
from loutilities.user.tablefiles import FilesCrud
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN, ROLE_LEADERSHIP_MEMBER

###########################################################################################
# files endpoint (files summary view)
###########################################################################################

files_dbattrs = 'id,fileid,filename,taskcompletion_id,mimetype'.split(',')
files_formfields = 'rowid,fileid,filename,taskcompletion_id,mimetype'.split(',')
files_dbmapping = dict(zip(files_dbattrs, files_formfields))
files_formmapping = dict(zip(files_formfields, files_dbattrs))

files = FilesCrud(
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Files,
                    local_interest_model = LocalInterest,
                    filesdirectory = lambda: current_app.config['APP_FILE_FOLDER'],
                    roles_accepted = [ROLE_SUPER_ADMIN],
                    template = 'datatables.jinja2',
                    pagename = 'files', 
                    endpoint = 'admin.files', 
                    endpointvalues={'interest': '<interest>'},
                    rule='/<interest>/files',
                    dbmapping = files_dbmapping,
                    formmapping = files_formmapping,
                    clientcolumns = [
                        { 'data': 'filename', 'name': 'filename', 'label': 'Filename',
                          },
                        { 'data': 'mimetype', 'name': 'mimetype', 'label': 'MIME type',
                          },
                        { 'data': 'fileid', 'name': 'fileid', 'label': 'File Id', '_unique': True,
                          },
                        { 'data': 'taskcompletion_id', 'name': 'taskcompletion_id', 'label': 'Task Completion ID',
                        },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons = ['remove'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
files.register()

###########################################################################################
# file endpoint (serves a single file)
###########################################################################################

class FileServer(DbCrudApiInterestsRolePermissions):
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        args = dict(
            app=bp,  # use blueprint instead of app
            db=db,
            model=Files,
            local_interest_model=LocalInterest,
            filesdirectory=lambda: current_app.config['APP_FILE_FOLDER'],
            roles_accepted=[ROLE_SUPER_ADMIN, ROLE_LEADERSHIP_ADMIN, ROLE_LEADERSHIP_MEMBER],
            endpoint='admin.file',
            endpointvalues={'interest': '<interest>'},
            rule='/<interest>/file/<fileid>',
            clientcolumns=[]
        )
        args.update(kwargs)

        # this initialization needs to be done before checking any self.xxx attributes
        super().__init__(**args)

    def get(self, fileid):
        # verify user can read the data, otherwise abort
        if not self.permission():
            self.rollback()
            self.abort()

        # get file information from table
        linterest = localinterest()
        file = Files.query.filter_by(fileid=fileid, interest=linterest).one_or_none()
        if not file:
            self.rollback()
            self.abort()

        # find path of file
        groupdir = join(self.filesdirectory(), g.interest)
        filepath = join(groupdir, fileid)

        if not exists(filepath):
            self.rollback()
            self.abort()

        return send_from_directory(groupdir, fileid,
                                   mimetype=file.mimetype,
                                   # as_attachment=True,
                                   attachment_filename=file.filename)

fileserver = FileServer()
fileserver.register()