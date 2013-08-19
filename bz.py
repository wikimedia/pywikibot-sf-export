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
    return bug.id  # Numerical bug id
