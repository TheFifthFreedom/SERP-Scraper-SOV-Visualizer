# -*- coding: utf-8 -*-

import os
import collections
from googleads import adwords

def get_traffic(keyword_set):

    #Initialize client object.
    adwords_client = adwords.AdWordsClient.LoadFromStorage(os.path.abspath('googleads.yaml'))

    #Initialize appropriate service.
    targeting_idea_service = adwords_client.GetService('TargetingIdeaService', version='v201502')

    PAGE_SIZE = 100
    offset = 0

    #Construct selector object and retrieve related keywords.
    selector = {
        'searchParameters': [
            {
                'xsi_type': 'RelatedToQuerySearchParameter',
                'queries': keyword_set
            },
            {
                'xsi_type': 'NetworkSearchParameter',
                'networkSetting': [{'targetSearchNetwork': 'true'}]
            }
        ],
        'ideaType': 'KEYWORD',
        'requestType': 'STATS',
        'requestedAttributeTypes': ['KEYWORD_TEXT', 'SEARCH_VOLUME', 'AVERAGE_CPC', 'COMPETITION', 'TARGETED_MONTHLY_SEARCHES'],
        'paging': {
            'startIndex': str(offset),
            'numberResults': str(PAGE_SIZE)
        }
    }

    months = {
        1: 'January',
        2: 'February',
        3: 'March',
        4: 'April',
        5: 'May',
        6: 'June',
        7: 'July',
        8: 'August',
        9: 'September',
        10: 'October',
        11: 'November',
        12: 'December'
    }
    traffic_results = {}
    more_pages = True
    while more_pages:
        page = targeting_idea_service.get(selector)

        #Display results.
        if 'entries' in page:
            for result in page['entries']:
                attributes = {}
                traffic_result_set = {}
                for attribute in result['data']:
                    attributes[attribute['key']] = getattr(attribute['value'], 'value', '0')

                if attributes['SEARCH_VOLUME'] == '0':
                    traffic_result_set['average_monthly_search_volume'] = None
                else:
                    traffic_result_set['average_monthly_search_volume'] = attributes['SEARCH_VOLUME']

                if attributes['AVERAGE_CPC'] == '0':
                    traffic_result_set['average_cpc'] = None
                else:
                    traffic_result_set['average_cpc'] = round(attributes['AVERAGE_CPC']['microAmount'] / 1000000, 2)

                if attributes['COMPETITION'] == '0':
                    traffic_result_set['competition'] = None
                else:
                    traffic_result_set['competition'] = round(attributes['COMPETITION'], 2)

                monthly_search_volumes_set = []
                for entry in attributes['TARGETED_MONTHLY_SEARCHES']:
                    if 'count' in entry:
                        monthly_search_volumes_set.append(months[entry['month']] + ' ' + str(entry['year']) + ': ' + str(entry['count']))
                traffic_result_set['monthly_search_volumes'] = monthly_search_volumes_set

                traffic_results[attributes['KEYWORD_TEXT']] = traffic_result_set
        else:
            print ('No related keywords were found.')

        offset += PAGE_SIZE
        selector['paging']['startIndex'] = str(offset)
        more_pages = offset < int(page['totalNumEntries'])

    return traffic_results
