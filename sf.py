#!/usr/bin/python
"""
Stuff to export data from sf.net
"""
import datetime
import requests

# The different types of "tickets" we have
types = [
    'feature-requests',
    'support-requests',
    'patches',
    'bugs',
]


def parse_ts(ts):
    #2013-08-10 23:36:31.812000
    fmt = "%Y-%m-%d %H:%M:%S.%f"
    return datetime.datetime.strptime(ts, fmt)


def get_list(group):
    """
    Get a list of tickets for that group
    """
    # FIXME: need to continue the query somehow
    url = 'https://sourceforge.net/rest/p/pywikipediabot/' + group
    r = requests.get(url)
    return r.json()


class Ticket:
    def __init__(self, group, number):
        self.group = group
        self.id = number

    def api(self):
        """
        API endpoint for this specific ticket
        """
        return 'https://sourceforge.net/rest/p/pywikipediabot/{0}/{1}'.format(self.group, self.id)

    def human_url(self):
        """
        The url for humans to use
        """
        return 'http://sourceforge.net/p/pywikipediabot/{0}/{1}/'.format(self.group, self.id)

    def get(self):
        if not hasattr(self, '_json'):
            r = requests.get(self.api())
            self._json = r.json()
        return self._json

    @property
    def json(self):
        """
        JSON representation of the ticket.
        Will fetch if needed
        """
        if not hasattr(self, '_json'):
            self.get()
        return self._json

    def description(self):
        return t.json['ticket']['description']

    def summary(self):
        return t.json['ticket']['summary']

    def comments(self):
        for cmt in self.json['ticket']['discussion_thread']['posts']:
            yield cmt['text']

    def is_open(self):
        return self.json['ticket']['status'] == 'open'

if __name__ == '__main__':
    t = Ticket('bugs', 1653)
    print 'Fetching {0}...'.format(t.human_url())
    print 'Subject: {0}'.format(t.summary())
    print 'Created on: {0}'.format(parse_ts(t.json['ticket']['created_date']))
    print t.description()
    for cmt in t.comments():
        print '------'
        print cmt