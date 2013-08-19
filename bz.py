#!/usr/bin/python
"""
Stuff to import into bugzilla with
"""

import bugzilla

b = bugzilla.Bugzilla(url='https://bugzilla.wikimedia.org/xmlrpc.cgi')
b.connect()
for thing in b.getproducts():
    print thing['name']
