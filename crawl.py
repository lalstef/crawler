#!/bin/python

"""
Asynchronously crawl URLs from a given list and save the first 10 characters of the page to a database
"""
import os
import csv
import requests
import argparse
import multiprocessing
from itertools import islice
import sqlalchemy as db

from logger import logger

MAX_CPU_NUMBER_TO_USE = multiprocessing.cpu_count() * 2
USER_ARGENT_STRING = 'Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1667.0 Safari/537.36'
FIRST_N_SYMBOLS_TO_USE = 10
URLS_TABLE_NAME = 'visited_urls'

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('file', metavar='FILE', type=str, help='path of the file to read URLs from')
parser.add_argument('--cpu-count', metavar='CPU_COUNT', type=int, default=MAX_CPU_NUMBER_TO_USE,
                    help='number of CPU cores (processes) the program should use')
args = parser.parse_args()

cpu_count = args.cpu_count
if args.cpu_count > MAX_CPU_NUMBER_TO_USE:
    logger.warning("The current CPU has {} CPU cores. Suggested maximum process count is {}."
            .format(multiprocessing.cpu_count(), MAX_CPU_NUMBER_TO_USE))

# Start replenish the queue with new urls when MIN_URLS_PER_PROCESS size of the queue is reached
MIN_URLS_PER_PROCESS = 2
# Keep around 10 times the CPU count urls in the queue at once
MAX_URLS_PER_PROCESS = 10
URLS_BATCH_SIZE = cpu_count * MAX_URLS_PER_PROCESS


def prepare_database():
    """
    Create connection to the database and create the necessary table.

    :return: connection - connection to the database
    """

    # Connect to the database
    engine = db.create_engine(os.environ.get('POSTGRES_DATABASE_URL'))
    connection = engine.connect()
    metadata = db.MetaData(engine)

    # Define the table
    urls_table = db.Table(
       URLS_TABLE_NAME, 
       metadata, 
       db.Column('url', db.String, primary_key=True), 
       db.Column('first_symbols', db.String(32)), 
    )

    if engine.dialect.has_table(engine, URLS_TABLE_NAME):
        urls_table.drop(engine)

    # Create the table
    metadata.create_all()

    return connection, urls_table

def fetch_url(connection, urls_table, queue, state):
    """
    Fetch url from the queue, get the response, save it to the database.

    This is the function being 'multiprocessed'. Works while there are urls in the queue.
    """
    while not queue.empty():
        # Check if the queue needs to be replenished
        if queue.qsize() < (cpu_count * MIN_URLS_PER_PROCESS):
            if not state['queue_loading_in_process']:
                replenish_queue(queue, state)
                state['queue_loading_in_process'] = False

        # Get next url from queue 
        url_id, url = queue.get()

        # Fetch response
        try:
            response = requests.get(url, headers={'User-Agent': USER_ARGENT_STRING})
            first_symbols = response.text[:FIRST_N_SYMBOLS_TO_USE]
            
            # Save url to database
            connection.execute(urls_table.insert(), url=url, first_symbols=first_symbols)
            
            logger.info("(PID {}) {}: {}".format(os.getpid(), url, first_symbols))
        except Exception as e:
            logger.error(e)



def replenish_queue(queue, state):
    """ 
    Read next batch of URLs from the file and put them to the queue. 

    We avoid reading the whole file at once to avoid using up too much memory.
    """
    logger.info('Replenishing queue. Queue size is {}'.format(queue.qsize()))
    
    last_file_pointer = state['file_pointer']
    state['file_pointer'] += URLS_BATCH_SIZE 
    domains = []

    with open(args.file) as domains_file:
        domains = list(islice(domains_file, last_file_pointer, state['file_pointer']))

    # Process domains and add urls to queue
    for item in domains:
        item = item.strip()
        domain_id, domain = item.split(',')
        url = 'http://{}'.format(domain)
        queue.put((domain_id, url))

    queue_loading_in_process = False


def crawl(connection, urls_table):
    """
    Create appropriate number of process and start them.
    """
    logger.info('Crawling started...')
    
    queue = multiprocessing.Queue()

    # Create the processes
    with multiprocessing.Manager() as manager:

        state = manager.dict()
        state['file_pointer'] = 0
        state['queue_loading_in_process'] = False

        processes = [
            multiprocessing.Process(
                target=fetch_url, 
                args=(connection, urls_table, queue, state)) 
            for _ in range(cpu_count)
        ]

        # Load some urls in the queue
        replenish_queue(queue, state)

        # Run processes
        for p in processes:
            p.start()

        # Exit the completed processes
        for p in processes:
            p.join()


if __name__ == '__main__':
    connection, urls_table = prepare_database()
    crawl(connection, urls_table)