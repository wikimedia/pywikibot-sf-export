#!/usr/bin/python
"""
Main export/import script.

Basic workflow is as such:

* Get a list of tickets in each category
* For each ticket, if it is still open, export it
* Create a new bug in bugzilla.
* Leave a comment on the sf ticket with a link to the bugzilla bug
"""

