#!/usr/bin/env python3
"""
Compare a Facebook group's member list with the club's members.

Current members come from RunSignUp (club RSU_CLUB in members.cfg). Facebook aliases and
former members come from the members database, which can be an older copy (e.g. dev) since
aliases rarely change. Member.svc_member_id is the RunSignUp user_id, so an alias stays
linked to its member even if the database copy is old.

Input is the CSV downloaded by fb_group_members.js (columns name, facebook_id,
profile_url). Each Facebook member is matched to the members database, in this order:

1. Facebook alias (Members > Facebook Aliases)
2. first and last name, with and without middle name
3. first and last word of the name, dropping middle names and initials on either side
   (matched_by "first-last"; check these, since a middle word can be a maiden name)
4. possible matches, for checking by hand: members with the same last name whose first
   name starts with the same letter or is a known nickname (Becky/Rebecca); the same
   for a middle word of the Facebook name as the last name, since it may be a former last
   name (Ainsley Cain Godwin, formerly Ainsley Cain); and close name matches (difflib)

Names are compared ignoring case, accents, punctuation and extra spaces. A name stored as
"Last, First" also matches "First Last". Jr, Sr, II, III and IV at the end are ignored.

The output CSV has one row per Facebook member, sorted by status:

    current   matched to a current RunSignUp member (end_date from RunSignUp)
    former    matched to someone in the database or memberships export who isn't a current
              RunSignUp member (end_date is their last membership end there)
    possible  no exact match; candidates lists possible members, current first
    nomatch   not a member, or a member who needs a Facebook alias

A summary goes to stderr.

Run inside the app container, which has the database config. In dev, app/src is
mounted at /app:

    docker exec -i members-app-1 python /app/scripts/facebook_group_members/compare_fb_group_members.py \\
        < fb_group_members.csv > fb_group_compare.csv

Options: --interest (default fsrc); --memberships FILE, a CSV export of the Memberships view
(Members > Memberships), to use for former members when the database is an older copy. The
file has to be inside the container, e.g. docker cp it to /tmp and delete it afterwards.
"""

import argparse
import csv
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from difflib import get_close_matches

# app.py is in /app, one level above this script's package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

STATUS_ORDER = ['current', 'former', 'possible', 'nomatch']
FUZZY_CUTOFF = 0.85
SUFFIXES = {'jr', 'sr', 'ii', 'iii', 'iv'}

# nicknames that don't start with the same letter as the formal name; same-letter
# nicknames (Mike/Michael, Katie/Kaitlin) are caught by the first-letter check
NICKNAMES = {
    'becky': {'rebecca'}, 'becca': {'rebecca'}, 'bill': {'william'}, 'billy': {'william'},
    'will': {'william'}, 'bob': {'robert'}, 'bobby': {'robert'}, 'rob': {'robert'},
    'dick': {'richard'}, 'rick': {'richard'}, 'peggy': {'margaret'}, 'maggie': {'margaret'},
    'meg': {'margaret'}, 'jerry': {'gerald'}, 'ted': {'edward', 'theodore'}, 'ned': {'edward'},
    'tony': {'anthony'}, 'jack': {'john'}, 'liz': {'elizabeth'}, 'beth': {'elizabeth'},
    'betsy': {'elizabeth'}, 'betty': {'elizabeth'}, 'patty': {'patricia'}, 'trish': {'patricia'},
    'sally': {'sarah'}, 'lainey': {'elaine'}, 'sandy': {'alexandra', 'sandra'},
    'xander': {'alexander'}, 'sasha': {'alexandra', 'alexander'}, 'hank': {'henry'},
    'kit': {'christopher', 'katherine'}, 'cathy': {'katherine', 'catherine'},
    'kathy': {'catherine'}, 'jim': {'james'}, 'jimmy': {'james'}, 'izzie': {'isabel', 'isabella'},
}


def normalize(name):
    """lowercase, strip accents and punctuation, collapse spaces; "Last, First" -> "first last" """
    if not name:
        return ''
    name = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in name if not unicodedata.combining(c))
    if name.count(',') == 1:
        last, first = name.split(',')
        name = f'{first} {last}'
    name = re.sub(r"[^\w\s]", '', name.lower().replace('-', ' '))
    words = name.split()
    while len(words) > 2 and words[-1] in SUFFIXES:
        words.pop()
    return ' '.join(words)


def first_last(key):
    """normalized name without middle names or initials"""
    words = key.split()
    return f'{words[0]} {words[-1]}' if len(words) > 2 else None


def member_keys(member):
    keys = {normalize(f'{member.given_name} {member.family_name}')}
    if member.middle_name:
        keys.add(normalize(f'{member.given_name} {member.middle_name} {member.family_name}'))
    return keys


