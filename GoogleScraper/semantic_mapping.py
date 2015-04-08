# -*- coding: utf-8 -*-

import re
import json
from sqlalchemy import *
from sqlalchemy.orm import *
from GoogleScraper import scrape_with_config, GoogleSearchError
from GoogleScraper.adwords import get_traffic
from GoogleScraper.database import SearchEngineResultsPage, KnowledgeGraph

def generate_map(config, n_depth):

    semantic_map = {'name': keyword_cleanup(config['SCRAPING']['keywords']), 'type': 'origin', 'duplicate': False}
    duplicates = {keyword_cleanup(config['SCRAPING']['keywords']): 1}
    keywords = [keyword_cleanup(config['SCRAPING']['keywords'])]
    keywords_string = '\n'.join(keywords)

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

            average_monthly_search_volume = sqlalchemy_session.query(SearchEngineResultsPage.average_monthly_search_volume).filter(SearchEngineResultsPage.query == keyword).order_by(desc(SearchEngineResultsPage.id)).first()[0]
            competition = sqlalchemy_session.query(SearchEngineResultsPage.competition).filter(SearchEngineResultsPage.query == keyword).order_by(desc(SearchEngineResultsPage.id)).first()[0]

            if related_searches is not None:
                if len(related_searches) > 1:
                    related_searches = related_searches.split('; ')
                    for related_search in related_searches:
                        if keyword_cleanup(related_search) not in keywords_temp:
                            keywords_temp.append(keyword_cleanup(related_search))
                        if keyword_cleanup(related_search) not in duplicates:
                            duplicates[keyword_cleanup(related_search)] = 1
                            children.append({'name': keyword_cleanup(related_search), 'type': 'related_search', 'duplicate': False})
                        else:
                            duplicates[keyword_cleanup(related_search)] += 1
                            children.append({'name': keyword_cleanup(related_search), 'type': 'related_search', 'duplicate': True})
                else:
                    if keyword_cleanup(related_searches) not in keywords_temp:
                        keywords_temp.append(keyword_cleanup(related_searches))
                    if keyword_cleanup(related_searches) not in duplicates:
                        duplicates[keyword_cleanup(related_searches)] = 1
                        children.append({'name': keyword_cleanup(related_searches), 'type': 'related_search', 'duplicate': False})
                    else:
                        duplicates[keyword_cleanup(related_searches)] += 1
                        children.append({'name': keyword_cleanup(related_searches), 'type': 'related_search', 'duplicate': True})

            if disambiguation_results is not None:
                if len(disambiguation_results) > 1:
                    disambiguation_results = disambiguation_results.split('; ')
                    for disambiguation_result in disambiguation_results:
                        if keyword_cleanup(disambiguation_result[:disambiguation_result.find(' - ')]) not in keywords_temp:
                            keywords_temp.append(keyword_cleanup(disambiguation_result[:disambiguation_result.find(' - ')]))
                        if keyword_cleanup(disambiguation_result[:disambiguation_result.find(' - ')]) not in duplicates:
                            duplicates[keyword_cleanup(disambiguation_result[:disambiguation_result.find(' - ')])] = 1
                            children.append({'name': keyword_cleanup(disambiguation_result[:disambiguation_result.find(' - ')]), 'type': 'disambiguation_result', 'duplicate': False})
                        else:
                            duplicates[keyword_cleanup(disambiguation_result[:disambiguation_result.find(' - ')])] += 1
                            children.append({'name': keyword_cleanup(disambiguation_result[:disambiguation_result.find(' - ')]), 'type': 'disambiguation_result', 'duplicate': True})

                else:
                    if keyword_cleanup(disambiguation_results[:disambiguation_results.find(' - ')]) not in keywords_temp:
                        keywords_temp.append(keyword_cleanup(disambiguation_results[:disambiguation_results.find(' - ')]))
                    if keyword_cleanup(disambiguation_results[:disambiguation_results.find(' - ')]) not in duplicates:
                        duplicates[keyword_cleanup(disambiguation_results[:disambiguation_results.find(' - ')])] = 1
                        children.append({'name': keyword_cleanup(disambiguation_results[:disambiguation_results.find(' - ')]), 'type': 'disambiguation_result', 'duplicate': False})
                    else:
                        duplicates[keyword_cleanup(disambiguation_results[:disambiguation_results.find(' - ')])] += 1
                        children.append({'name': keyword_cleanup(disambiguation_results[:disambiguation_results.find(' - ')]), 'type': 'disambiguation_result', 'duplicate': True})

            if autocomplete_results is not None:
                if len(autocomplete_results) > 1:
                    autocomplete_results = autocomplete_results.split('; ')
                    for autocomplete_result in autocomplete_results:
                        if keyword_cleanup(autocomplete_result) not in keywords_temp:
                            keywords_temp.append(keyword_cleanup(autocomplete_result))
                        if keyword_cleanup(autocomplete_result) not in duplicates:
                            duplicates[keyword_cleanup(autocomplete_result)] = 1
                            children.append({'name': keyword_cleanup(autocomplete_result), 'type': 'autocomplete_result', 'duplicate': False})
                        else:
                            duplicates[keyword_cleanup(autocomplete_result)] += 1
                            children.append({'name': keyword_cleanup(autocomplete_result), 'type': 'autocomplete_result', 'duplicate': True})

                else:
                    if keyword_cleanup(autocomplete_results) not in keywords_temp:
                        keywords_temp.append(keyword_cleanup(autocomplete_results))
                    if keyword_cleanup(autocomplete_results) not in duplicates:
                        duplicates[keyword_cleanup(autocomplete_results)] = 1
                        children.append({'name': keyword_cleanup(autocomplete_results), 'type': 'autocomplete_result', 'duplicate': False})
                    else:
                        duplicates[keyword_cleanup(autocomplete_results)] += 1
                        children.append({'name': keyword_cleanup(autocomplete_results), 'type': 'autocomplete_result', 'duplicate': True})

            if autocorrect_forced is not None:
                if keyword_cleanup(autocorrect_forced) not in keywords_temp:
                    keywords_temp.append(keyword_cleanup(autocorrect_forced))
                if keyword_cleanup(autocorrect_forced) not in duplicates:
                    duplicates[keyword_cleanup(autocorrect_forced)] = 1
                    children.append({'name': keyword_cleanup(autocorrect_forced), 'type': 'autocorrect_forced', 'duplicate': False})
                else:
                    duplicates[keyword_cleanup(autocorrect_forced)] += 1
                    children.append({'name': keyword_cleanup(autocorrect_forced), 'type': 'autocorrect_forced', 'duplicate': True})

            elif autocorrect_suggested is not None:
                if keyword_cleanup(autocorrect_suggested) not in keywords_temp:
                    keywords_temp.append(keyword_cleanup(autocorrect_suggested))
                if keyword_cleanup(autocorrect_suggested) not in duplicates:
                    duplicates[keyword_cleanup(autocorrect_suggested)] = 1
                    children.append({'name': keyword_cleanup(autocorrect_suggested), 'type': 'autocorrect_suggested', 'duplicate': False})
                else:
                    duplicates[keyword_cleanup(autocorrect_suggested)] += 1
                    children.append({'name': keyword_cleanup(autocorrect_suggested), 'type': 'autocorrect_suggested', 'duplicate': True})

            if people_also_search_for is not None:
                if len(people_also_search_for) > 1:
                    people_also_search_for = people_also_search_for.split('; ')
                    for people_also_search_for_element in people_also_search_for:
                        if keyword_cleanup(people_also_search_for_element) not in keywords_temp:
                            keywords_temp.append(keyword_cleanup(people_also_search_for_element))
                        if keyword_cleanup(people_also_search_for_element) not in duplicates:
                            duplicates[keyword_cleanup(people_also_search_for_element)] = 1
                            children.append({'name': keyword_cleanup(people_also_search_for_element), 'type': 'people_also_search_for', 'duplicate': False})
                        else:
                            duplicates[keyword_cleanup(people_also_search_for_element)] += 1
                            children.append({'name': keyword_cleanup(people_also_search_for_element), 'type': 'people_also_search_for', 'duplicate': True})
                else:
                    if keyword_cleanup(people_also_search_for) not in keywords_temp:
                        keywords_temp.append(keyword_cleanup(people_also_search_for))
                    if keyword_cleanup(people_also_search_for) not in duplicates:
                        duplicates[keyword_cleanup(people_also_search_for)] = 1
                        children.append({'name': keyword_cleanup(people_also_search_for), 'type': 'people_also_search_for', 'duplicate': False})
                    else:
                        duplicates[keyword_cleanup(people_also_search_for)] += 1
                        children.append({'name': keyword_cleanup(people_also_search_for), 'type': 'people_also_search_for', 'duplicate': True})

            pointers = keyword_pointers[keyword]
            for pointer in pointers:
                if average_monthly_search_volume is not None:
                    pointer['average_monthly_search_volume'] = int(average_monthly_search_volume)
                else:
                    pointer['average_monthly_search_volume'] = 0

                if competition is not None:
                    pointer['competition'] = float(competition)
                else:
                    pointer['competition'] = 0

                pointer['children'] = children

        keywords = keywords_temp
        keywords_string = '\n'.join(keywords_temp)


        if i == n_depth - 1:
            keywords_traffic = get_traffic(keywords)
            keyword_pointers = {}
            for keyword in keywords:
                results = []
                traverse(semantic_map, keyword, results)
                keyword_pointers[keyword] = results

            for keyword in keywords:
                pointers = keyword_pointers[keyword]
                for pointer in pointers:
                    search_volume = keywords_traffic.get(keyword).get('average_monthly_search_volume')
                    competition = keywords_traffic.get(keyword).get('competition')
                    if search_volume is not None:
                        pointer['average_monthly_search_volume'] = search_volume
                    else:
                        pointer['average_monthly_search_volume'] = 0

                    if competition is not None:
                        pointer['competition'] = competition
                    else:
                        pointer['competition'] = 0

    with open('Reingold-Tilford/semantic_map.json', 'w') as outfile:
        json.dump(semantic_map, outfile, indent = 4)

    with open('Reingold-Tilford/duplicates.json', 'w') as outfile:
        json.dump(duplicates, outfile, indent = 4)


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
