#!/usr/bin/python
"""
Stuff to import into bugzilla with
"""

import logging


def create_bug(BZ, ticket):
    """
    Currently just a mock implementation...


    Import a bug from sf.net to bugzilla
    @param BZ: Bugzilla object that has already been logged in
    @type BZ: bugzilla.Bugzilla
    @param ticket: the sf.net ticket to import
    @type ticket: sf.Ticket
    """
    params = {
        'product': 'Pywikibot',
        'component': find_valid_component(ticket.labels()),  # Need to map this
        'summary': ticket.summary(),
        'version': '',  # ???
        'description': ticket.export(),
        'status': find_status(ticket),  # Need to map this
    }
    if ticket.group == 'feature-requests':
        params['severity'] = 'Enhancement'
    logging.info('Uploading {0} to Bugzilla'.format(ticket.human_url()))
    bug = BZ.createbug(**params)

    # Now add all the comments.
    for cmt in ticket.comments():
        upd = BZ.build_update(comment=cmt)
        BZ.update_bugs(bug.id, upd)

    return bug  # Bug object


def add_to_see_also(bug, ticket):
    """
    @type bug: bugzilla.Bug
    @type ticket: sf.Ticket
    """
    url = ticket.human_url()
    upd = bug.bugzilla.build_update(
        see_also_add=[url]
    )
    bug.bugzilla.update_bugs(bug.bug_id, upd)


def upload_attachments(bug, ticket):
    for url, obj in ticket.fetch_attachments():
        desc = 'Copy of attachment from {0}'.format(url)
        bug.bugzilla.attachfile(bug.bug_id,  # bug list
                                obj,  # StringIO object of attachment text
                                desc,  # Simple description of file
                                file_name=desc,  # Does this even make sense?
                                content_type='text/plain'  # python-bugzilla says we need to do this
        )

def find_status(ticket):
    if ticket.owner():
        return "ASSIGNED"
    return "NEW"
def find_valid_component(labels):
    """
    Modified slightly from Amir's list...
    @param labels: current labels on the ticket
    @return: component to add
    """
    components = [
        'category.py',
        'copyright.py',
        'Cosmetic changes',
        'General',
        'i18n',
        'interwiki.py',
        'login.py',
        'network',
        'redirect.py',
        'solve_disambiguation.py',
        'weblinkchecker.py',
        'Wikidata',
    ]
    mapping = {
        'interwiki': 'interwiki.py',
        'category': 'category.py',
        'copyright': 'copyright.py',
        'cosmetic_changes': 'Cosmetic changes',
        'GUI': 'General',  # GUI is deprecated
        'login': 'login.py',
        'other': 'General',
        'redirect': 'redirect.py',
        'rewrite': 'General',
        'solve_disambiguation': 'solve_disambiguation.py',
        'weblinkchecker': 'weblinkchecker.py',
    }
    for label in labels:
        if label in mapping:
            return mapping[label]
        if label in components:
            return label

    return 'General'
