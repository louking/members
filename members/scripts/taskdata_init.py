'''
taskdata_init - command line database initialization - initialize test data
=========================================================================================
run from 3 levels up, like python -m members.scripts.scripts.taskdata_init

'''
# standard
from os.path import join, dirname
from datetime import timedelta, date, datetime
from argparse import ArgumentParser

# pypi
from flask import url_for
from sqlalchemy.orm import aliased

# homegrown
from loutilities.transform import Transform
from members import create_app
from members.settings import Development
from members.model import db
from members.applogging import setlogging
from members.model import update_local_tables
from members.model import LocalUser, LocalInterest, Task, TaskGroup, TaskField, TaskTaskField, Position
from members.model import input_type_all, gen_fieldname, FIELDNAME_ARG
from members.model import INPUT_TYPE_UPLOAD, INPUT_TYPE_DATE, INPUT_TYPE_DISPLAY, INPUT_TYPE_TEXT, INPUT_TYPE_TEXTAREA
from members.model import NEED_REQUIRED, NEED_ONE_OF, NEED_OPTIONAL
from loutilities.user.model import User, Interest

class parameterError(Exception): pass

def main():
    parser = ArgumentParser()
    parser.add_argument('--noclear', default=False, action='store_const', const=True, help='use --nomembers to skip members')
    args = parser.parse_args()

    scriptdir = dirname(__file__)
    # two levels up
    scriptfolder = dirname(dirname(scriptdir))
    configdir = join(scriptfolder, 'config')
    memberconfigfile = "members.cfg"
    memberconfigpath = join(configdir, memberconfigfile)
    userconfigfile = "users.cfg"
    userconfigpath = join(configdir, userconfigfile)

    # create app and get configuration
    # use this order so members.cfg overrrides users.cfg
    configfiles = [userconfigpath, memberconfigpath]
    app = create_app(Development(configfiles), configfiles)

    # set up database
    db.init_app(app)

    # set up scoped session
    with app.app_context():
        # turn on logging
        setlogging()

        # clear and initialize the members database
        # bind=None per https://flask-sqlalchemy.palletsprojects.com/en/2.x/binds/
        if not args.noclear:
            db.drop_all(bind=None)
            db.create_all(bind=None)

            update_local_tables()

        testuser = User.query.filter_by(email='lou.king@steeplechasers.org').one()
        fsrcinterest = Interest.query.filter_by(interest='fsrc').one()
        localfsrcinterest = LocalInterest.query.filter_by(interest_id=fsrcinterest.id).one()
        localtestuser = LocalUser.query.filter_by(user_id=testuser.id, interest_id=localfsrcinterest.id).one()
        localfsrcinterest.initial_expiration = date(2020, 4, 1)
        localfsrcinterest.from_email = "volunteer@steeplechasers.org"

        taskgroups = [
            {'taskgroup': 'Board Meeting Attendee', 'description': 'People who attend board meeting'},
            {'taskgroup': 'Nomination Process', 'description': 'Tasks about nominating officers and directors'},
            {'taskgroup': 'Executive Officer', 'description': 'President, Vice President, Treasurer, Secretary',
             'taskgroups': ['Board Meeting Attendee', 'Nomination Process'],
             },
            {'taskgroup': 'Board of Directors', 'description': 'Board of Directors',
             'taskgroups': ['Board Meeting Attendee', 'Nomination Process'],
             },
            {'taskgroup': 'Training', 'description': 'Tasks for training group'},
            {'taskgroup': 'Youth Training', 'description': 'Tasks for youth trainers'},
            {'taskgroup': 'Signature Race Director', 'description': 'Tasks about signature races',
             'taskgroups': ['Board Meeting Attendee'],
             },
            {'taskgroup': 'Low Key Race Director', 'description': 'Tasks about low key races'},
            {'taskgroup': 'Memorial Scholarship', 'description': 'Tasks about Memorial Scholarship'},
            {'taskgroup': 'President', 'description': 'Tasks just for the president'},
            {'taskgroup': 'Finances', 'description': 'Tasks for Treasurer / Finance Committee'},
            {'taskgroup': 'Races', 'description': 'Tasks for Races Committee'},
            {'taskgroup': 'Bank Account Full Access', 'description': 'Task for those who have full access to bank account'},
            {'taskgroup': 'General Committee Leadership', 'description': 'Committee lead tasks',
             'taskgroups': ['Board Meeting Attendee'],
             },
            {'taskgroup': 'Technology Committee Leadership', 'description': 'Committee lead tasks',
             'taskgroups': ['Board Meeting Attendee', 'General Committee Leadership'],
             },
            {'taskgroup': 'Communications Committee Leadership', 'description': 'Committee lead tasks',
             'taskgroups': ['Board Meeting Attendee', 'General Committee Leadership'],
             },
            {'taskgroup': 'Membership Committee Leadership', 'description': 'Committee lead tasks',
             'taskgroups': ['Board Meeting Attendee', 'General Committee Leadership'],
             },
        ]

        for taskgroup in taskgroups:
            subgroups = taskgroup.pop('taskgroups', [])
            tgp = TaskGroup(interest=localfsrcinterest, **taskgroup)
            taskgroup['TaskGroup'] = tgp
            db.session.add(tgp)
            # need to flush each one so we find subgroups
            db.session.flush()
            tgp = TaskGroup.query.filter_by(taskgroup=taskgroup['taskgroup']).one()
            for subgroup in subgroups:
                thissubgroup = TaskGroup.query.filter_by(taskgroup=subgroup).one()
                tgp.taskgroups.append(thissubgroup)

        ssuploadfield = gen_fieldname()
        sscompdatefield = gen_fieldname()
        # ref https://docs.google.com/document/d/1dQcnj-eqwMA9j9k5UuYMlT_3-pImvQxpyPgUIJX9rvo/edit
        coifieldtype = ['a-output', 'a-input', 'b-output', 'b-input', 'c-input-output']
        coifieldnames = [gen_fieldname() for i in range(5)]
        coifieldneeds = [NEED_OPTIONAL, NEED_ONE_OF, NEED_OPTIONAL, NEED_ONE_OF, NEED_REQUIRED]
        coifield = dict(zip(coifieldtype, coifieldnames))
        coifieldneed = dict(zip(coifieldtype, coifieldneeds))
        coitaskfields = {}
        taskfields = [
            # safe sport
            {
                'taskfield': 'Safe Sport Completion Date',
                'fieldname': sscompdatefield, 'inputtype':INPUT_TYPE_DATE, 'priority':1, 'displaylabel': 'Safe Sport Completion Date',
                'override_completion': True
            },
            {
                'taskfield': 'Safe Sport Upload',
                'fieldname': ssuploadfield, 'inputtype': INPUT_TYPE_UPLOAD, 'priority':2,
                'displaylabel':'Upload Safe Sport Certificate',
                'uploadurl':url_for('admin.fieldupload', interest='fsrc') + '?{}={}'.format(FIELDNAME_ARG, ssuploadfield)},

            # conflict of interest
            {
                'taskfield': 'COI Display No Conflict',
                'fieldname': coifield['a-output'], 'inputtype': INPUT_TYPE_DISPLAY, 'priority': 1, 'displaylabel': 'If no conflicts',
                'displayvalue': 'I am not aware of any relationship or interest or situation involving my family or myself '
                            'which might result in, or give the appearance of being, a conflict of interest between such '
                            'family member or me on one hand and the Frederick Steeplechasers Running Club on the other. '},
            {
                'taskfield': 'COI Input No Conflict',
                'fieldname': coifield['a-input'], 'inputtype': INPUT_TYPE_TEXT, 'priority': 2, 'displaylabel': 'Your initials'
            },
            {
                'taskfield': 'COI Display Conflict',
                'fieldname': coifield['b-output'], 'inputtype': INPUT_TYPE_DISPLAY, 'priority': 3, 'displaylabel': 'If conflicts',
                'displayvalue': 'The following are relationships, interests, or situations involving me or a member of my '
                             'family which I consider might result in or appear to be an actual, apparent or potential '
                             'conflict of interest between such family members or myself on one hand and the Frederick '
                             'Steeplechasers Running Club on the other. '
                             '<ul>'
                             '<li>For-profit corporate directorships, positions, and employment with (list)</li>'
                             '<li>Nonprofit trusteeships of positions: Memberships in the following organizations (list)</li>'
                             '<li>Contracts, business activities, and investments with or in the following organizations (list)</li>'
                             '<li>Other relationships and activities (list)</li>'
                             '</ul>'
             },

            {
                'taskfield': 'COI Input Conflict',
                'fieldname': coifield['b-input'], 'inputtype': INPUT_TYPE_TEXTAREA, 'priority': 4, 'displaylabel': ''
            },
            {
                'taskfield': 'COI Input Occupation',
                'fieldname': coifield['c-input-output'], 'inputtype': INPUT_TYPE_TEXT, 'priority': 5,
                'displaylabel': 'My primary business or occupation at this time is'
            },
        ]
        for taskfield in taskfields:
            thisfield = TaskField(interest=localfsrcinterest, **taskfield)
            db.session.add(thisfield)
            coitaskfields[taskfield['fieldname']] = thisfield
        db.session.flush()

        tasks = [
            {'task': 'Executive Officer Job Description', 'priority':2, 'period':timedelta(104*7),
             'isoptional':False,
             'expirysoon': timedelta(2*7),
             'description':'Review [Executive Officer Job Description](https://docs.google.com/document/d/14yW5nK_mc9jiutPmniMmzDjLncjxlD7xA7tRruO43MY/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Executive Officer')
             ],
             },
            {'task': 'Board of Directors Job Description', 'priority':2, 'period':timedelta(104*7),
             'isoptional':False,
             'expirysoon': timedelta(2*7),
             'description':'Review [Board of Directors Job Description](https://docs.google.com/document/d/1rps35T5Z5YHKpI_80ZX7CFKaW7TPhuZYBFckCTSNnho/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board of Directors')
             ],
             },
            {'task': 'Board Orientation and Operation', 'priority': 1, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2*7),
             'description': 'Review [FSRC Board Orientation and Operation](https://docs.google.com/document/d/1mwz3zpjv2kjk_LukT2KTtEslk3pWujyAU50yrEvIc1M/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee')
             ],
             },
            {'task': 'Articles of Incorporation', 'priority': 5,
             'isoptional': False,
             'description': 'Review [Articles of Incorporation](https://drive.google.com/open?id=1iMc-qq2mlXQKsilZfXgQFqHfAET227Vj)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee')
             ],
             },
            {'task': 'Constitution / Bylaws', 'priority': 5, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2*7),
             'description': 'Review [FSRC Constitution / Bylaws](https://drive.google.com/open?id=1bxULc_jEuzUUSxfDWYIOtAvpnA0LXq7O8kkcybCBEQ0)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee')
             ],
             },
            {'task': 'Conflict of Interest Policy', 'priority': 2, 'period': timedelta(52 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2*7),
             'description': 'Review [Conflict of Interest Policy](https://docs.google.com/document/d/1dQcnj-eqwMA9j9k5UuYMlT_3-pImvQxpyPgUIJX9rvo/edit?usp=sharing)',
             'fields': [coifieldneed[ft] + '/' + coifield[ft] for ft in coifieldtype],
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee')
             ],
             },
            {'task': 'Board Meeting Procedures', 'priority': 1, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Review [Board Meeting Procedures](https://drive.google.com/open?id=1k1eDwEa641Rdd6fRZcRv4bkMJXfXWtWAoyiyw9jtZc0)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee')
             ],
             },
            {'task': 'Code of Conduct Policy', 'priority': 2, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Review [Code of Conduct Policy](https://docs.google.com/document/d/11MuwstPD1X_8ivuR4TV6qrpXAfUPHoGNnTqlMVHlFoA/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee')
             ],
             },
            {'task': 'Social Media Policy', 'priority': 2, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Review [Social Media Policy - Leadership Team](https://docs.google.com/document/d/1_sZYz8SLtepLlAT7V9laD0lGcUckXnslMrm9xlaR0_I/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee')
             ],
             },
            {'task': 'Executive Board Nomination Process', 'priority': 5, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Review [Executive Board Nomination Process](https://docs.google.com/document/d/110KryUEX_77Fj24QJHk9BEbGXAgcPdEIsba8Izwz-AE/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Nomination Process')
             ],
             },
            {'task': 'Safe Sport Policy', 'priority': 3, 'period': timedelta(52 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Review [Safe Sport Policy](https://docs.google.com/document/d/1I9TGaf5FmSZsqIWlguZOXyWsVkAU7Q3kXZ_WijBRkH8/edit?usp=sharing)',
              'taskgroups': [
                  next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Training')
              ],
              },
            {'task': 'Safe Sport Training', 'priority': 4, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2*7),
             'description': 'Complete Safe Sport Training',
             'fields': [
                 NEED_REQUIRED + '/' + sscompdatefield,
                 NEED_REQUIRED + '/' + ssuploadfield,
             ],
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Training')
             ],
             },
            {'task': 'Training Programs - Youth Participation Policy', 'priority': 5, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Review [Training Programs - Youth Participation Policy](https://docs.google.com/document/d/1jjDoqAkfKxFfTN16uMW2-J1ptW8o7DflocloFjjpm0A/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Training')
             ],
             },
            {'task': 'RRCA Coach Certification', 'priority': 6,
             'isoptional': True,
             'description': 'Take RRCA Coach Certification Course',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Training')
             ],
             },
            {'task': 'First Aid Training', 'priority': 6,
             'isoptional': True,
             'description': 'Take First Aid Training (required by RRCA every two years for RRCA Certified Coachesee',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Training')
             ],
             },
            {'task': 'Background Check', 'priority': 2, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Apply for background check. '
                            'For instructions see [NCSI Self Registration Letter](https://drive.google.com/file/d/0B8Zxg7taJn4FR2RVc2ZiQ2tmeVhiNlRCT01IUnVoRHRhVWIw/view?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Youth Training'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Bank Account Full Access'),
             ],
             },
            {'task': 'Race Revenue Proposal', 'priority': 3, 'dateofyear': '11-01', 'expirystarts': timedelta(13*3*7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'Produce Race Revenue Proposal based on '
                            '[FSRC Event Revenue Policy](https://docs.google.com/document/d/1K-x_xY1b2nWS8qZ2fljauJl_Plbb0qK2ANjy-43cEU8/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Signature Race Director')
             ],
             },
            {'task': 'Race Policy', 'priority': 3, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Review '
                            '[FSRC Race Policy](https://docs.google.com/document/d/1UxT1Z9sjcKJyFjgLpfDtkSHQ-lzIam0t5lbxcBAjYGo/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Signature Race Director'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Low Key Race Director'),
             ],
             },
            {'task': 'Severe Weather Cancellation Policy', 'priority': 3, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Review '
                            '[Severe Weather Cancellation Policy](https://docs.google.com/document/d/1s14YePWI6chccrTtibyBokyigaG-yAx__jpcni611Bk/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Signature Race Director'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Low Key Race Director'),
             ],
             },
            {'task': 'RRCA Race Director Certification', 'priority': 3,
             'isoptional': True,
             'description': 'Take RRCA Race Director Certification course',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Signature Race Director'),
             ],
             },
            {'task': 'Memorial Scholarship Policy', 'priority': 3, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Review '
                            '[FSRC Memorial Scholarship Policy](https://docs.google.com/document/d/1aF-m32Y6x3Nl0AQZWCgsnv2cw25JTLiBb9fzOZ-oK44/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Memorial Scholarship'),
             ],
             },
            {'task': 'Annual Report', 'priority': 3, 'dateofyear': '05-01',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'Issue Annual Report for review',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'President')
             ],
             },
            {'task': 'Q1 President\'s Message', 'priority': 3, 'dateofyear': '03-01',
             'expirystarts': timedelta(13 * 2 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Write Q1 President\'s Message for Intervals Blog',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'President')
             ],
             },
            {'task': 'Q2 President\'s Message', 'priority': 3, 'dateofyear': '06-01',
             'expirystarts': timedelta(13 * 2 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Write Q2 President\'s Message for Intervals Blog',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'President')
             ],
             },
            {'task': 'Q3 President\'s Message', 'priority': 3, 'dateofyear': '09-01',
             'expirystarts': timedelta(13 * 2 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Write Q3 President\'s Message for Intervals Blog',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'President')
             ],
             },
            {'task': 'Q4 President\'s Message', 'priority': 3, 'dateofyear': '12-01',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'Write Q4 President\'s Message for Intervals Blog',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'President')
             ],
             },

            {'task': 'Financial Policies', 'priority': 3, 'period': timedelta(104*7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Review '
                            '[Financial Policies](https://docs.google.com/document/d/1Aa8NCSj20Pb9FgLJB2Q82m9_SLlAc3qBYiFY9sGUzz0/edit)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Finances')
             ],
             },
            {'task': 'Sales Tax Exemption', 'priority': 3, 'period': timedelta(104*7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Renew sales tax exemption',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Finances')
             ],
             },
            {'task': 'Annual Budget', 'priority': 3, 'dateofyear': '02-01',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'Manage and develop the proposed annual budget',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Finances')
             ],
             },
            {'task': '1099-MISC to Subcontractors', 'priority': 3, 'dateofyear': '01-16',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'Issue contractor 1099-MISC to subcontractors',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Finances')
             ],
             },
            {'task': '990 Tax Return', 'priority': 3, 'dateofyear': '04-01',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'File 990 Tax Return',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Finances')
             ],
             },
            {'task': 'Maryland Property Taxes', 'priority': 3, 'dateofyear': '04-15',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'File Maryland State Annual Report and Personal Property Tax Return',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Finances')
             ],
             },
            {'task': 'Update Maryland Charitable Fundraising Registration', 'priority': 3, 'dateofyear': '04-15',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'File Maryland State Annual Update of Registration',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Finances')
             ],
             },
            {'task': 'Sales Tax H1', 'priority': 3, 'dateofyear': '06-20',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'File H1 Sales Tax Return',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Finances')
             ],
             },
            {'task': 'Sales Tax H2', 'priority': 3, 'dateofyear': '01-20',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'File H2 Sales Tax Return',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Finances')
             ],
             },
            {'task': 'Frederick City Property Taxes', 'priority': 3, 'dateofyear': '07-31',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'File Frederick City Personal Property Tax Return',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Finances')
             ],
             },
            {'task': 'RRCA Annual Dues, etc', 'priority': 3, 'dateofyear': '12-31',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'Renew RRCA Annual Dues, Insurance and Music Licensing',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Finances')
             ],
             },
            {'task': 'RRCA Property Insurance', 'priority': 3, 'dateofyear': '12-31',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'Renew RRCA Property Insurance',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Finances')
             ],
             },

            {'task': 'Annual FSRC Race Calendar', 'priority': 3, 'dateofyear': '11-30',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'Submit annual race calendar to the Board',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Races')
             ],
             },
            {'task': 'RRCA Race Calendar', 'priority': 3, 'dateofyear': '01-31',
             'expirystarts': timedelta(13 * 3 * 7),
             'isoptional': False,
             'expirysoon': timedelta(4 * 7),
             'description': 'Update RRCA Race Calendar',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Races')
             ],
             },

            {'task': 'Technology Roles and Responsibilities', 'priority': 5, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Review '
                            '[Technology Roles and Responsibilities](https://docs.google.com/document/d/1p73d2aPZ5ws8Ooul5JAgQYZXMAL2j2mj9NqXJkgpGY8/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Technology Committee Leadership')
             ],
             },
            {'task': 'Membership Roles and Responsibilities', 'priority': 5, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Review '
                            '[Membership Roles and Responsibilities](https://docs.google.com/document/d/1VAGcgKhi4EVB_vYN2-Q4cxC6x1-0mIlYe5wnYClOtMU/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Membership Committee Leadership')
             ],
             },
            {'task': 'Communications Roles and Responsibilities', 'priority': 5, 'period': timedelta(104 * 7),
             'isoptional': False,
             'expirysoon': timedelta(2 * 7),
             'description': 'Review '
                            '[Communications Roles and Responsibilities](https://docs.google.com/document/d/1F5-k1fqz96xanu_ckI_DfT3UllNiPBrw7pmHz8MNYWA/edit?usp=sharing)',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Communications Committee Leadership')
             ],
             },
        ]

        for thetask in tasks:
            fields = thetask.pop('fields',[])
            thistask = Task(interest=localfsrcinterest, **thetask)
            db.session.add(thistask)
            db.session.flush()
            for field in fields:
                need, taskfieldname = field.split('/')
                tasktaskfield = TaskTaskField(need=need, taskfield=TaskField.query.filter_by(fieldname=taskfieldname).one())
                thistask.fields.append(tasktaskfield)

        positions = [
            {'position': 'President',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'President'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Executive Officer'),
             ],
             },
            {'position': 'Vice President',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Executive Officer'),
             ],
             },
            {'position': 'Treasurer',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Executive Officer'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Finances'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Bank Account Full Access'),
             ],
             },
            {'position': 'Secretary',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Executive Officer'),
             ],
             },
            {'position': 'Reviewing Officer',
             'description': 'Performs regular (monthly) review of financial records',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Bank Account Full Access'),
             ],
             },
            {'position': 'Director',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board of Directors'),
             ],
             },
            {'position': 'Training Committee Chair',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'General Committee Leadership'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Training'),
             ],
             },
            {'position': 'Training Coach',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Training'),
             ],
             },
            {'position': 'Youth Training Coach',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Training'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Youth Training'),
             ],
             },
            {'position': 'Races Committee Chair',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'General Committee Leadership'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Races'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Signature Race Director'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Low Key Race Director'),
             ],
             },
            {'position': 'Market Street Mile Race Director',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Signature Race Director'),
             ],
             },
            {'position': 'Summer Solstice 8K Race Director',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Signature Race Director'),
             ],
             },
            {'position': 'Women\'s Distance Festival Race Director',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Signature Race Director'),
             ],
             },
            {'position': 'Rick\'s Run Race Director',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Signature Race Director'),
             ],
             },
            {'position': 'Lewis Run Race Director',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Low Key Race Director'),
             ],
             },
            {'position': 'Independence 5000 Race Director',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Low Key Race Director'),
             ],
             },
            {'position': 'Pie Run Race Director',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Low Key Race Director'),
             ],
             },
            {'position': 'Li\'l Bennet 5K Race Director',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Low Key Race Director'),
             ],
             },
            {'position': 'FSRC Memorial Scholarship Review Board Chair',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Memorial Scholarship'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'General Committee Leadership'),
             ],
             },
            {'position': 'Nominating Committee Member',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Nomination Process'),
             ],
             },
            {'position': 'Technology Chair',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Technology Committee Leadership'),
             ],
             },
            {'position': 'Membership Chair',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Membership Committee Leadership'),
             ],
             },
            {'position': 'Communications Chair',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Communications Committee Leadership'),
             ],
             },
            {'position': 'Store Chair',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'General Committee Leadership'),
             ],
             },
            {'position': 'Race Services Chair',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'General Committee Leadership'),
             ],
             },
            {'position': 'Competition Chair',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'General Committee Leadership'),
             ],
             },
            {'position': 'Community Liaison Chair',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'General Committee Leadership'),
             ],
             },
            {'position': 'Racing Team Chair',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'General Committee Leadership'),
             ],
             },
            {'position': 'Volunteer Appreciation Chair',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'General Committee Leadership'),
             ],
             },
            {'position': 'Panther\'s Head Coach',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Youth Training'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Training'),
             ],
             },
            {'position': 'Spires Head Coach',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Youth Training'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Training'),
             ],
             },
            {'position': 'Social Chair',
             'taskgroups': [
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'Board Meeting Attendee'),
                 next(tg['TaskGroup'] for tg in taskgroups if tg['taskgroup'] == 'General Committee Leadership'),
             ],
             },
        ]

        for position in positions:
            if 'description' not in position:
                position['description'] = position['position']
            thisposition = Position(interest=localfsrcinterest, **position)
            db.session.add(thisposition)
            db.session.flush()

        db.session.commit()

if __name__ == "__main__":
    main()