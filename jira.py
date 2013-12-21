import sys
import requests
import textwrap
import json
import bugzilla

from datetime import datetime, timedelta

assert(requests.__version__ > "1.0.0")

# iets met BugZilla nog

# JIRA config
project = "REPORTS"   # SET THIS!
stepsize = 1000

# BZ config
bug_defaults = {
    'product': 'Tool Labs tools',      # SET THIS!
    'component': 'tsreports',  # SET THIS!
    'version': 'unspecified',
    'blocked': '',               # SET THIS! (to tracking bug or empty for no tracking bug)
    'op_sys': 'All',
    'rep_platform': 'All',
}

#base_url = "http://192.168.1.103:8080/xmlrpc.cgi"
base_url = "https://bugzilla.wikimedia.org/xmlrpc.cgi"

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
    prefix = '>'*nindent + ' '
    return textwrap.fill(text, initial_indent=prefix, subsequent_indent=prefix, break_long_words=False)

users = {}

try:
    f = open('user-email-mapping.json', 'r')
    users = json.load(f)
except Exception, e:
    print e

def getBZuser(email, name):
    global users
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
        'jql': 'project = %s AND status in (Open, "In Progress", Reopened, "In Review", Assigned, "Waiting for customer")' % project,
        'fields': 'self',
        'maxResults': stepsize
    }
)['issues']

runAll = False

maillist = {}
retrIssues = []
for issue in issues:
    issue = get(issue['self'])
    retrIssues.append(issue)
    fields = issue['fields']

    if fields['assignee']:
        maillist[fields['assignee']['emailAddress']] = fields['assignee']['displayName']

    maillist[fields['reporter']['emailAddress']] = fields['reporter']['displayName']

    for c in fields['comment']['comments']:
        maillist[c['author']['emailAddress']] = c['author']['displayName']

print "Retrieving users from bugzilla..."

for mail, name in maillist.items():
    bzu = getBZuser(mail, name)
    if bzu:
        print "%s <%s> => %s" % (name, mail, bzu)
    else:
        print "%s <%s> not found" % (name, mail)

f = open('user-email-mapping.json', 'w')
json.dump(users, f)
f.close()

for issue in retrIssues:
    # check if issue is already on BZ
    existing_bugs = [bug.bug_id for bug in bz.query({"short_desc": "PYWP-16"})]
    if existing_bugs:
        print "Skipping " + issue['key'] + " " + fields['summary'] + "; already uploaded? Check bug ID %r" % existing_bugs
        continue
    fields = issue['fields']

    cclist = set()
    if fields['assignee']:
        cclist.add(getBZuser(fields['assignee']['emailAddress'], fields['assignee']['displayName']))
        assignee = "%s <%s>" % (fields['assignee']['displayName'], fields['assignee']['emailAddress'])
    else:
        assignee = "(none)"
    cclist.add(getBZuser(fields['reporter']['emailAddress'], fields['reporter']['displayName']))

    print issue['key'] + " " + fields['summary'],
    sys.stdout.flush()

    if not fields['description']:
        fields['description'] = u''
    description = u"""This issue was converted from https://jira.toolserver.org/browse/{i[key]}.
Summary: {f[summary]}
Issue type: {f[issuetype][name]} - {f[issuetype][description]}
Priority: {f[priority][name]}
Status: {f[status][name]}
Assignee: {assignee}

On {f[created]:%a, %d %b %Y %T}, {f[reporter][displayName]} <{f[reporter][emailAddress]}> opened the following bug:
{wrapped_description}
""".format(i=issue, f=fields, assignee=assignee, wrapped_description=reply_format(fields['description']))

    params = bug_defaults.copy()
    params['bug_severity'] = fields['priority']['name']
    params['summary'] = issue['key'] + " " + fields['summary']
    params['description'] = description

    bug = bz.createbug(**params)
    print " -- bz id ", bug.bug_id,
    sys.stdout.flush()

    ncs = 0
    natt = 0
    for comment in fields['comment']['comments']:
        ncs += 1
        cclist.add(getBZuser(comment['author']['emailAddress'], comment['author']['displayName']))
        commenttext = """On {f[created]:%a, %d %b %Y %T}, {f[author][displayName]} <{f[author][emailAddress]}> wrote:
{wrapped_description}
""".format(f=comment, wrapped_description=reply_format(comment["body"]))

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

    if not runAll:
        if raw_input().upper() == "A":
            runAll = True
