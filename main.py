#!/usr/bin/python
"""
Main export/import script.

Basic workflow is as such:

* Get a list of tickets in each category
* For each ticket, if it is still open, export it
* Create a new bug in bugzilla.
* Leave a comment on the sf ticket with a link to the bugzilla bug
"""

import bugzilla
import sf
import bz

b = bugzilla.Bugzilla(
    url='https://bugzilla.wikimedia.org/xmlrpc.cgi',
    user='blah',
    password='blah'
)
b.connect()  # This calls b.login()

# The different types of "tickets" we have
types = [
    'feature-requests',
    'support-requests',
    'patches',
    'bugs',
]


def main():
    for group in types:
        for ticket in sf.iter_tickets(group):
            if ticket.is_not_closed():
                bug = bz.create_bug(b, ticket)
                text = 'This ticket has been moved to ' \
                       'https://bugzilla.wikimedia.org/show_bug.cgi?id={0}'.format(bug.id)

                ticket.add_comment(text)
                bz.add_to_see_also(bug, ticket)
                bz.upload_attachments(bug, ticket)

if __name__ == '__main__':
    main()
