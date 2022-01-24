# standard
from datetime import datetime
from traceback import format_exception_only, format_exc
from json import dumps
from urllib.parse import urlencode
from collections import OrderedDict
from traceback import format_exc, format_tb
from sys import exc_info
from html import escape

# pypi
from flask import request, render_template, jsonify, current_app, url_for, g
from flask.views import MethodView
from loutilities.user.model import Interest
from loutilities.tables import DteFormValidate, TimeOptHoursConverter
from loutilities.flask_helpers.mailer import sendmail
from loutilities.timeu import age, asctime
import requests
from dominate.tags import div, p, table, tbody, tr, td, br
from dominate.util import text
from formencode.schema import Schema
from formencode.validators import ByteString, Email, DateConverter, Number, OneOf, FancyValidator, NotEmpty

# homegrown
from ...model import RacingTeamResult, RacingTeamVolunteer, db, LocalInterest, RacingTeamInfo, localinterest_query_params
from ...model import RacingTeamConfig, RacingTeamMember
from ...helpers import localinterest

from . import bp

isodate = asctime('%Y-%m-%d')

class ParameterError(Exception): pass

class InfoCommonValidator(Schema):
    common_name = ByteString(not_empty=True)
    common_eventname = ByteString(not_empty=True)
    common_eventdate = DateConverter(month_style='iso')
    common_infotype = OneOf(['raceresult', 'volunteer'])

class InfoRaceResultValidator(Schema):
    common_eventdate = DateConverter(month_style='iso')
    raceresult_distance = Number(min=0, max=200)
    raceresult_units = OneOf(['miles', 'km'])
    raceresult_time = TimeOptHoursConverter()

class InfoVolunteerValidator(Schema):
    common_eventdate = DateConverter(month_style='iso')
    volunteer_hours = Number(min=0, max=200)
    volunteer_comments = NotEmpty()
    
class InfoValidator(FancyValidator):
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        
    def _convert_to_python(self, value, state):
        civ = InfoCommonValidator(**self.kwargs)
        py = civ._convert_to_python(value, state)
        if value['common_infotype'] == 'raceresult':
            rrv = InfoRaceResultValidator(**self.kwargs)
            addlpy = rrv._convert_to_python(value, state)
            py.update(addlpy)
        else:
            vv = InfoVolunteerValidator(**self.kwargs)
            addlpy = vv._convert_to_python(value, state)
            py.update(addlpy)
        return py

class RacingTeamInfoView(MethodView):

    def get(self):
        config = RacingTeamConfig.query.filter_by(**localinterest_query_params()).one_or_none()
        if not config:
            raise ParameterError(f'racing team configuration needs to be created for interest \'{g.interest}\'')

        configdict = {}
        for field in ['openbehavior']:
            configdict[field] = getattr(config, field)
        configdict['agegenderapi'] = url_for('frontend._rt_getagegender', interest=g.interest)
        configdict['agegradeapi'] = url_for('frontend._rt_getagegrade', interest=g.interest)
        
        namesdb = RacingTeamMember.query.filter_by(active=True, **localinterest_query_params()).all()
        names = [n.name for n in namesdb]

        return render_template('racing-info.jinja2', config=configdict, names=names, assets_js='frontendmaterialize_js', assets_css= 'frontendmaterialize_css')

    def post(self):
        try:
            val = DteFormValidate(InfoValidator(allow_extra_fields=True))
            results = val.validate(request.form)
            if results['results']:
                raise ParameterError(results['results'])
            
            formdata = results['python']
            name = formdata['common_name']
            member = RacingTeamMember.query.filter_by(name=name, active=True, **localinterest_query_params()).one()
            config = RacingTeamConfig.query.filter_by(**localinterest_query_params()).one_or_none()
            interest = Interest.query.filter_by(interest=g.interest).one()
            if not config:
                raise ParameterError('interest configuration needs to be created')
            
            # we're logging this now
            logtime = datetime.now()
            inforec = RacingTeamInfo(interest=localinterest(), member=member, logtime=logtime)
            db.session.add(inforec)

            # race result information
            if formdata['common_infotype'] == 'raceresult':
                mailfields = OrderedDict([
                    ('common_name', 'Name'),
                    ('common_eventname', 'Event Name'),
                    ('common_eventdate', 'Event Date'),
                    ('common_infotype', 'Submission Type'),
                    ('raceresult_distance', 'Distance'),
                    ('raceresult_units', ''),
                    ('raceresult_time', 'Official Time (hh:mm:ss)'),
                    ('raceresult_age', 'Age (Race Date)'),
                    ('raceresult_agegrade', 'Age Grade'),
                    ('raceresult_awards', 'Awards'),
                ])
                
                resultfields = {
                    'common_eventname': 'eventname',
                    'raceresult_distance': 'distance',
                    'raceresult_units': 'units',
                    'raceresult_time': 'time',
                    'raceresult_age': 'age',
                    'raceresult_agegrade': 'agegrade',
                    'raceresult_awards': 'awards',
                }

                resultsrec = RacingTeamResult(interest=localinterest())
                for field in resultfields:
                    setattr(resultsrec, resultfields[field], request.form[field])
                # use conversion to datetime
                resultsrec.eventdate = formdata['common_eventdate']
                resultsrec.info = inforec
                db.session.add(resultsrec)
            
            else:
                mailfields = OrderedDict([
                    ('common_name', 'Name'),
                    ('common_eventname', 'Event Name'),
                    ('common_eventdate', 'Event Date'),
                    ('common_infotype', 'Submission Type'),
                    ('volunteer_hours', 'How Many Hours'),
                    ('volunteer_comments', 'Comments'),
                ])
            
                resultfields = {
                    'common_eventname': 'eventname',
                    'volunteer_hours': 'hours',
                    'volunteer_comments': 'comment',
                }
                
                volunteerrec = RacingTeamVolunteer(interest=localinterest())
                for field in resultfields:
                    setattr(volunteerrec, resultfields[field], request.form[field])
                # use conversion to datetime
                volunteerrec.eventdate = formdata['common_eventdate']
                volunteerrec.info = inforec
                db.session.add(volunteerrec)
            
            # commit database changes
            db.session.commit()
                
            # send confirmation email
            subject = "[racing-team-info] New racing team information from {}".format(name)
            body = div()
            with body:
                p('The following information for the racing team was submitted. If this is correct, '
                f'no action is required. If you have any changes, please contact {config.fromemail}')
                with table(), tbody():
                    for field in mailfields:
                        with tr():
                            td(mailfields[field])
                            td(request.form[field])
                with p():
                    text(f'Racing Team - {config.fromemail}')
                    br()
                    text(f'{interest.description}')

            html = body.render()
            tolist = member.email
            fromlist = config.fromemail
            cclist = config.infoccemail
            sendmail(subject, fromlist, tolist, html, ccaddr=cclist)
                
            return jsonify({'status': 'OK'})

        except Exception as e:
            db.session.rollback()
            exc_type, exc_value, exc_traceback = exc_info()
            current_app.logger.error(''.join(format_tb(exc_traceback)))
            error = format_exc()
            return jsonify({'status': 'error', 'error': escape(repr(e))})

