#!/usr/bin/python3
# -*- coding: utf-8 -*-
from GoogleScraper.adwords import get_traffic
from GoogleScraper.semantic_mapping import generate_map
from GoogleScraper import scrape_with_config, GoogleSearchError

if __name__ == '__main__':

    config = {
        'SCRAPING': {
            'use_own_ip': 'True',
            'keywords': 'per se',
            'search_engines': 'google',
            'num_workers': 1
        },
        'SELENIUM': {
            'sel_browser': 'chrome',
        },
        'GLOBAL': {
            'do_caching': 'False',
        },
        'OUTPUT': {
            'database_name': 'scraping_results'
        }
    }

    try:
        sqlalchemy_session = scrape_with_config(config)
        # generate_map(config, 2)
    except GoogleSearchError as e:
        print(e)