def load_people(interest, memberships=None):
    """
    return {person key: person dict}, {alias: [person key]}, {name: [person key]},
    {first and last word of name: [person key]},
    {last name: {(first name, person key)}}

    Current members come from RunSignUp. Facebook aliases and former members come from
    the members database, and former members also from memberships (rows of a Memberships
    view export) if given. Member.svc_member_id is the RunSignUp user_id, which links an
    alias to a RunSignUp member. A person can have more than one Member row, membership or
    user id; rows with the same user id, or the same name and dob, are combined, keeping the
    latest end date. People are keyed by (first name, last name, dob). Memberships
    from the older system (ids starting with @, before 2018) are ignored.
    """
    from flask import current_app
    from loutilities.user.model import Interest
    from members.community import CLUB_MEMBERS_PER_PAGE
    from members.helpers import make_runsignup_fluent_client
    from members.model import LocalInterest, Member, MemberAlias, Membership, db
    from sqlalchemy import func, select

    def add(userid, given, middle, family, dob, email, end_date, status):
        """add or update a person; the same user id, or the same name and dob, is the same person"""
        pkey = uid2key.get(userid) or (normalize(given), normalize(family), str(dob or ''))
        uid2key[userid] = pkey
        person = people.setdefault(pkey, {
            'name': f'{given} {family}', 'email': email, 'end_date': end_date,
            'status': status, 'keys': set(), 'aliases': set(),
        })
        person['keys'].add(normalize(f'{given} {family}'))
        # a nickname in quotes, e.g. Sonya "Izzie"
        for nick in re.findall(r'["\u201c\u201d](.+?)["\u201c\u201d]', given or ''):
            person['keys'].add(normalize(f'{nick} {family}'))
        if middle:
            person['keys'].add(normalize(f'{given} {middle} {family}'))
        if status == 'current' and person['status'] != 'current':
            person.update(status='current', name=f'{given} {family}', end_date=end_date, email=email)
        elif person['status'] == 'current' and status != 'current':
            pass  # keep RunSignUp's current end date and email
        elif end_date and (not person['end_date'] or end_date > person['end_date']):
            person['end_date'] = end_date
            person['email'] = email

    people = {}
    uid2key = {}

    # current members from RunSignUp
    rsu = make_runsignup_fluent_client()
    clubid = current_app.config['RSU_CLUB']
    page = 1
    while True:
        resp = rsu.club._(clubid).members.params({
            'current_members_only': 'T',
            'results_per_page': CLUB_MEMBERS_PER_PAGE,
            'page': page,
        }).get()
        pagemembers = resp.json().get('club_members', [])
        for m in pagemembers:
            user = m['user']
            add(str(user['user_id']), user['first_name'], user.get('middle_name'), user['last_name'],
                user.get('dob'), user['email'], date.fromisoformat(m['membership_end']), 'current')
        if len(pagemembers) < CLUB_MEMBERS_PER_PAGE:
            break
        page += 1
    ncurrent = len(people)

    # former members from a Memberships view export
    # Member ID is the user id at the time, and changes for some people, so name and dob
    # are what group these rows
    for row in memberships or []:
        if row['Membership ID'].startswith('@'):
            continue    # older system, before RunSignUp
        add(row['Member ID'], row['First Name'], None, row['Last Name'], row['DOB'], row['Email'],
            date.fromisoformat(row['End']) if row['End'] else None, 'former')

    # former members and aliases from the members database
    dbinterest = Interest.query.filter_by(interest=interest).one()
    locinterest = LocalInterest.query.filter_by(interest_id=dbinterest.id).one()
    lastend = dict(db.session.execute(
        select(Membership.member_id, func.max(Membership.end_date))
        .filter(Membership.interest_id == locinterest.id)
        .filter(Membership.svc_membership_id.not_like('@%'))   # older system, before RunSignUp
        .group_by(Membership.member_id)
    ).all())
    members = Member.query.filter_by(interest_id=locinterest.id).all()
    for member in members:
        if member.id not in lastend:
            continue    # only older-system memberships
        userid = member.svc_member_id or f'member.id={member.id}'
        add(userid, member.given_name, member.middle_name, member.family_name, member.dob, member.email,
            lastend.get(member.id), 'former')
        if member.memberalias and member.memberalias.facebookalias:
            people[uid2key[userid]]['aliases'].add(normalize(member.memberalias.facebookalias))

    print(f'{ncurrent} current members in RunSignUp club {clubid}, '
          f'{len(people) - ncurrent} former members', file=sys.stderr)

    byalias = defaultdict(list)
    byname = defaultdict(list)
    byfirstlast = defaultdict(list)
    bylast = defaultdict(set)
    for userid, person in people.items():
        for alias in person['aliases']:
            byalias[alias].append(userid)
        for key in person['keys']:
            byname[key].append(userid)
            byfirstlast[first_last(key) or key].append(userid)
            words = key.split()
            if len(words) > 1:
                bylast[words[-1]].add((words[0], userid))
    return people, byalias, byname, byfirstlast, bylast


