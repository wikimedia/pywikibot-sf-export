#!/usr/bin/python
"""
Stuff to export data from sf.net
"""
import datetime
import requests
import StringIO


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
    r = requests.get(url, params={'limit': 5000})
    return r.json()


def iter_tickets(group):
    stuff = get_list(group)
    for thing in stuff['tickets']:
        yield Ticket(group, thing['ticket_num'])


class Ticket:
    def __init__(self, group, number):
        self.group = group
        self.id = number

    def api(self):
        """
        API endpoint for this specific ticket
        """
        return 'https://sourceforge.net/rest/p/pywikipediabot/{0}/{1}'.format(self.group, self.id)

    def thread_api(self):
        """
        API endpoint for the "discussion thread"
        """
        return self.api() + '/_discuss/thread/{0}/new'.format(self.json['ticket']['discussion_thread']['_id'])

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

    def labels(self):
        return self.json['ticket']['labels']

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
        return self.json['ticket']['description']

    def summary(self):
        return self.json['ticket']['summary']

    def comments(self):
        for cmt in self.json['ticket']['discussion_thread']['posts']:
            yield cmt['text']

    def is_open(self):
        """
        Works for the most part, but is_not_closed is better I think.
        """
        return self.json['ticket']['status'].startswith('open')

    def is_not_closed(self):
        return not self.json['ticket']['status'].startswith('closed')

    def add_comment(self, text):
        # TODO: Test this
        params = {'text': text}
        r = requests.post(self.thread_api(), params)
        print 'Added comment.'

    def reporter(self):
        rep = self.json['ticket']['reported_by']
        if rep == '*anonymous':
            rep = 'Anonymous user'
        return rep

    def iter_attachments(self):
        """
        Yields urls for each attachment.
        Apparently you can't get them over HTTPS, so force HTTP
        """
        for attachment in self.json['ticket']['attachments']:
            yield attachment['url'].replace('https://', 'http://')

    def fetch_attachments(self):
        """
        Actually fetches the attachments.
        returns tuple of str, StringIO.StringIO
        """
        for url in self.iter_attachments():
            r = requests.get(url)
            s = StringIO.StringIO()
            s.write(r.text)
            s.seek(0)  # reset
            yield url, s

    def export(self):
        # TODO: Is this good?
        t = ''
        t += 'Originally from: {0}\n'.format(self.human_url())
        t += 'Reported by: {0}\n'.format(self.reporter())
        t += 'Created on: {0}\n'.format(parse_ts(self.json['ticket']['created_date']))
        t += 'Subject: {0}\n'.format(self.summary())
        if len(self.labels()) > 1:
            t+= 'Original labels: ' + ', '.join(self.labels())
        t += 'Original description:\n{0}\n'.format(self.description())
        #for cmt in self.comments():
        #    t += '---------\n'
        #    t += cmt + '\n'
        return t


def testticket():
    t = Ticket('bugs', 1653)
    print 'Fetching {0}...'.format(t.human_url())
    print 'Subject: {0}'.format(t.summary())
    print 'Created on: {0}'.format(parse_ts(t.json['ticket']['created_date']))
    print t.description()
    for cmt in t.comments():
        print '------'
        print cmt


if __name__ == '__main__':
    i = iter_tickets('bugs')
    for t in i:
        print t.json['ticket']['reported_by']
