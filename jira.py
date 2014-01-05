#!/usr/bin/env python
# 
# Required packages:
reqs = """
requests >= 2.0.0
python-bugzilla >= 0.8.0
html2text >= 3.200.3
"""

import sys

try:
    import requests
    assert(requests.__version__ >= "2.0.0")

    import bugzilla
    assert(bugzilla.__version__ >= "0.8.0")

    import html2text
    assert(html2text.__version__ >= "3.200.3")
except (ImportError, AssertionError), e:
    print "Required package not found: ", e
    open("jira-reqs.txt", "w").write(reqs)
    print "Please pip install -r jira-reqs.txt"
    sys.exit(1)

import sys
import textwrap
import json
import re

from datetime import datetime, timedelta

# iets met BugZilla nog

# JIRA config
stepsize = 1000

if len(sys.argv) < 3:
    print("""Usage: {argv[0]} 'bugzilla component name within Tool Labs Tools' 'JIRA JQL query' [-importdoubles]

    -importdoubles can be used to double-import bugs, which is useful for
                   testing. Otherwise, bugs that already exist in Bugzilla
                   are skipped.

Example:
    {argv[0]} 'DrTrigonBot - General' 'project = DRTRIGON'"
""".format(argv=sys.argv))
    sys.exit(1)

component = sys.argv[1]
jql = sys.argv[2]

# BZ config
bug_defaults = {
    'product': 'Tool Labs tools',      # SET THIS!
    'component': component, #"Database Queries",  # SET THIS!
    'version': 'unspecified',
    'blocked': '',               # SET THIS! (to tracking bug or empty for no tracking bug)
    'op_sys': 'All',
    'rep_platform': 'All',
}

base_url = "https://bugzilla.wikimedia.org/xmlrpc.cgi"
saveMigration = True
skip_existing = "-importdoubles" not in sys.argv

if False:
    base_url = "http://192.168.1.103:8080/xmlrpc.cgi"
    saveMigration = False
    skip_existing = False
    bug_defaults = {
        'product': 'TestProduct',      # SET THIS!
        'component': 'TestComponent',  # SET THIS!
        'version': 'unspecified',
        'blocked': '',               # SET THIS! (to tracking bug or empty for no tracking bug)
        'op_sys': 'All',
        'rep_platform': 'All',
    }

username = "wmf.bugconverter@gmail.com"
import config
password = config.password

print "Logging in to Bugzilla..."

bz = bugzilla.Bugzilla(url=base_url)
bz.login(username, password)

def hook(a):
    for key in a:
        if isinstance(a[key], basestring):
            try:
                a[key] = datetime.strptime(a[key], "%Y-%m-%dT%H:%M:%S.%f+0000")
            except Exception, e:
                pass
    return a

def get(*args, **kwargs):
    kwargs['verify'] = False # mitmproxy
    return json.loads(requests.get(*args, **kwargs).text, object_hook=hook)

def reply_format(text, nindent=1):
    prefix = ('>'*nindent + ' ') if nindent > 0 else ''
    return textwrap.fill(text, initial_indent=prefix, subsequent_indent=prefix, break_long_words=False)

def htmltobz(html):
    # remove 'plain text' links that were linkified by jira
    html = re.sub(r'<a href="(.*?)">\1</a>', r'\1', html)

    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_links = True
    h.inline_links = False
    h.unicode_snob = True
    return h.handle(html)

users = {}

try:
    f = open('user-email-mapping.json', 'r')
    users = json.load(f)
except Exception, e:
    print e

def getBZuser(email, name):
    global users
    if not email:
        email = name + "@invalid"
    if email in users:
        return users[email]

    try:
        user = bz.getuser(email)
        users[email] = email
        return email
    except bugzilla.xmlrpclib.Fault, e:
        if e.faultCode == 51:
            pass
        else:
            raise

    # not found, try heuristics. Search by Full Name!
    fusers = bz.searchusers(name)
    if not fusers:
        users[email] = None
    else:
        user = fusers[0]
        print "Assuming %s <%s> is actually %s <%s>" % (name, email, user.real_name, user.email)
        if raw_input("Is this OK? Y/n ").upper().strip() == "Y":
            users[email] = user.email
        else:
            users[email] = None
    return users[email]