def sheetsafe(value):
    """keep a spreadsheet from reading a Facebook name as a formula"""
    value = str(value)
    return f"'{value}" if value[:1] in ('=', '+', '-', '@') else value


def first_name_fits(fbfirst, first):
    """True if a Facebook first name could be a nickname of a member's first name"""
    return fbfirst[0] == first[0] or first in NICKNAMES.get(fbfirst, ()) or fbfirst in NICKNAMES.get(first, ())


def best(people, pkeys):
    """among same-named people, a current member first, then the latest end date"""
    return max((people[k] for k in pkeys),
               key=lambda p: (p['status'] == 'current', p['end_date'] or date.min))


def compare(fbrows, people, byalias, byname, byfirstlast, bylast):
    allnames = list(byname)
    out = []
    for row in fbrows:
        fbname = row['name']
        key = normalize(fbname)
        result = {
            'facebook_name': fbname,
            'facebook_id': row.get('facebook_id', ''),
            'profile_url': row.get('profile_url', ''),
            'status': 'nomatch', 'matched_by': '', 'member_name': '', 'end_date': '',
            'email': '', 'candidates': '', 'notes': '',
        }
        pkeys = None
        if key in byalias:
            pkeys, result['matched_by'] = byalias[key], 'alias'
        elif key in byname:
            pkeys, result['matched_by'] = byname[key], 'name'
        elif (first_last(key) or key) in byfirstlast:
            pkeys, result['matched_by'] = byfirstlast[first_last(key) or key], 'first-last'

        if pkeys:
            person = best(people, pkeys)
            result.update(status=person['status'], member_name=person['name'],
                          end_date=person['end_date'] or '', email=person['email'] or '')
            notes = []
            if len(set(pkeys)) > 1:
                notes.append(f'{len(set(pkeys))} people with this name; check which one')
            if person['status'] == 'former' and person['end_date'] and person['end_date'] >= date.today():
                notes.append('end date is in the future but not a current member in RunSignUp')
            result['notes'] = '; '.join(notes)
        elif key:
            words = key.split()
            cand_ids = []
            if len(words) > 1:
                cand_ids += sorted(uid for first, uid in bylast.get(words[-1], ()) if first_name_fits(words[0], first))
            # a middle word may be a former last name, e.g. Ainsley Cain Godwin, formerly Ainsley Cain
            for middle in words[1:-1]:
                cand_ids += sorted(uid for first, uid in bylast.get(middle, ()) if first_name_fits(words[0], first))
            for name in get_close_matches(key, allnames, n=3, cutoff=FUZZY_CUTOFF):
                cand_ids += byname[name]
            cand_ids = list(dict.fromkeys(cand_ids))
            if cand_ids:
                cands = sorted((people[uid] for uid in cand_ids),
                               key=lambda p: (p['status'] != 'current', p['name'].lower()))
                cands = [f"{p['name']} ({p['status']} {p['end_date']})" for p in cands]
                result.update(status='possible', matched_by='close', candidates='; '.join(cands))
        else:
            result['notes'] = 'no name in export'
        out.append(result)

    out.sort(key=lambda r: (STATUS_ORDER.index(r['status']), r['facebook_name'].lower()))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('infile', nargs='?', default='-', help='CSV from fb_group_members.js (default stdin)')
    parser.add_argument('--interest', default='fsrc')
    parser.add_argument('--memberships', help='CSV export of the Memberships view, for up to date former members')
    args = parser.parse_args()

    infile = sys.stdin if args.infile == '-' else open(args.infile, newline='', encoding='utf-8-sig')
    fbrows = list(csv.DictReader(infile))
    memberships = None
    if args.memberships:
        with open(args.memberships, newline='', encoding='utf-8-sig') as f:
            memberships = list(csv.DictReader(f))

    # creating the app logs; keep stdout for the CSV only
    stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        from app import app
        with app.app_context():
            people, byalias, byname, byfirstlast, bylast = load_people(args.interest, memberships)
    finally:
        sys.stdout = stdout

    results = compare(fbrows, people, byalias, byname, byfirstlast, bylast)

    writer = csv.DictWriter(sys.stdout, fieldnames=list(results[0]) if results else ['facebook_name'])
    writer.writeheader()
    writer.writerows({k: sheetsafe(v) for k, v in r.items()} for r in results)

    counts = Counter(r['status'] for r in results)
    print(f'{len(results)} Facebook members: ' + ', '.join(f'{counts[s]} {s}' for s in STATUS_ORDER),
          file=sys.stderr)


if __name__ == '__main__':
    main()
