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
                num = bz.create_bug(b, ticket)
                text = 'This ticket has been moved to ' \
                       'https://bugzilla.wikimedia.org/show_bug.cgi?id={0}'.format(num)

                ticket.add_comment(text)

if __name__ == '__main__':
    main()
