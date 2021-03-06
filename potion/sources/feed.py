#!/usr/bin/env python

# this file is part of potion.
#
#  potion is free software: you can redistribute it and/or modify
#  it under the terms of the gnu affero general public license as published by
#  the free software foundation, either version 3 of the license, or
#  (at your option) any later version.
#
#  potion is distributed in the hope that it will be useful,
#  but without any warranty; without even the implied warranty of
#  merchantability or fitness for a particular purpose.  see the
#  gnu affero general public license for more details.
#
#  you should have received a copy of the gnu affero general public license
#  along with potion. if not, see <http://www.gnu.org/licenses/>.
#
# (c) 2012- by adam tauber, <asciimoo@gmail.com>


import re

from feedparser import parse
from datetime import datetime
from urlparse import urlparse, urlunparse
from itertools import ifilterfalse, imap
import urllib
import urllib2
import httplib

from potion.models import db_session, Source, Item

opener = urllib2.build_opener()
opener.addheaders = [('User-agent', '')]


# removes annoying UTM params to urls.
utmRe=re.compile('utm_(source|medium|campaign|content)=')
def urlSanitize(url):
    # handle any redirected urls from the feed, like
    # ('http://feedproxy.google.com/~r/Torrentfreak/~3/8UY1UySQe1k/')
    us=httplib.urlsplit(url)
    if us.scheme=='http':
        conn = httplib.HTTPConnection(us.netloc, timeout=3)
        req = urllib.quote(url[7+len(us.netloc):])
    elif us.scheme=='https':
        conn = httplib.HTTPSConnection(us.netloc)
        req = urllib.quote(url[8+len(us.netloc):])
    #conn.set_debuglevel(9)
    headers={'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}
    conn.request("HEAD", req,None,headers)
    res = conn.getresponse()
    conn.close()
    if res.status in [301, 304]:
        url = res.getheader('Location')
    # removes annoying UTM params to urls.
    pcs=urlparse(urllib.unquote_plus(url))
    tmp=list(pcs)
    tmp[4]='&'.join(ifilterfalse(utmRe.match, pcs.query.split('&')))
    return urlunparse(tmp)

def fetchFeed(url):
    try:
        return opener.open(url, timeout=5)
    except:
        print '[EE] cannot fetch %s' % url
        return ''


def parseFeed(feed):
    counter = 0
    #modified = feed['modified'].timetuple() if feed.get('modified') else None
    f = None
    f = parse(fetchFeed(feed.address)
             ,etag      = feed.attributes.get('etag')
             ,modified  = feed.attributes.get('modified')
             )
    if not f:
        print '[EE] cannot parse %s - %s' % (feed.name, feed.address)
        return counter
    #print '[!] parsing %s - %s' % (feed.name, feed.url)
    try:
        feed.attributes['etag'] = f.etag
    except AttributeError:
        pass
    try:
        feed.attributes['modified'] = f.modified
    except AttributeError:
        pass
    d = feed.updated
    for item in reversed(f['entries']):
        try:
           u = urlSanitize(item['links'][0]['href'])
        except:
           u = ''
        # checking duplications
        if db_session.query(Item).filter(Item.source_id==feed.source_id).filter(Item.url==u).first():
            continue

        try:
            tmp_date = datetime(*item['updated_parsed'][:6])
        except:
            tmp_date = datetime.now()

        # title content updated
        try:
            c = unicode(''.join([x.value for x in item.content]))
        except:
            c = u'[EE] No content found, plz check the feed (%s) and fix me' % feed.name
            for key in ['media_text', 'summary', 'description', 'media:description']:
                if item.has_key(key):
                    c = unicode(item[key])
                    break

        t = unicode(item.get('title','[EE] Notitle'))

        # date as tmp_date?!
        feed.items.append(Item(t, c, url=u, attributes={'date':tmp_date}))
        db_session.commit()
        counter += 1
    feed.updated = d
    db_session.commit()
    #feed.save()
    return counter

if __name__ == '__main__':
    counter = sum(imap(parseFeed, Source.query.filter(Source.source_type=='feed').all()))
    print '[!] %d item added' % counter