print "Retrieving issues from JIRA..."

issues = get(
    'https://jira.toolserver.org/rest/api/2/search',
    params={
        'jql': jql,
        'fields': 'self',
        'maxResults': stepsize
    }
)['issues']

runAll = False

maillist = {}
retrIssues = []
print "Getting %i details..." % len(issues)
for issue in issues:
    issue = get(issue['self'] + "?expand=renderedFields")
    retrIssues.append(issue)
    fields = issue['fields']

    if fields['assignee']:
        maillist[fields['assignee']['emailAddress']] = fields['assignee']['displayName']

    maillist[fields['reporter']['emailAddress']] = fields['reporter']['displayName']

    for c in fields['comment']['comments']:
        if 'author' in c:
            maillist[c['author']['emailAddress']] = c['author']['displayName']

print "Retrieving users from bugzilla..."

for mail, name in maillist.items():
    bzu = getBZuser(mail, name)
    if bzu:
        print "%s <%s> => %s" % (name, mail, bzu)
    else:
        print "%s <%s> not found" % (name, mail)

f = open('user-email-mapping.json', 'w')
json.dump(users, f, indent=4)
f.close()

for issue in retrIssues:
    fields = issue['fields']
    renderedFields = issue['renderedFields']

    # check if issue is already on BZ
    existing_bugs = bz.query({"short_desc": issue['key'] + " "})
    if existing_bugs and skip_existing:
        found = False
        for bug in existing_bugs:
            if (issue['key'] + " ") in bug.summary:
                print "Skipping " + issue['key'] + " " + fields['summary'] + "; already uploaded? Check bug ID %i" % bug.bug_id
                found = True
                break
        if found:
            continue
    cclist = set()
    if fields['assignee']:
        cclist.add(getBZuser(fields['assignee']['emailAddress'], fields['assignee']['displayName']))
        assignee = "%s <%s>" % (fields['assignee']['displayName'], fields['assignee']['emailAddress'])
    else:
        assignee = "(none)"
    cclist.add(getBZuser(fields['reporter']['emailAddress'], fields['reporter']['displayName']))

    print issue['key'] + " " + fields['summary'],
    sys.stdout.flush()

    if not runAll:
        if raw_input().upper() == "A":
            runAll = True

    if not renderedFields['description']:
        renderedFields['description'] = u''
    description = u"""This issue was converted from https://jira.toolserver.org/browse/{i[key]}.
Summary: {f[summary]}
Issue type: {f[issuetype][name]} - {f[issuetype][description]}
Priority: {f[priority][name]}
Status: {f[status][name]}
Assignee: {assignee}

-------------------------------------------------------------------------------
From: {f[reporter][displayName]} <{f[reporter][emailAddress]}>
Date: {f[created]:%a, %d %b %Y %T}
-------------------------------------------------------------------------------

{description}
""".format(i=issue, f=fields, assignee=assignee, description=htmltobz(renderedFields['description']))

    params = bug_defaults.copy()
    params['bug_severity'] = fields['priority']['name']
    params['summary'] = issue['key'] + " " + fields['summary']
    params['description'] = description
    params['assigned_to'] = username # set assignee to the bug convertor initially

    bug = bz.createbug(**params)
    print " -- bz id ", bug.bug_id,
    sys.stdout.flush()

    ncs = 0
    natt = 0
    for comment,renderedComment in zip(fields['comment']['comments'], renderedFields['comment']['comments']):
        ncs += 1
        if 'author' in comment:
            cclist.add(getBZuser(comment['author']['emailAddress'], comment['author']['displayName']))
        else:
            comment['author'] = {'displayName': "Anonymous", 'emailAddress': 'None'}
        commenttext = u"""-------------------------------------------------------------------------------
From: {f[author][displayName]} <{f[author][emailAddress]}>
Date: {f[created]:%a, %d %b %Y %T}
-------------------------------------------------------------------------------

{description}
""".format(f=comment, description=htmltobz(renderedComment["body"]))

        bug.addcomment(commenttext)

        if 'attachment' in fields:
            for attachment in fields['attachment']:
                if attachment['author']['emailAddress'] == comment['author']['emailAddress'] and \
                   abs(attachment['created'] - comment['created']) < timedelta(seconds=1):
                    natt += 1
                    atfile = bug.bugzilla.attachfile(
                            bug.bug_id,
                            requests.get(attachment['content'], stream=True).raw,
                            comment["body"],
                            file_name = attachment['filename'],
                            content_type = attachment['mimeType']
                    )

    # now insert email addresses. Do this as last action, to prevent bugspam

    update = {'cc_add': []}
    if fields['assignee']:
        bzu = getBZuser(fields['assignee']['emailAddress'], fields['assignee']['displayName'])
        if bzu:
            update['assigned_to'] = bzu

    for user in cclist:
        if user:
            update['cc_add'].append(user)

    if fields['status']:
        sn = fields['status']['name']
        if sn in ["Open", "Reopened", "Unassigned", "Accepted", "Waiting for customer"]:
            update['status'] = "NEW"
        elif sn in ["In Progress", "In Review", "Assigned"]:
            update['status'] = "ASSIGNED"
        elif sn in ["Resolved", "Closed", "Declined", "Done", "Aborted"]:
            update['status'] = "RESOLVED"
            if 'assigned_to' not in update:
                update['assigned_to'] = '(none)'
            update['comment'] = """
This bug was imported as RESOLVED. The original assignee has therefore not been
set, and the original reporters/responders have not been added as CC, to
prevent bugspam.

If you re-open this bug, please consider adding these people to the CC list:
Original assignee: %s
CC list: %s""" % (update['assigned_to'], ', '.join(update['cc_add']))
            del update['assigned_to'] # no need to assign a bug that has been resolved
            del update['cc_add'] # also no need to add CCs

    if fields['resolution']:
        if 'status' in update and update['status'] == "RESOLVED":
            rn = fields['resolution']['name']
            if rn in ["Fixed", "Answered"]:
                update['resolution'] = "FIXED"
            elif rn in ["Won't Fix", "Declined", "External/Upstream"]:
                update['resolution'] = "WONTFIX"
            elif rn in ["Incomplete", "Cannot Reproduce"]:
                update['resolution'] = "WORKSFORME"
            elif rn in ["Duplicate"]:
                update['resolution'] = "DUPLICATE" # these should not be imported in the first place...
            elif rn in ["Not a bug"]:
                update['resolution'] = "INVALID"

    bzupdate = bz.build_update(**update)
    try:
        bz.update_bugs(bug.bug_id, bzupdate)
    except bugzilla.xmlrpclib.Fault, e:
        if e.faultCode == 115:
            print "WARNING: Cannot assign bug on Bugzilla!"
            del update['assigned_to']
            bzupdate = bz.build_update(**update)
            bz.update_bugs(bug.bug_id, bzupdate)

    print " -- %i comments, %i attachments" % (ncs, natt)
    sys.stdout.flush()

    if saveMigration:
        comment = "This bug has been migrated to Bugzilla: https://bugzilla.wikimedia.org/%i" % bug.bug_id
        response = requests.post(issue['self'] + "/transitions",
            headers={"content-type": "application/json"},
            data=json.dumps(
                {
                    "transition": {"id": "2"},
                    "update": {
                        "comment": [{"add": {"body": comment}}],
                        "resolution": [{"set": {"id": "7"}}] # "Answered"
                    }
                }
            ),
            auth=('bugzilla-exporter', password)
        )

        if response.status_code != 204: #ok
            print "WARNING: Cannot transition bug %s: %s" % (issue['key'], response.text)
            requests.post(issue['self'] + "/comment",
                headers={"content-type": "application/json"},
                data=json.dumps({'body': comment}),
                auth=('bugzilla-exporter', password)
            )


