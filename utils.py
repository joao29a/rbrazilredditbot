#!/usr/bin/env python3
from __future__ import print_function
from urllib.parse import urlparse, quote
import subprocess

import logging

import praw
import requests
import weasyprint
from bs4 import BeautifulSoup
from imgurpython import ImgurClient

import config

import urllib.request as urlrequest
import json




def save_as_image(html, filename):
    '''Uses Weasyprint to convert HTML to a PNG.'''
    #logging.info("reading html file... {}".format(html))
    wp = weasyprint.HTML(string=html)

    logging.info("generating png...")
    wp.write_png(filename)
    logging.info("generated.")


def readability_response(url):
    req_url = config.READABILITY_API_URL.format(url)
    response = requests.get(req_url).json()
    error = response.get('error', None)
    if error:
        logging.warning("error reason: ".format(error))
        return None
    return response


def get_comments(domain, url):
    try:
        if 'g1.globo' in domain:
            api_url = 'http://comentarios.globo.com/comentarios/%s/%s/%s/%s/%s/populares/%s.json'

            command = 'curl -s %s | grep -e "idExterno" -e "shortUrl" -e "uri:"\
                    -e "titulo:"' % url
            p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
            
            out, err = p.communicate()

            def get_value(line):
                return quote(line.replace('"', "'")
                        .split("'")[2].replace('/', '@@'))

            values = {}
            for line in out.splitlines():
                line = str(line)
                if 'uri' in line:
                    values['uri'] = get_value(line)
                elif 'idExterno' in line:
                    values['idExterno'] = get_value(line)
                elif 'shortUrl' in line:
                    values['shortUrl'] = get_value(line)
                elif 'titulo' in line:
                    values['titulo'] = get_value(line)

            values['url'] = quote(url.replace('/', '@@'))

            path = api_url % (values['uri'], values['idExterno'], values['url'],
                    values['shortUrl'], values['titulo'], 1)


            response = urlrequest.urlopen(path)
            response = response.read().decode('utf8').replace('__callback_listacomentarios(','')
            response = ''.join(response.rsplit(')', 1))

            return json.loads(response)
    except Exception as e:
        logging.info('error: {}'.format(e))
    return None


def parse_top_comment(top_comment):
    return '\n\n*"' + top_comment['texto'] + '"* - ' +\
        top_comment['Usuario']['nomeFormatado']

def parse_snippet(domain, body):
    soup = BeautifulSoup(body, 'html.parser')


    def search_for_text(class_name, tag='div', element='class'):
        content = soup.find(tag, {element: class_name})
        logging.info("got content {}".format(content))
        if content:
            return ['\n\n*' + snippet.text.replace('\n', '').strip() + '*\n'
                    for snippet in content.find_all('p')[:2]]


    if 'folha' in domain:
        return search_for_text('content')
    elif 'oglobo' in domain:
        return search_for_text('corpo')
    elif 'g1.globo' in domain:
        content = search_for_text('materia-conteudo')
        if not content:
            content = search_for_text('post-content', 'section')
        return content
    elif 'noticias.uol' in domain:
        return search_for_text('texto', element='id')


def upload_image(imgur, filename):
    return imgur.upload_from_path(filename)['link']


def reddit_login():
    reddit = praw.Reddit(user_agent="the devil")
    reddit.login(
        config.REDDIT_USERNAME, config.REDDIT_PASSWORD, disable_warning=True
    )
    logging.info("logged into reddit")
    return reddit


def imgur_login():
    logging.info("logging into imgur")
    return ImgurClient(config.IMGUR_API_CLIENT, config.IMGUR_API_SECRET)


def parse_url(news_url):
    logging.info("news url: {}".format(news_url))
    url = None
    if 'folha' in news_url:
        if 'tools' in news_url:
            return news_url
        elif '?mobile' in news_url:
            url = news_url.replace('?mobile', '')
            url = url.replace('/m.folha', '/www1.folha')
        elif "web.archive" in news_url:
            url = news_url.replace('https://web.archive.org/save/', '')
        elif "http://f5" in news_url:
            # try http and https
            url = news_url.replace('http://f5', 'http://').replace('https://f5', 'https://')
        else:
            url = urlparse(news_url)
            url = url.scheme + '://' + url.netloc + url.path
        url = print_folha_url(url)
        logging.info("formatted Folha url: {}".format(url))
    elif 'oglobo' in news_url:
        # we cannot parse blog posts, so ignore them.
        if not 'blogs' in news_url:
            url = urlparse(news_url)
            url = url.scheme + '://' + url.netloc + url.path
    elif 'g1.globo' in news_url:
        return news_url
    elif 'noticias.uol' in news_url:
        return news_url
    return url


def print_folha_url(url):
    return 'http://tools.folha.com.br/print?site=emcimadahora&url={}'.format(url)


def subreddits_posts(conn):
    submissions = []

    def get_submissions_from_subreddits(subs):
        for sub in subs:
            for submission in conn.get_subreddit(sub).get_hot():
                submissions.append(submission)
            for submission in conn.get_subreddit(sub).get_new():
                submissions.append(submission)
            for submission in conn.get_subreddit(sub).get_controversial_from_day():
                submissions.append(submission)


    get_submissions_from_subreddits(config.SUBREDDITS)
    for submission in submissions:
        if 'folha.uol' in submission.url or 'oglobo' in submission.url\
                or 'g1.globo' in submission.url\
                or 'noticias.uol' in submission.url:
            yield submission


def html_beautify(title, body):
    soup = BeautifulSoup(body, 'html.parser')
    return '''<html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style type="text/css">
                body {
                    margin:40px auto;
                    max-width:650px;
                    line-height:1.6;
                    font-size:18px;
                    color:#444;
                    padding:0 10px;
                    background: white;
                }
                h1,h2,h3 {
                    line-height:1.2
                }
            </style>
        </head>
        <body>
        <h1>
            %s
        </h1>
            %s
        </body>
    </html>
    ''' % (title, soup.prettify())
