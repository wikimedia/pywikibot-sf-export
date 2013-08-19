#!/usr/bin/python
"""
Stuff to import into bugzilla with
"""


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
        'component': '',  # Need to map this
        'summary': ticket.summary(),
        'version': '',  # ???
        'description': ticket.export(),
        'status': '',  # Need to map this
    }
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