'''
organization_frontend - views handling organization data
===========================================================================
'''

# standard
from datetime import date
from flask import g

# pypi
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.user.model import Interest

# homegrown
from . import bp
from ...helpers import member_qualifiers_active, memberqualifierstr, localinterest
from ...model import db
from ...model import LocalInterest, Position

##########################################################################################
# positions endpoint
##########################################################################################

def position_members(position):
    ondate = date.today()
    names = [memberqualifierstr(m) for m in member_qualifiers_active(position, ondate)]
    names.sort()
    return ', '.join(names)

position_dbattrs = 'id,interest_id,position,__readonly__'.split(',')
position_formfields = 'rowid,interest_id,position,users'.split(',')
position_dbmapping = dict(zip(position_dbattrs, position_formfields))
position_formmapping = dict(zip(position_formfields, position_dbattrs))
position_formmapping['users'] = position_members

class PositionsView(DbCrudApiInterestsRolePermissions):
    decorators = [] # remove auth_required()
    
    def permission(self):
        self.interest = Interest.query.filter_by(interest=g.interest).one_or_none()
        if not self.interest:
            return False
        return True
    
    def beforequery(self):
        super().beforequery()
        
        # filter to only the positions which have the indicated tags
        thesepositions = []
        for tag in localinterest().interestpublicpositionstags:
            thesepositions += [p for p in tag.positions if p not in thesepositions]
        self.queryfilters = [Position.id.in_([pos.id for pos in thesepositions])]
        
position_view = PositionsView(
    local_interest_model = LocalInterest,
    app = bp,   # use blueprint instead of app
    db = db,
    model = Position,
    template = 'datatables.jinja2',
    pagename = 'Positions',
    endpoint = 'frontend.positions',
    endpointvalues={'interest': '<interest>'},
    rule = '/<interest>/positions',
    dbmapping = position_dbmapping,
    formmapping = position_formmapping,
    checkrequired = True,
    clientcolumns = [
        {'data': 'position', 'name': 'position', 'label': 'Position'},
        {'data': 'users', 'name': 'users', 'label': 'Names'},
    ],
    servercolumns = None,  # not server side
    idSrc = 'rowid',
    buttons = [],
    dtoptions = {
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
position_view.register()
