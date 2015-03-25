# -*- coding: utf-8 -*-

import re
import json
from sqlalchemy import *
from sqlalchemy.orm import *
from GoogleScraper import scrape_with_config, GoogleSearchError
from GoogleScraper.database import SearchEngineResultsPage, KnowledgeGraph

def generate_map(config):

    semantic_map = {'name': keyword_cleanup(config['SCRAPING']['keywords']), 'type': 'origin', 'size': 0}
    keywords = [keyword_cleanup(config['SCRAPING']['keywords'])]
    keywords_string = '\n'.join(keywords)
    n_depth = 2

    for i in range(n_depth):
        keywords_temp = []
        config['SCRAPING']['keywords'] = keywords_string
        sqlalchemy_session = scrape_with_config(config)

        keyword_pointers = {}
        for keyword in keywords:
            results = []
            traverse(semantic_map, keyword, results)
            keyword_pointers[keyword] = results

        for keyword in keywords:
            children = []
            serp_id = sqlalchemy_session.query(SearchEngineResultsPage.id).filter(SearchEngineResultsPage.query == keyword).order_by(desc(SearchEngineResultsPage.id)).first()[0]
            related_searches = sqlalchemy_session.query(SearchEngineResultsPage.related_searches).filter(SearchEngineResultsPage.query == keyword).order_by(desc(SearchEngineResultsPage.id)).first()[0]
            disambiguation_results = sqlalchemy_session.query(SearchEngineResultsPage.disambiguation_results).filter(SearchEngineResultsPage.query == keyword).order_by(desc(SearchEngineResultsPage.id)).first()[0]
            autocomplete_results = sqlalchemy_session.query(SearchEngineResultsPage.autocomplete_results).filter(SearchEngineResultsPage.query == keyword).order_by(desc(SearchEngineResultsPage.id)).first()[0]
            autocorrect_forced = sqlalchemy_session.query(SearchEngineResultsPage.autocorrect_forced).filter(SearchEngineResultsPage.query == keyword).order_by(desc(SearchEngineResultsPage.id)).first()[0]
            autocorrect_suggested = sqlalchemy_session.query(SearchEngineResultsPage.autocorrect_suggested).filter(SearchEngineResultsPage.query == keyword).order_by(desc(SearchEngineResultsPage.id)).first()[0]
            people_also_search_for = (sqlalchemy_session.query(KnowledgeGraph.people_also_search_for).filter(KnowledgeGraph.serp_id == serp_id).order_by(desc(KnowledgeGraph.id)).first()[0] if sqlalchemy_session.query(exists().where(KnowledgeGraph.serp_id == serp_id)).scalar() else None)

            if related_searches is not None:
                if len(related_searches) > 1:
                    related_searches = related_searches.split('; ')
                    for related_search in related_searches:
                        children.append({'name': keyword_cleanup(related_search), 'type': 'related_search', 'size': 0})
                        if keyword_cleanup(related_search) not in keywords_temp:
                            keywords_temp.append(keyword_cleanup(related_search))
                else:
                    children.append({'name': keyword_cleanup(related_searches), 'type': 'related_search', 'size': 0})
                    if keyword_cleanup(related_searches) not in keywords_temp:
                        keywords_temp.append(keyword_cleanup(related_searches))

            if disambiguation_results is not None:
                if len(disambiguation_results) > 1:
                    disambiguation_results = disambiguation_results.split('; ')
                    for disambiguation_result in disambiguation_results:
                        children.append({'name': keyword_cleanup(disambiguation_result[:disambiguation_result.find(' - ')]), 'type': 'disambiguation_result', 'size': 0})
                        if keyword_cleanup(disambiguation_result[:disambiguation_result.find(' - ')]) not in keywords_temp:
                            keywords_temp.append(keyword_cleanup(disambiguation_result[:disambiguation_result.find(' - ')]))
                else:
                    children.append({'name': keyword_cleanup(disambiguation_results[:disambiguation_results.find(' - ')]), 'type': 'disambiguation_result', 'size': 0})
                    if keyword_cleanup(disambiguation_results[:disambiguation_results.find(' - ')]) not in keywords_temp:
                        keywords_temp.append(keyword_cleanup(disambiguation_results[:disambiguation_results.find(' - ')]))

            if autocomplete_results is not None:
                if len(autocomplete_results) > 1:
                    autocomplete_results = autocomplete_results.split('; ')
                    for autocomplete_result in autocomplete_results:
                        children.append({'name': keyword_cleanup(autocomplete_result), 'type': 'autocomplete_result', 'size': 0})
                        if keyword_cleanup(autocomplete_result) not in keywords_temp:
                            keywords_temp.append(keyword_cleanup(autocomplete_result))
                else:
                    children.append({'name': keyword_cleanup(autocomplete_results), 'type': 'autocomplete_result', 'size': 0})
                    if keyword_cleanup(autocomplete_results) not in keywords_temp:
                        keywords_temp.append(keyword_cleanup(autocomplete_results))

            if autocorrect_forced is not None:
                children.append({'name': keyword_cleanup(autocorrect_forced), 'type': 'autocorrect_forced', 'size': 0})
                if keyword_cleanup(autocorrect_forced) not in keywords_temp:
                    keywords_temp.append(keyword_cleanup(autocorrect_forced))
            elif autocorrect_suggested is not None:
                children.append({'name': keyword_cleanup(autocorrect_suggested), 'type': 'autocorrect_suggested', 'size': 0})
                if keyword_cleanup(autocorrect_suggested) not in keywords_temp:
                    keywords_temp.append(keyword_cleanup(autocorrect_suggested))

            if people_also_search_for is not None:
                if len(people_also_search_for) > 1:
                    people_also_search_for = people_also_search_for.split('; ')
                    for people_also_search_for_element in people_also_search_for:
                        children.append({'name': keyword_cleanup(people_also_search_for_element), 'type': 'people_also_search_for', 'size': 0})
                        if keyword_cleanup(people_also_search_for_element) not in keywords_temp:
                            keywords_temp.append(keyword_cleanup(people_also_search_for_element))
                else:
                    children.append({'name': keyword_cleanup(people_also_search_for), 'type': 'people_also_search_for', 'size': 0})
                    if keyword_cleanup(people_also_search_for) not in keywords_temp:
                        keywords_temp.append(keyword_cleanup(people_also_search_for))

            pointers = keyword_pointers[keyword]
            for pointer in pointers:
                pointer['children'] = children

        keywords = keywords_temp
        keywords_string = '\n'.join(keywords_temp)

    print (json.dumps(semantic_map, indent=3))


def traverse(obj, target, results):
    if isinstance(obj, dict):
        if obj['name'] == target and 'children' not in obj:
            results.append(obj)
        return {k: traverse(v, target, results) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [traverse(elem, target, results) for elem in obj]
    else:
        return obj  # no container, just values (str, int, float)

def keyword_cleanup(keyword):
    return re.sub(' +',' ', re.sub('[^\x00-\x7F]+',' ', keyword.lower()))
