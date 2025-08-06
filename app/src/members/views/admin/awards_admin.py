"""
awards - awards views
==========================================================
"""

# standard
from datetime import datetime, timedelta
from traceback import format_exception_only, format_exc
from itertools import zip_longest
from csv import DictWriter
from io import StringIO

# pypi
from flask import current_app, request, url_for, g, jsonify, abort, render_template, flash, Response
from flask.views import MethodView
from flask_security import current_user
from dominate.tags import select, option, button, input_, i
from loutilities.user.tables import DbCrudApiInterestsRolePermissions
from loutilities.user.roles import ROLE_SUPER_ADMIN, ROLE_AWARDS_ADMIN
from loutilities.timeu import asctime
from loutilities.filters import filtercontainerdiv, filterdiv
from loutilities.transform import Transform
from running.runsignup import RunSignUp

# home grown
from . import bp
from ...model import db
from ...model import LocalInterest, AwardsRace, AwardsEvent, AwardsDivision, AwardsAwardee
from ...version import __docversion__
from .viewhelpers import localinterest

awards_roles = [ROLE_SUPER_ADMIN, ROLE_AWARDS_ADMIN]
adminguide = 'https://members.readthedocs.io/en/{docversion}/organization-admin-guide.html'.format(
    docversion=__docversion__)

rsudt = asctime('%m/%d/%Y %H:%M')

awardraces_dbattrs = 'id,interest_id,name,rsu_race_id'.split(',')
awardraces_formfields = 'rowid,interest_id,name,rsu_race_id'.split(',')
awardraces_dbmapping = dict(zip(awardraces_dbattrs, awardraces_formfields))
awardraces_formmapping = dict(zip(awardraces_formfields, awardraces_dbattrs))

class AwardRaceView(DbCrudApiInterestsRolePermissions):
    def create_race(self, formdata):
        with RunSignUp(key=current_app.config['RSU_KEY'], secret=current_app.config['RSU_SECRET']) as rsu:
            race = rsu.getrace(formdata['rsu_race_id'])
            formdata['name'] = race['name']
            racerow = super().createrow(formdata)
        return racerow, race
        
    def get_race(self, thisid, formdata):
        with RunSignUp(key=current_app.config['RSU_KEY'], secret=current_app.config['RSU_SECRET']) as rsu:
            race = rsu.getrace(formdata['rsu_race_id'])
            racerow = super().updaterow(thisid, formdata)
        return racerow, race

    def update_divisions(self, race_id, race):
        # retrieve all events and divisions for this race
        stored_race = AwardsRace.query.filter_by(interest=localinterest(), id=race_id).one()
        stored_events = stored_race.events
        stored_events_d = {e.rsu_event_id: {'event': e} for e in stored_events}
        for stored_event in stored_events:
            stored_divisions = stored_event.divisions
            stored_events_d[stored_event.rsu_event_id]['divisions'] = {d.rsu_div_id: d for d in stored_divisions}

        with RunSignUp(key=current_app.config['RSU_KEY'], secret=current_app.config['RSU_SECRET']) as rsu:
            
            # add new events, skip any that are outside the awards window or have no divisions
            for event_id in race['events']:
                eventstart = rsudt.asc2dt(event_id['start_time'])
                if datetime.now() - eventstart > timedelta(days=current_app.config['AWARDS_WINDOW']):
                    continue
                
                rsu_race_id = race['race_id']
                rsu_event_id = event_id['event_id']
                
                # if no divisions, skip
                divisions = rsu.getracedivisions(rsu_race_id, rsu_event_id)
                if not divisions:
                    continue

                # create or update event
                eventname = event_id['name']
                eventdate = eventstart.date().isoformat()
                
                stored_event = stored_events_d.pop(rsu_event_id, None)
                eventrow = stored_event['event'] if stored_event else None

                if eventrow:
                    # update the existing event
                    eventrow.name = eventname
                    eventrow.date = eventdate
                else:
                    # create a new event
                    eventrow = AwardsEvent(
                        interest=localinterest(),
                        race_id=race_id,
                        rsu_event_id=rsu_event_id,
                        name=eventname,
                        date=eventdate,
                    )
                    db.session.add(eventrow)
                db.session.flush()
                
                # create or update divisions
                for division_id in divisions:
                    rsu_division_id = division_id['race_division_id']
                    priority = division_id['division_priority']
                    divname = division_id['division_name']
                    shortname = division_id['division_short_name']
                    num_awards = division_id['show_top_num']
                    min_age = division_id.get('auto_selection_criteria', {}).get('min_age', None)
                    max_age = division_id.get('auto_selection_criteria', {}).get('max_age', None)
                    gender = division_id.get('auto_selection_criteria', {}).get('gender', None)
                    
                    # create the division if it doesn't already exist
                    divisionrow = stored_event['divisions'].pop(rsu_division_id, None) if stored_event else None
                    
                    if divisionrow:
                        # update the existing division
                        divisionrow.priority = priority
                        divisionrow.name = divname
                        divisionrow.shortname = shortname
                        
                        # if number of awards for this division has been
                        # reduced, remove any awardees for new non-awards
                        if num_awards < divisionrow.num_awards:
                            for awardee in divisionrow.awardees:
                                if awardee.order > num_awards:
                                    awardee.active = False
                        divisionrow.num_awards = num_awards
                        
                        divisionrow.min_age = min_age
                        divisionrow.max_age = max_age
                        divisionrow.gender = gender
                    else:
                        # create a new division
                        divisionrow = AwardsDivision(
                            interest=localinterest(),
                            event=eventrow,
                            rsu_div_id=rsu_division_id,
                            priority=priority,
                            name=divname,
                            shortname=shortname,
                            num_awards=num_awards,
                            min_age=min_age,
                            max_age=max_age,
                            gender=gender,
                        )
                        db.session.add(divisionrow)
                    
                    # save changes
                    db.session.flush()
                    
                # delete any remaining divisions
                if stored_event:
                    for division_id in stored_event['divisions']:
                        current_app.logger.debug(f'deleting {stored_event['divisions'][division_id]}')
                        db.session.delete(stored_event['divisions'][division_id])

            # delete any remaining events
            for event_id in stored_events_d:
                current_app.logger.debug(f'deleting {stored_events_d[event_id]['event']}')
                db.session.delete(stored_events_d[event_id]['event'])
                
    def createrow(self, formdata):
        racerow, race = self.create_race(formdata)
        self.update_divisions(self.created_id, race)
        
        return racerow

    def updaterow(self, thisid, formdata):
        racerow, race = self.get_race(thisid, formdata)
        self.update_divisions(thisid, race)
        
        return racerow