bp.add_url_rule('<interest>/racingteaminfo', view_func=RacingTeamInfoView.as_view('racingteaminfo'),
                methods=['GET', 'POST'])

class RacingTeamAgeGenderApi(MethodView):
    def get(self):
        try:
            name = request.args['name']
            member = RacingTeamMember.query.filter_by(name=name, **localinterest_query_params()).one()
            racedatedt = isodate.asc2dt(request.args['racedate'])
            memberage = age(racedatedt, member.dateofbirth)
            return jsonify(status='success', age=memberage, gender=member.gender)

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status' : 'fail', 'error': 'exception occurred:\n{}'.format(exc)}
            current_app.logger.error(format_exc())
            return jsonify(output_result)

bp.add_url_rule('/<interest>/_rt_getagegender', view_func=RacingTeamAgeGenderApi.as_view('_rt_getagegender'),
                methods=['GET'])

class RacingTeamAgeGradeApi(MethodView):
    def get(self):
        try:
            name = request.args['name']
            member = RacingTeamMember.query.filter_by(name=name, **localinterest_query_params()).one()
            racedatedt = isodate.asc2dt(request.args['racedate'])
            memberage = age(racedatedt, member.dateofbirth)
            dist = request.args['dist']
            units = request.args['units']
            time = request.args['time']
            member = RacingTeamMember.query.filter_by(name=name, **localinterest_query_params()).one()
            # return jsonify(status='success', age=member.age, gender=member.gender)

            # convert marathon and half marathon to exact miles
            if (dist == 26.2 and units == 'miles') or (dist == 42.2 and units == 'km'):
                dist = 26.2188
            
            elif (dist == 13.1 and units == 'miles') or (dist == 21.1 and units == 'km'):
                dist = 13.1094
            
            # convert dist to miles
            elif units == 'km':
                dist = float(dist) / 1.609344

            # convert parameters to query string
            theparams = {
                'age'      : memberage,
                'gender'   : member.gender,
                'distance' : dist,
                'time'     : time,
            }
            
            # get age grade data
            response = requests.get(f'https://scoretility.com/_agegrade?{urlencode(theparams)}');
            if response.status_code == 200:
                # no need to jsonify() the text, as scoretility already did that
                return response.text;

            else:
                # need ERROR, to emulate error string from scoretility
                return jsonify(status='fail', errorfield='server response', errordetail='ERROR,bad response from agegrade fetch')

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status' : 'fail', 'error': 'exception occurred:\n{}'.format(exc)}
            current_app.logger.error(format_exc())
            return jsonify(output_result)

bp.add_url_rule('/<interest>/_rt_getagegrade', view_func=RacingTeamAgeGradeApi.as_view('_rt_getagegrade'),
                methods=['GET'])
