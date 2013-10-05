#!/usr/bin/python
"""
Stuff to export data from sf.net
"""
from __future__ import unicode_literals

import certifi
import datetime
import oauth2 as oauth
import requests
import StringIO
from urllib import urlencode
import urlparse
import webbrowser

from private import *  # Private keys!

REQUEST_TOKEN_URL = 'https://sourceforge.net/rest/oauth/request_token'
AUTHORIZE_URL = 'https://sourceforge.net/rest/oauth/authorize'
ACCESS_TOKEN_URL = 'https://sourceforge.net/rest/oauth/access_token'
URL_BASE = 'http://sourceforge.net/rest/'


def login():
    """
    Login to sf.net, get auth details...
    Taken from https://sourceforge.net/p/forge/documentation/Allura%20API/
    """
    consumer = oauth.Consumer(CONSUMER_KEY, CONSUMER_SECRET)
    client = oauth.Client(consumer)
    client.ca_certs = certifi.where()
    # Step 1: Get a request token. This is a temporary token that is used for
    # having the user authorize an access token and to sign the request to obtain
    # said access token.

    resp, content = client.request(REQUEST_TOKEN_URL, 'GET')
    if resp['status'] != '200':
        raise Exception("Invalid response %s." % resp['status'])

    request_token = dict(urlparse.parse_qsl(content))

    # these are intermediate tokens and not needed later
    #print "Request Token:"
    #print "    - oauth_token        = %s" % request_token['oauth_token']
    #print "    - oauth_token_secret = %s" % request_token['oauth_token_secret']
    #print

    # Step 2: Redirect to the provider. Since this is a CLI script we do not
    # redirect. In a web application you would redirect the user to the URL
    # below, specifying the additional parameter oauth_callback=<your callback URL>.

    webbrowser.open("%s?oauth_token=%s" % (AUTHORIZE_URL, request_token['oauth_token']))

    # Since we didn't specify a callback, the user must now enter the PIN displayed in
    # their browser.  If you had specified a callback URL, it would have been called with
    # oauth_token and oauth_verifier parameters, used below in obtaining an access token.
    oauth_verifier = raw_input('What is the PIN? ')

    # Step 3: Once the consumer has redirected the user back to the oauth_callback
    # URL you can request the access token the user has approved. You use the
    # request token to sign this request. After this is done you throw away the
    # request token and use the access token returned. You should store this
    # access token somewhere safe, like a database, for future use.
    token = oauth.Token(request_token['oauth_token'], request_token['oauth_token_secret'])
    token.set_verifier(oauth_verifier)
    client = oauth.Client(consumer, token)
    client.ca_certs = certifi.where()

    resp, content = client.request(ACCESS_TOKEN_URL, "GET")
    access_token = dict(urlparse.parse_qsl(content))
    print access_token
    return access_token


def make_authenticated_request(url, data):
    consumer = oauth.Consumer(CONSUMER_KEY, CONSUMER_SECRET)
    access_token = oauth.Token(ACCESS_KEY, ACCESS_SECRET)
    client = oauth.Client(consumer, access_token)
    client.ca_certs = certifi.where()
    response = client.request(
        url, 'POST',
        body=urlencode(data))
    print "Done.  Response was:"
    print response


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

    def status(self):
        return self.json['ticket']['status']

    def owner(self):
        if not ('assigned_to' in self.json['ticket']):
            return None
        if self.json['ticket']['assigned_to'] == "nobody":
            return None
        return self.json['ticket']['assigned_to']
        
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
        #r = requests.post(self.thread_api(), params)
        make_authenticated_request(self.thread_api(), params)
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
            s.write(r.text.encode('utf-8'))
            s.seek(0)  # reset
            yield url, s

    def export(self):
        # TODO: Is this good?
        t = ''
        t += 'Originally from: {0}\n'.format(self.human_url())
        t += 'Reported by: {0}\n'.format(self.reporter())
        t += 'Created on: {0}\n'.format(parse_ts(self.json['ticket']['created_date']))
        t += 'Subject: {0}\n'.format(self.summary())
        assignee = self.owner()
        if assignee:
            t += 'Assigned to: {0}\n'.format(assignee)
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
    login()
