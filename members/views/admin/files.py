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
from os import remove

# pypi
from flask import current_app

# homegrown
from . import bp
from ...model import db, Files, LocalInterest
from loutilities.user.tablefiles import FilesCrud
from loutilities.user.roles import ROLE_SUPER_ADMIN

###########################################################################################
# files endpoint
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