awardraces_view = AwardRaceView(
    roles_accepted=awards_roles,
    app=bp,
    db=db,
    local_interest_model=LocalInterest,
    model=AwardsRace,
    template='datatables.jinja2',
    templateargs={'adminguide': adminguide},
    pagename='Award Races',
    endpoint='admin.awardraces',
    endpointvalues={'interest': '<interest>'},
    rule='/<interest>/awardraces',
    dbmapping=awardraces_dbmapping,
    formmapping=awardraces_formmapping,
    checkrequired=True,
    clientcolumns=[
        {'data': 'rsu_race_id', 'name': 'rsu_race_id', 'label': 'RSU Race ID', 'type': 'text', 
         '_unique': True,
         },
        {'data': 'name', 'name': 'name', 'label': 'Name', 'type': 'text',
         'type': 'hidden',  # only affects editor modal
         },
    ],
    servercolumns=None,  # not server side
    idSrc='rowid',
    buttons=lambda: [
        'create',
        {
            'extend': 'edit',
            'text': 'Update',
            'editor': {'eval':'editor'},
        },
        'remove', 
        'separator',
        {
            'extend': 'selected',
            'text': 'Awards',
            'action': {
                'eval': f'award_races_awards_button("{url_for('admin.raceawards', interest=g.interest)}")'
            }
        },

    ],
    dtoptions={
        'scrollCollapse': True,
        'scrollX': True,
        'scrollXInner': "100%",
        'scrollY': True,
    },
)
awardraces_view.register()


class RaceAwardsBase(MethodView):
    def __init__(self):
        self.roles_accepted = [ROLE_SUPER_ADMIN, ROLE_AWARDS_ADMIN]

    def permission(self):
        '''
        determine if current user is permitted to use the view
        '''
        # adapted from loutilities.tables.DbCrudApiRolePermissions
        allowed = False

        # must have race_id query arg
        race_id = request.args.get('race_id', False)
        if race_id:
            self.interest = localinterest()
            self.race = AwardsRace.query.filter_by(interest_id=self.interest.id, id=race_id).first()
            
            # race must be in the interest
            if self.race:
                for role in self.roles_accepted:
                    if current_user.has_role(role):
                        allowed = True
                        break

        return allowed

    
