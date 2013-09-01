#!/usr/bin/python
"""
Main export/import script.

Basic workflow is as such:

* Get a list of tickets in each category
* For each ticket, if it is still open, export it
* Create a new bug in bugzilla.
* Leave a comment on the sf ticket with a link to the bugzilla bug
"""

import logging
import bugzilla
import sf
import bz

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Log to a file
fh = logging.FileHandler('sf-export.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

# Also print log messages
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)

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
                if len(ticket.labels()) > 1:
                    logging.warn('Ticket: {0} (now bug {1}) had multiple labels'.format(ticket.human_url(), bug.id))

if __name__ == '__main__':
    main()
