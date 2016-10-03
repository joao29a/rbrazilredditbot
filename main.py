#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
import os
import time
import logging

import utils
import config


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


filename='posts.txt'

def get_posts_read():
    posts = []
    f = open(filename)
    for line in f:
        posts.append(line.replace('\n',''))
    return posts

def write_to_file(id):
    f = open(filename, 'a')
    f.write(id + '\n')
    f.close()


def main():
    reddit_conn = utils.reddit_login()
    imgur_conn = utils.imgur_login()
    posts = get_posts_read()
    while True:
        try:
            for post in utils.subreddits_posts(reddit_conn):
                try:
                    if post.id not in posts:
                        logging.info('new post: {}'.format(post.id))
                        url = utils.parse_url(post.url)
                        #logging.info("parsed url: {}, post: {}".format(url, post))
                        if not url:
                            # tools.folha url or blogs post in case of oglobo. do not post. however, put it in post list so it doesn't keep getting processed
                            posts.append(post.id)
                            continue

                        response = utils.readability_response(url)
                        if not response:
                            # do not retry it. if readability failed to parse, there is nothing we can do
                            posts.append(post.id)
                            logging.warning('something went wrong with readability {}'.format(response))
                            continue

                        title, body, domain = response['title'], response['content'], response['domain']

                        snippet = utils.parse_snippet(domain, body)

                        comments = utils.get_comments(domain, post.url)
                        top_comment = None
                        if comments:
                            try:
                                top_comment = comments['itens'][0]
                            except Exception as e:
                                logging.warning('error occurred {}'.format(e))

                        formatted_html = utils.html_beautify(title, body)
                        utils.save_as_image(
                            html=formatted_html,
                            filename=config.DOWNLOAD_FILENAME
                        )
                        img_link = utils.upload_image(imgur_conn, config.DOWNLOAD_FILENAME).replace("http://", "https://")
                        logging.info("img link generated: {}".format(img_link))
 
                        mensagem = '''Segue a imagem [link]({}), e você pode acessar o 
                            link para ler por [aqui]({}).'''.format(img_link, url)

                        if not snippet:
                            mensagem = mensagem + ''' Me desculpe,
                                não consegui buscar um resuminho.'''
                        else:
                            mensagem = mensagem + ''' Segue algumas
                            linhas do negócio: {} {}'''.format(*snippet) 

                        if top_comment:
                            try:
                                post.add_comment(
                                        mensagem + '''\n\n**Top
                                        comentário G1:**
                                        {}'''.format(utils.parse_top_comment(top_comment)))
                            except Exception as e:
                                post.add_comment(mensagem)
                        else:
                            post.add_comment(mensagem)

                        os.remove(config.DOWNLOAD_FILENAME)
                        posts.append(post.id)
                        write_to_file(post.id)
                except Exception as e:
                    logging.warning("error occurred {}".format(e))
                    pass

            logging.info("waiting...")
            time.sleep(config.SLEEP_TIME)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.warning("error occurred {}".format(e))
            pass  # do not die


if __name__ == '__main__':
    main()