class RaceAwardsView(RaceAwardsBase):

    def get(self):
        try:
            # verify user can write the data, otherwise abort (adapted from loutilities.tables._editormethod)
            if not self.permission():
                db.session.rollback()
                cause = 'operation not permitted for user'
                return abort(403, cause)

            rows = AwardsEvent.query.filter_by(race_id=self.race.id).order_by(AwardsEvent.date.desc()).all()
            raceawards_filters = filtercontainerdiv()
            with raceawards_filters:
                with filterdiv('external-filter-event', 'Event'):
                    eventselect = select(id='events', style='width: 200px;')
                    with eventselect:
                        # select first option as selected
                        selected = False
                        for row in rows:
                            if not selected:
                                selected = True
                                option(f'{row.eventyear}', value=row.id, selected='true')
                            else: 
                                option(f'{row.eventyear}', value=row.id)
                
                with filterdiv('filter-bib-container', 'Bib'):
                    input_(type='text', id='bib-filter', placeholder='Bib number', style='width: 100px;')
                    i(cls='icon search-off', id='bib-search-off', title='Clear Bib Filter')
                
                button('CSV', id='awards-csv-button', url=url_for('admin._awardcsv', interest=g.interest))

            return render_template('raceawards.jinja2',
                                pagename=f'{self.race.name} Awards',
                                raceawards_filters=raceawards_filters.render(),
                                awards_poll_period=current_app.config['AWARDS_POLL_PERIOD'],
                                )
            
        except:
            # roll back database updates and close transaction
            db.session.rollback()
            raise

bp.add_url_rule('/<interest>/raceawards', view_func=RaceAwardsView.as_view('raceawards'), methods=['GET'])


class RaceAwardsApi(RaceAwardsBase):

    def update_event_awards(self, event):
        '''
        update the AwardsAwardee records for the event
        '''
        try:
            # get the results for this event from RunSignUp
            with RunSignUp(key=current_app.config['RSU_KEY'], secret=current_app.config['RSU_SECRET']) as rsu:
                # current_app.logger.debug(f'retrieving results for race {event.race.rsu_race_id} event {event.rsu_event_id}')
                rsu_results_headers = rsu.geteventresults(event.race.rsu_race_id, event.rsu_event_id, '')
                rsu_results = rsu_results_headers['results']
                rsu_headers = rsu_results_headers['headers']

            # get the divisions for this event, ordered by priority -- this assumes that the database is correct
            db_divisions = AwardsDivision.query.filter_by(event_id=event.id).order_by(AwardsDivision.priority).all()
            rsu_div_ids = [d.rsu_div_id for d in db_divisions]
            rsu_div_lookup = {d.rsu_div_id: d for d in db_divisions}
            
            # get the active awardees for the event from the database
            awardees = AwardsAwardee.query.filter_by(event_id=event.id, active=True).all()
            
            # create dictionaries of awardees for quick lookup
            award_placement = {(a.div.rsu_div_id, a.order): a for a in awardees}
            
            # loop through results from RunSignUp. Add AwardsAwardee for any awardees that are not in the database
            for result in rsu_results:
                awardee = None
                for rsu_div_id in rsu_div_ids:
                    div = rsu_div_lookup.get(rsu_div_id)

                    # check if the result deserves an award for this division
                    order = result[f'division-{rsu_div_id}-placement']
                    if order and order <= div.num_awards:          
                        name = f'{result['first_name']} {result['last_name']}'  # full name

                        # add result if the result is not already in the division results
                        if (rsu_div_id, order) not in award_placement:
                            current_app.logger.debug(f'new (div, place) ({div.shortname}, {order}) {name} result_id {result['result_id']}')
                            # create a new awardee
                            awardee = AwardsAwardee(
                                interest=localinterest(),
                                div=div,
                                event_id=event.id,
                                order=order,
                                active=True,
                                awardee_name=name,
                                awardee_bib=result['bib'],
                                picked_up=False,  # default to not picked up
                                rsu_result_id=result['result_id'],  # store the RunSignUp result ID
                            )
                            db.session.add(awardee)
                            db.session.flush()
                            award_placement[(rsu_div_id, order)] = awardee
                            
                            # we've awarded this result, so we can stop checking other divisions
                            break
                            
                        elif award_placement[(rsu_div_id, order)].rsu_result_id != result['result_id']:
                            current_app.logger.debug(f'updated result_id (div, place) ({div.shortname}, {order}) {name} result_id {award_placement[(rsu_div_id, order)].rsu_result_id} with {result['result_id']}')
                            
                            # if the awardee is already in the database and picked up, save the previous awardee
                            prev_awardee = award_placement[(rsu_div_id, order)]

                            # if the bib number didn't change, just update the rsu result id
                            if prev_awardee.awardee_bib == result['bib']:
                                current_app.logger.debug(f'updating (div, place) ({div.shortname}, {order}) {name} result_id {award_placement[(rsu_div_id, order)].rsu_result_id} with {result['result_id']}')
                                
                                # update result_id for existing record
                                prev_awardee.rsu_result_id = result['result_id']
                            
                            # if the bib number changed, create a new awardee and link to previous if it had been picked up
                            else:
                                picked_up = prev_awardee.picked_up
                                current_app.logger.debug(f'overwriting result (div, place) ({div.shortname}, {order}) {name} result_id {award_placement[(rsu_div_id, order)].rsu_result_id} with {result['result_id']} for '
                                                         f'{result['first_name']} {result['last_name']}: picked_up {picked_up} prev_awardee {prev_awardee}')
                                
                                prev_awardee.active = False
                                if not picked_up:
                                    prev_awardee = None
                                    
                                awardee = AwardsAwardee(
                                    interest=localinterest(),
                                    div=div,
                                    event_id=event.id,
                                    order=order,
                                    active=True,
                                    awardee_name=f'{result['first_name']} {result['last_name']}',  # full name
                                    awardee_bib=result['bib'],
                                    picked_up=False,
                                    rsu_result_id=result['result_id'],  # store the RunSignUp result ID
                                    prev_awardee=prev_awardee  # link to the previous awardee if the award had been picked up
                                )
                                db.session.add(awardee)
                                award_placement[(rsu_div_id, order)] = awardee

                            # flush whether we just updated the existing awardee or created a new one
                            db.session.flush()

                            # we've awarded this result, so we can stop checking other divisions
                            break
                                                    
            db.session.commit()
        
        except Exception as e:
            db.session.rollback()
            raise e
            cause = f'missing division for event {event.name}, use update from Race Awards view to correct'
            flash(cause, 'error')
            return cause
        
    def get(self):
        try:
            # verify user can write the data, otherwise abort (adapted from loutilities.tables._editormethod)
            if not self.permission():
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            event_id = request.args.get('event_id', None)
            if not event_id:
                # if no event_id, return
                return jsonify({'status': 'fail', 'error': 'event_id not specified'})
            
            need_divisions = request.args.get('need_divisions', 'false') == 'true'
            
            # get the event
            event = AwardsEvent.query.filter_by(interest_id=self.interest.id, id=event_id).first()
            if not event:
                # if no event, return
                return jsonify({'status': 'fail', 'error': 'event not found'})
            
            # retrieve divisions, awards for the displayed event
            awardsresp = {'awards': []}
            
            # this updates the AwardsAwardee records for the event
            error = self.update_event_awards(event)
            if error:
                # if there was an error, return it
                return jsonify({'status': 'fail', 'error': error})
            
            # return the current state to the client
            # this will include all the divisions and awards for the event
            divisions = (AwardsDivision.query.filter_by(event_id=event.id)
                            .order_by(AwardsDivision.priority).all())
            gendivisions = {}
            for division in divisions:
                # only generate the divisions data if needed
                if need_divisions:
                    gendivisions.setdefault(division.gender, [])
                    gendivisions[division.gender].append({
                        'div_id': division.id,
                        'rsu_div_id': division.rsu_div_id,
                        'name': division.name,
                        'shname': division.shortname,
                        'prio': division.priority,
                        'num_awards': division.num_awards,
                        'gen': division.gender,
                        'min': division.min_age,
                        'max': division.max_age,
                    })
                
                awards = AwardsAwardee.query.filter_by(div=division, active=True).order_by(AwardsAwardee.order).all()
                for award in awards:
                    awardsresp['awards'].append({
                        'awardee_id': award.id,
                        'div_id': division.id,
                        'rsu_div_id': division.rsu_div_id,
                        'place': award.order,
                        'name': award.awardee_name,
                        'bib': award.awardee_bib,
                        'picked_up': award.picked_up,
                        'prev_picked_up': award.prev_awardee.picked_up if not award.picked_up and award.prev_awardee else False,
                        'notes': award.notes,
                    })

            # if asked, return a list of division rows for the table to be built
            if need_divisions:
                awardsresp['divisions'] = list(zip_longest(*[gendivisions[g] for g in gendivisions.keys()]))
            
            # commit database updates and close transaction, then return the result
            db.session.commit()
            return jsonify({'status': 'success', 'data': awardsresp})
        
        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status' : 'fail', 'error': 'exception occurred:<br>{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

bp.add_url_rule('/<interest>/_raceawards/rest', view_func=RaceAwardsApi.as_view('_raceawards'),
                methods=['GET'])


class AwardPickUpApi(RaceAwardsBase):
    def permission(self):
        permission = super().permission()
        if permission:
            event_id = request.args.get('event_id', None)
            self.event = AwardsEvent.query.filter_by(interest=self.interest, id=event_id).first()
            if not self.event: return False
        
        return permission
            
    def post(self):
        if not self.permission():
            return jsonify({'status': 'fail', 'error': 'not permitted'})
        
        awardee_id = request.args.get('awardee_id', None)
        awardee = AwardsAwardee.query.filter_by(interest=self.interest, id=awardee_id).first()
        was_picked_up = request.args.get('was_picked_up', 'false') == 'true'
        if awardee:
            if not was_picked_up:
                awardee.picked_up = True
                retdata = jsonify({'status': 'success', 'picked_up': True, 'prev_picked_up': False})
            else:
                awardee.picked_up = False
                retdata = jsonify({'status': 'success', 'picked_up': False, 'prev_picked_up': True if awardee.prev_awardee else False})
        
            db.session.commit()
            
        # no awardee, indicate not picked up
        else:
            retdata = jsonify({'status': 'success', 'picked_up': False})
        
        db.session.commit()
        return retdata
        
bp.add_url_rule('/<interest>/_awardpickedup/rest', view_func=AwardPickUpApi.as_view('_awardpickedup'),
                methods=['POST'])

class AwardNotesApi(RaceAwardsBase):
    def permission(self):
        permission = super().permission()
        if permission:
            event_id = request.args.get('event_id', None)
            self.event = AwardsEvent.query.filter_by(interest=self.interest, id=event_id).first()
            if not self.event: return False
        
        return permission
    
    def get(self):
        if not self.permission():
            return jsonify({'status': 'fail', 'error': 'not permitted'})
        
        awardee_id = request.args.get('awardee_id', None)
        awardee = AwardsAwardee.query.filter_by(interest=self.interest, id=awardee_id).first()
        
        if awardee:
            return jsonify({'status': 'success', 'notes': awardee.notes if awardee.notes else ''})
        
        # no awardee, logic error
        else:
            return jsonify({'status': 'error', 'error': 'no awardee'})
    
    def post(self):
        if not self.permission():
            return jsonify({'status': 'fail', 'error': 'not permitted'})
        
        awardee_id = request.args.get('awardee_id', None)
        awardee = AwardsAwardee.query.filter_by(interest=self.interest, id=awardee_id).first()
        notes = request.args.get('notes', '')
        if awardee:
            awardee.notes = notes
            retdata = jsonify({'status': 'success', 'notes': notes})
        
            db.session.commit()
            
        # no awardee, logic error
        else:
            retdata = jsonify({'status': 'error', 'error': 'no awardee'})
        
        db.session.commit()
        return retdata
        
bp.add_url_rule('/<interest>/_awardnotes/rest', view_func=AwardNotesApi.as_view('_awardnotes'),
                methods=['GET', 'POST'])


class AwardCsvApi(RaceAwardsBase):
    def permission(self):
        permission = super().permission()
        if permission:
            event_id = request.args.get('event_id', None)
            self.event = AwardsEvent.query.filter_by(interest=self.interest, id=event_id).first()
            if not self.event: return False
        
        return permission
    
    def get(self):
        if not self.permission():
            return jsonify({'status': 'fail', 'error': 'not permitted'})
        
        awardees = AwardsAwardee.query.filter_by(interest=self.interest, event_id=self.event.id).all()
        filename = f'{self.event.date}-{self.event.race.name}-{self.event.name}-awards.csv'
        
        fieldnames = 'name,bib,division,place,status,notes,updated'.split(',')
        si = StringIO()
        cw = DictWriter(si, fieldnames)
        cw.writeheader()
        
        db2csv = Transform(
            sourceattr=True, targetattr=False,
            mapping={
                'name': 'awardee_name',
                'bib':  'awardee_bib',
                'division': lambda r: r.div.shortname,
                'place': 'order',
                'status': lambda r: ('picked up' if r.picked_up and r.active 
                                     else 'distribution error' if r.picked_up and not r.active
                                     else 'pending pickup' if r.active
                                     else 'withdrawn'),
                'notes': 'notes',
                'updated': lambda r: r.update_time.isoformat(sep=' ') if r.update_time else '',
            })
        
        for awardee in awardees:
            csvrow = {}
            db2csv.transform(awardee, csvrow)
            cw.writerow(csvrow)
        
        output = si.getvalue()
        response = Response(output, mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response
        
bp.add_url_rule('/<interest>/_awardcsv', view_func=AwardCsvApi.as_view('_awardcsv'),
                methods=['GET'])

