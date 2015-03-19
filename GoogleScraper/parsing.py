# -*- coding: utf-8 -*-

import sys
import os
import re
import lxml.html
from lxml.html.clean import Cleaner
import logging
from urllib.parse import urlparse, unquote
import pprint
from GoogleScraper.database import SearchEngineResultsPage, Link
from GoogleScraper.config import Config
from GoogleScraper.log import out
from cssselect import HTMLTranslator

logger = logging.getLogger('GoogleScraper')

class InvalidSearchTypeException(Exception):
    pass


class UnknowUrlException(Exception):
    pass


class NoParserForSearchEngineException(Exception):
    pass

class Parser():
    """Parses SERP pages.

    Each search engine results page (SERP) has a similar layout:

    The main search results are usually in a html container element (#main, .results, #leftSide).
    There might be separate columns for other search results (like ads for example). Then each
    result contains basically a link, a snippet and a description (usually some text on the
    target site). It's really astonishing how similar other search engines are to Google.

    Each child class (that can actual parse a concrete search engine results page) needs
    to specify css selectors for the different search types (Like normal search, news search, video search, ...).

    Attributes:
        search_results: The results after parsing.
    """

    # this selector specified the element that notifies the user whether the search
    # had any results.
    no_results_selector = []

    # if subclasses specify an value for this attribute and the attribute
    # targets an element in the serp page, then there weren't any results
    # for the original query.
    effective_query_selector = []

    # the selector that gets the number of results (guessed) as shown by the search engine.
    num_results_search_selectors = []

    # some search engine show on which page we currently are. If supportd, this selector will get this value.
    page_number_selectors = []

    # The supported search types. For instance, Google supports Video Search, Image Search, News search
    search_types = []

    # Autocorrect result selector
    autocorrect_selector = []
    autocorrect_forced_check_selector = []

    # Map result selector
    map_selector = []

    # Image results selector
    image_results_selector = []

    # Image mega block selector
    image_mega_block_selector = []

    # Answer box selector
    answer_box_selector = []
    answer_box_multi_selector = []

    # Knowledge Graph Thumbnail
    knowledge_graph_box_selector = []

    # Knowledge Graph Title
    knowledge_graph_title_selector = []

    # Knowledge Graph Google Review
    knowledge_graph_google_star_rating_selector = []
    knowledge_graph_google_star_rating_numbers_selector = []
    knowledge_graph_google_star_rating_big_selector = []
    knowledge_graph_google_star_rating_numbers_big_selector = []

    # Knowledge Graph Subtitle
    knowledge_graph_subtitle_selector = []
    # Knowledge Graph location-specific Subtitle
    knowledge_graph_location_subtitle_selector = []

    # Knowledge Graph Snippet
    knowledge_graph_snippet_selector = []
    # Knowledge Graph location-specific Snippet
    knowledge_graph_location_snippet_selector = []

    # Knowledge Graph Google+ Recent Post
    knowledge_graph_google_plus_recent_post_selector = []

    # Knowledge Graph Map
    knowledge_graph_map_selector = []

    # Knowledge Graph Image Thumbnail
    knowledge_graph_thumbnail_selector = []

    # Knowledge Graph Google Images Scrapbook Selector
    knowledge_graph_google_images_scrapbook_selector = []

    # Each subclass of Parser may declare an arbitrary amount of attributes that
    # follow a naming convention like this:
    # *_search_selectors
    # where the asterix may be replaced with arbitrary identifier names.
    # Any of these attributes represent css selectors for a specific search type.
    # If you didn't specify the search type in the search_types list, this attribute
    # will not be evaluated and no data will be parsed.

    def __init__(self, html=None, query=''):
        """Create new Parser instance and parse all information.

        Args:
            html: The raw html from the search engine search. If not provided, you can parse
                    the data later by calling parse(html) directly.
            searchtype: The search type. By default "normal"

        Raises:
            Assertion error if the subclassed
            specific parser cannot handle the the settings.
        """
        self.searchtype = Config['SCRAPING'].get('search_type', 'normal')
        assert self.searchtype in self.search_types, 'search type "{}" is not supported in {}'.format(self.searchtype, self.__class__.__name__)

        self.query = query
        self.html = html
        self.dom = None
        self.search_results = {}
        self.num_results_for_query = ''
        self.num_results = 0
        self.effective_query = ''
        self.page_number = -1
        self.no_results = False
        self.autocorrect = None
        self.autocorrect_forced_check = None
        self.map_result = False
        self.image_results = False
        self.image_mega_block = False
        self.answer_box = False
        self.knowledge_graph_box = False
        self.knowledge_graph_title = None
        self.knowledge_graph_google_star_rating = None
        self.knowledge_graph_google_star_rating_numbers = None
        self.knowledge_graph_google_star_rating_big = None
        self.knowledge_graph_google_star_rating_numbers_big = None
        self.knowledge_graph_subtitle = None
        self.knowledge_graph_location_subtitle = None
        self.knowledge_graph_snippet = None
        self.knowledge_graph_location_snippet = None
        self.knowledge_graph_google_plus_recent_post = None
        self.knowledge_graph_map = False
        self.knowledge_graph_thumbnail = False
        self.knowledge_graph_google_images_scrapbook = False

        # to be set by the implementing sub classes
        self.search_engine = ''

        # short alias because we use it so extensively
        self.css_to_xpath = HTMLTranslator().css_to_xpath

        if self.html:
            self.parse()

    def parse(self, html=None):
        """Public function to start parsing the search engine results.

        Args:
            html: The raw html data to extract the SERP entries from.
        """
        if html:
            self.html = html

        # lets do the actual parsing
        self._parse()

        # Apply subclass specific behaviour after parsing has happened
        # This is needed because different parsers need to clean/modify
        # the parsed data uniquely.
        self.after_parsing()

    def _parse_lxml(self, cleaner=None):
        try:
            parser = lxml.html.HTMLParser(encoding='utf-8')
            if cleaner:
                self.dom = cleaner.clean_html(self.dom)
            self.dom = lxml.html.document_fromstring(self.html, parser=parser)
            self.dom.resolve_base_href()
        except Exception as e:
            # maybe wrong encoding
            logger.error(e)

    def _parse(self, cleaner=None):
        """Internal parse the dom according to the provided css selectors.

        Raises: InvalidSearchTypeException if no css selectors for the searchtype could be found.
        """
        self._parse_lxml(cleaner)

        # try to parse the number of results.
        attr_name = self.searchtype + '_search_selectors'
        selector_dict = getattr(self, attr_name, None)

        # get the appropriate css selectors for the num_results for the keyword
        num_results_selector = getattr(self, 'num_results_search_selectors', None)

        self.num_results_for_query = self.first_match(num_results_selector, self.dom)
        if not self.num_results_for_query:
            out('{}: Cannot parse num_results from serp page with selectors {}'.format(self.__class__.__name__, num_results_selector), lvl=4)

        # get the current page we are at. Sometimes we search engines don't show this.
        try:
            self.page_number = int(self.first_match(self.page_number_selectors, self.dom))
        except ValueError as e:
            self.page_number = -1

        # let's see if the search query was shitty (no results for that query)
        self.effective_query = self.first_match(self.effective_query_selector, self.dom)
        if self.effective_query:
            out('{}: There was no search hit for the search query. Search engine used {} instead.'.format(self.__class__.__name__, self.effective_query), lvl=4)

        # the element that notifies the user about no results.
        self.no_results_text = self.first_match(self.no_results_selector, self.dom)

        # check for autocorrect results
        if self.first_match(self.autocorrect_selector, self.dom) != '' and self.first_match(self.autocorrect_selector, self.dom) != False:
            self.autocorrect = self.first_match(self.autocorrect_selector, self.dom)
        if self.first_match(self.autocorrect_forced_check_selector, self.dom) != '' and self.first_match(self.autocorrect_forced_check_selector, self.dom) != False:
            self.autocorrect_forced_check = self.first_match(self.autocorrect_forced_check_selector, self.dom)

        # check for a map result
        if self.first_match(self.map_selector, self.dom) != False:
            self.map_result = True

        # check for image results
        if self.first_match(self.image_mega_block_selector, self.dom) != False:
            self.image_mega_block = True
        elif self.first_match(self.image_results_selector, self.dom) != False:
            self.image_results = True

        # check for answer box
        if self.first_match(self.answer_box_selector, self.dom) != False or self.first_match(self.answer_box_multi_selector, self.dom) != False:
            self.answer_box = True

        self.knowledge_graph_box = (True if self.first_match(self.knowledge_graph_box_selector, self.dom) != False else False)
        self.knowledge_graph_title = self.first_match(self.knowledge_graph_title_selector, self.dom)
        self.knowledge_graph_google_star_rating = (self.first_match(self.knowledge_graph_google_star_rating_selector, self.dom) if self.first_match(self.knowledge_graph_google_star_rating_selector, self.dom) != False else None)
        self.knowledge_graph_google_star_rating_numbers = (self.first_match(self.knowledge_graph_google_star_rating_numbers_selector, self.dom) if self.first_match(self.knowledge_graph_google_star_rating_numbers_selector, self.dom) != False else None)
        self.knowledge_graph_google_star_rating_big = (self.first_match(self.knowledge_graph_google_star_rating_big_selector, self.dom) if self.first_match(self.knowledge_graph_google_star_rating_big_selector, self.dom) != False else None)
        self.knowledge_graph_google_star_rating_numbers_big = (self.first_match(self.knowledge_graph_google_star_rating_numbers_big_selector, self.dom) if self.first_match(self.knowledge_graph_google_star_rating_numbers_big_selector, self.dom) != False else None)
        self.knowledge_graph_subtitle = (self.first_match(self.knowledge_graph_subtitle_selector, self.dom) if self.first_match(self.knowledge_graph_subtitle_selector, self.dom) != False else None)
        self.knowledge_graph_location_subtitle = (self.first_match(self.knowledge_graph_location_subtitle_selector, self.dom) if self.first_match(self.knowledge_graph_location_subtitle_selector, self.dom) != False else None)
        self.knowledge_graph_snippet = (self.first_match(self.knowledge_graph_snippet_selector, self.dom) if self.first_match(self.knowledge_graph_snippet_selector, self.dom) != False else None)
        self.knowledge_graph_location_snippet = (self.first_match(self.knowledge_graph_location_snippet_selector, self.dom) if self.first_match(self.knowledge_graph_location_snippet_selector, self.dom) != False else None)
        self.knowledge_graph_google_plus_recent_post = (self.first_match(self.knowledge_graph_google_plus_recent_post_selector, self.dom) if self.first_match(self.knowledge_graph_google_plus_recent_post_selector, self.dom) != False else None)
        self.knowledge_graph_map = (True if self.first_match(self.knowledge_graph_map_selector, self.dom) != False else False)
        self.knowledge_graph_thumbnail = (True if self.first_match(self.knowledge_graph_thumbnail_selector, self.dom) != False else False)
        self.knowledge_graph_google_images_scrapbook = (True if self.first_match(self.knowledge_graph_google_images_scrapbook_selector, self.dom) != False else False)

        # get the stuff that is of interest in SERP pages.
        if not selector_dict and not isinstance(selector_dict, dict):
            raise InvalidSearchTypeException('There is no such attribute: {}. No selectors found'.format(attr_name))

        for result_type, selector_class in selector_dict.items():

            self.search_results[result_type] = []

            for selector_specific, selectors in selector_class.items():

                if 'result_container' in selectors and selectors['result_container']:
                    css = '{container} {result_container}'.format(**selectors)
                else:
                    css = selectors['container']

                results = self.dom.xpath(
                    self.css_to_xpath(css)
                )

                to_extract = set(selectors.keys()) - {'container', 'result_container'}
                selectors_to_use = {key: selectors[key] for key in to_extract if key in selectors.keys()}

                for index, result in enumerate(results):
                    # Let's add primitive support for CSS3 pseudo selectors
                    # We just need two of them
                    # ::text
                    # ::attr(attribute)

                    # You say we should use xpath expressions instead?
                    # Maybe you're right, but they are complicated when it comes to classes,
                    # have a look here: http://doc.scrapy.org/en/latest/topics/selectors.html
                    serp_result = {}
                    # key are for example 'link', 'snippet', 'visible-url', ...
                    # selector is the selector to grab these items
                    for key, selector in selectors_to_use.items():
                        serp_result[key] = self.advanced_css(selector, result)

                    serp_result['rank'] = index+1

                    # only add items that have not None links.
                    # Avoid duplicates. Detect them by the link.
                    # Except for local pack results - detect those by their address
                    # If statements below: Lazy evaluation. The more probable case first.
                    if result_type == 'local_pack_results' and 'address' in serp_result and serp_result['address'] and \
                            not [e for e in self.search_results[result_type] if e['address'] == serp_result['address']]:
                        self.search_results[result_type].append(serp_result)
                        self.num_results += 1

                    elif result_type == 'knowledge_graph_trivia' and 'title' in serp_result and serp_result['title'] and \
                            not [e for e in self.search_results[result_type] if e['title'] == serp_result['title']]:
                        self.search_results[result_type].append(serp_result)

                    elif result_type == 'knowledge_graph_trivia' and 'link_title' in serp_result and serp_result['link_title'] and \
                            not [e for e in self.search_results[result_type] if e['link_title'] == serp_result['link_title']]:
                        self.search_results[result_type].append(serp_result)

                    elif result_type == 'knowledge_graph_trivia' and 'hours_title' in serp_result and serp_result['hours_title'] and \
                            not [e for e in self.search_results[result_type] if e['hours_title'] == serp_result['hours_title']]:
                        self.search_results[result_type].append(serp_result)

                    elif 'link' in serp_result and serp_result['link'] and \
                            not [e for e in self.search_results[result_type] if e['link'] == serp_result['link']]:
                        self.search_results[result_type].append(serp_result)
                        self.num_results += 1


    def advanced_css(self, selector, element):
        """Evaluate the :text and ::attr(attr-name) additionally.

        Args:
            selector: A css selector.
            element: The element on which to apply the selector.

        Returns:
            The targeted element.

        """
        value = None

        if selector.endswith('::text'):
            try:
                value = element.xpath(self.css_to_xpath(selector.split('::')[0]))[0].text_content()
            except IndexError as e:
                pass
        else:
            match = re.search(r'::attr\((?P<attr>.*)\)$', selector)

            if match:
                attr = match.group('attr')
                try:
                    value = element.xpath(self.css_to_xpath(selector.split('::')[0]))[0].get(attr)
                except IndexError as e:
                    pass
            else:
                try:
                    value = element.xpath(self.css_to_xpath(selector))[0]
                except IndexError as e:
                    pass

        return value


    def first_match(self, selectors, element):
        """Get the first match.

        Args:
            selectors: The selectors to test for a match.
            element: The element on which to apply the selectors.

        Returns:
            The very first match or False if all selectors didn't match anything.
        """
        assert isinstance(selectors, list), 'selectors must be of type list!'

        for selector in selectors:
            if selector:
                try:
                    match = self.advanced_css(selector, element=element)
                    if match is not None:
                        return match
                except IndexError as e:
                    pass

        return False

    def after_parsing(self):
        """Subclass specific behaviour after parsing happened.

        Override in subclass to add search engine specific behaviour.
        Commonly used to clean the results.
        """

    def __str__(self):
        """Return a nicely formatted overview of the results."""
        return pprint.pformat(self.search_results)

    @property
    def cleaned_html(self):
        # Try to parse the provided HTML string using lxml
        # strip all unnecessary information to save space
        cleaner = Cleaner()
        cleaner.scripts = True
        cleaner.javascript = True
        cleaner.comments = True
        cleaner.style = True
        self.dom = cleaner.clean_html(self.dom)
        assert len(self.dom), 'The html needs to be parsed to get the cleaned html'
        return lxml.html.tostring(self.dom)


    def iter_serp_items(self):
        """Yields the key and index of any item in the serp results that has a link value"""

        for key, value in self.search_results.items():
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict) and item['link']:
                        yield (key, i)

"""
Here follow the different classes that provide CSS selectors
for different types of SERP pages of several common search engines.

Just look at them and add your own selectors in a new class if you
want the Scraper to support them.

You can easily just add new selectors to a search engine. Just follow
the attribute naming convention and the parser will recognize them:

If you provide a dict with a name like finance_search_selectors,
then you're adding a new search type with the name finance.

Each class needs a attribute called num_results_search_selectors, that
extracts the number of searches that were found by the keyword.

Please note:
The actual selectors are wrapped in a dictionary to clarify with which IP
they were requested. The key to the wrapper div allows to specify distinct
criteria to whatever settings you used when you requested the page. So you
might add your own selectors for different User-Agents, distinct HTTP headers, what-
ever you may imagine. This allows the most dynamic parsing behaviour and makes
it very easy to grab all data the site has to offer.
"""


class GoogleParser(Parser):
    """Parses SERP pages of the Google search engine."""

    search_engine = 'google'

    search_types = ['normal', 'image']

    effective_query_selector = ['#topstuff .med > b::text']

    no_results_selector = []

    num_results_search_selectors = ['#resultStats::text']

    page_number_selectors = ['#navcnt td.cur::text']

    autocorrect_selector = ['div.med a.spell::text']
    autocorrect_forced_check_selector = ['div.med a.spell_orig::text']

    map_selector = ['div._LPe.rhsvw._CC']

    image_results_selector = ['#imagebox_bigimages']

    image_mega_block_selector = ['ul.rg_ul > li._ZGc.bili.uh_r.rg_el:nth-child(9)']

    answer_box_selector = ['#center_col li.g.mnr-c.g-blk']
    answer_box_multi_selector = ['div.rl_container']

    knowledge_graph_box_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk']

    knowledge_graph_title_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk div.kno-ecr-pt.kno-fb-ctx::text']

    knowledge_graph_google_star_rating_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk div._j3d span.rtng::text']
    knowledge_graph_google_star_rating_numbers_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk div._j3d a.fl::text']
    knowledge_graph_google_star_rating_big_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk div._i3d span.rtng::text']
    knowledge_graph_google_star_rating_numbers_big_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk div._i3d a.fl::text']

    knowledge_graph_subtitle_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk div._gdf.kno-fb-ctx::text']
    knowledge_graph_location_subtitle_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk div._mr._Wfc.vk_gy::text']

    knowledge_graph_snippet_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk div.kno-rdesc > span:first-child::text']
    knowledge_graph_location_snippet_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk span._N1d::text']

    knowledge_graph_google_plus_recent_post_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk div._b4 div.s > div:last-child::text']

    knowledge_graph_map_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk #lu_map']

    knowledge_graph_thumbnail_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk img.iuth']

    knowledge_graph_google_images_scrapbook_selector = ['#rhs li.g.mnr-c.rhsvw.g-blk div._iH']

    normal_search_selectors = {
        'organic_results': {
            'us_ip': {
                'container': '#center_col',
                'result_container': 'li.g:not(li.g.card-section):not(li.g.no-sep):not(li#imagebox_bigimages.g):not(li.g.mnr-c.g-blk)',
                'link': 'h3.r > a:first-child::attr(href)',
                'snippet': 'div.s span.st::text',
                'title': 'h3.r > a:first-child::text',
                'visible_link': 'cite::text',
                'google_star_rating': '#lclbox span.rtng::text',
                'google_star_rating_reviews' : '#lclbox > a.fl > span::text',
                'address': '#lclbox table.ts.intrlu > tbody > tr > td:last-child::text',
                'search_bar': '#nqsbq',
                'schema_enhanced_listing': 'div.s div.f.slp::text',
                'image_thumbnail': 'div.s div.th._lyb',
                'video_thumbnail': 'div.s div.th._lyb._YQd',
                'small_sitelink_1': 'div.osl > a.fl:nth-child(1)::text',
                'small_sitelink_2': 'div.osl > a.fl:nth-child(2)::text',
                'small_sitelink_3': 'div.osl > a.fl:nth-child(3)::text',
                'small_sitelink_4': 'div.osl > a.fl:nth-child(4)::text',
                'small_sitelink_5': 'div.osl > a.fl:nth-child(5)::text',
                'small_sitelink_6': 'div.osl > a.fl:nth-child(6)::text',
                'big_sitelink_1': 'tbody > tr.mslg._Amc > td:first-child h3.r > a.l::text',
                'big_sitelink_1_description': 'tbody > tr.mslg._Amc > td:first-child div.st::text',
                'big_sitelink_2': 'tbody > tr.mslg._Amc > td:last-child h3.r > a.l::text',
                'big_sitelink_2_description': 'tbody > tr.mslg._Amc > td:last-child div.st::text',
                'big_sitelink_3': 'tbody > tr.mslg._Amc + tr.mslg > td:first-child h3.r > a.l::text',
                'big_sitelink_3_description': 'tbody > tr.mslg._Amc + tr.mslg > td:first-child div.st::text',
                'big_sitelink_4': 'tbody > tr.mslg._Amc + tr.mslg > td:last-child h3.r > a.l::text',
                'big_sitelink_4_description': 'tbody > tr.mslg._Amc + tr.mslg > td:last-child div.st::text',
                'big_sitelink_5': 'tbody > tr.mslg._Amc + tr.mslg + tr.mslg > td:first-child h3.r > a.l::text',
                'big_sitelink_5_description': 'tbody > tr.mslg._Amc + tr.mslg + tr.mslg > td:first-child div.st::text',
                'big_sitelink_6': 'tbody > tr.mslg._Amc + tr.mslg + tr.mslg > td:last-child h3.r > a.l::text',
                'big_sitelink_6_description': 'tbody > tr.mslg._Amc + tr.mslg + tr.mslg > td:last-child div.st::text'
            },
            'de_ip': {
                'container': '#center_col',
                'result_container': 'li.g:not(li.g.card-section):not(li.g.no-sep):not(li#imagebox_bigimages.g):not(li.g.mnr-c.g-blk)',
                'link': 'h3.r > a:first-child::attr(href)',
                'snippet': 'div.s span.st::text',
                'title': 'h3.r > a:first-child::text',
                'visible_link': 'cite::text',
                'google_star_rating': '#lclbox span.rtng::text',
                'google_star_rating_reviews' : '#lclbox > a.fl > span::text',
                'address': '#lclbox table.ts.intrlu > tbody > tr > td:last-child::text',
                'search_bar': '#nqsbq',
                'schema_enhanced_listing': 'div.s div.f.slp::text',
                'image_thumbnail': 'div.s div.th._lyb',
                'video_thumbnail': 'div.s div.th._lyb._YQd',
                'small_sitelink_1': 'div.osl > a.fl:nth-child(1)::text',
                'small_sitelink_2': 'div.osl > a.fl:nth-child(2)::text',
                'small_sitelink_3': 'div.osl > a.fl:nth-child(3)::text',
                'small_sitelink_4': 'div.osl > a.fl:nth-child(4)::text',
                'small_sitelink_5': 'div.osl > a.fl:nth-child(5)::text',
                'small_sitelink_6': 'div.osl > a.fl:nth-child(6)::text',
                'big_sitelink_1': 'tbody > tr.mslg._Amc > td:first-child h3.r > a.l::text',
                'big_sitelink_1_description': 'tbody > tr.mslg._Amc > td:first-child div.st::text',
                'big_sitelink_2': 'tbody > tr.mslg._Amc > td:last-child h3.r > a.l::text',
                'big_sitelink_2_description': 'tbody > tr.mslg._Amc > td:last-child div.st::text',
                'big_sitelink_3': 'tbody > tr.mslg._Amc + tr.mslg > td:first-child h3.r > a.l::text',
                'big_sitelink_3_description': 'tbody > tr.mslg._Amc + tr.mslg > td:first-child div.st::text',
                'big_sitelink_4': 'tbody > tr.mslg._Amc + tr.mslg > td:last-child h3.r > a.l::text',
                'big_sitelink_4_description': 'tbody > tr.mslg._Amc + tr.mslg > td:last-child div.st::text',
                'big_sitelink_5': 'tbody > tr.mslg._Amc + tr.mslg + tr.mslg > td:first-child h3.r > a.l::text',
                'big_sitelink_5_description': 'tbody > tr.mslg._Amc + tr.mslg + tr.mslg > td:first-child div.st::text',
                'big_sitelink_6': 'tbody > tr.mslg._Amc + tr.mslg + tr.mslg > td:last-child h3.r > a.l::text',
                'big_sitelink_6_description': 'tbody > tr.mslg._Amc + tr.mslg + tr.mslg > td:last-child div.st::text'
            }
        },
        'paid_results': {
            'us_ip': {
                'container': 'li.ads-ad',
                'link': 'h3 > a+a:first-child::attr(href)',
                'snippet': '.ads-creative::text',
                'title': 'h3 > a+a:first-child::text',
                'visible_link': '.ads-visurl cite::text',
                'google_star_rating': 'span._uEc::text',
                'address': 'div._wnd > div._H2b:last-child > a._vnd::text',
                'phone_number': 'div._wnd > div._H2b:last-child > div._K2b > span._xnd::text',
                'small_sitelink_1': 'ul:last-child > li:nth-child(1) > a::text',
                'small_sitelink_2': 'ul:last-child > li:nth-child(2) > a::text',
                'small_sitelink_3': 'ul:last-child > li:nth-child(3) > a::text',
                'small_sitelink_4': 'ul:last-child > li:nth-child(4) > a::text',
                'small_sitelink_5': 'ul:last-child > li:nth-child(5) > a::text',
                'small_sitelink_6': 'ul:last-child > li:nth-child(6) > a::text',
                'big_sitelink_1': 'ul:last-child > li:nth-child(1) > h3 > a::text',
                'big_sitelink_1_description': 'ul:last-child > li:nth-child(1) > div.ads-creative.ac::text',
                'big_sitelink_2': 'ul:last-child > li:nth-child(2) > h3 > a::text',
                'big_sitelink_2_description': 'ul:last-child > li:nth-child(2) > div.ads-creative.ac::text',
                'big_sitelink_3': 'ul:last-child > li:nth-child(3) > h3 > a::text',
                'big_sitelink_3_description': 'ul:last-child > li:nth-child(3) > div.ads-creative.ac::text',
                'big_sitelink_4': 'ul:last-child > li:nth-child(4) > h3 > a::text',
                'big_sitelink_4_description': 'ul:last-child > li:nth-child(4) > div.ads-creative.ac::text',
                'big_sitelink_5': 'ul:last-child > li:nth-child(5) > h3 > a::text',
                'big_sitelink_5_description': 'ul:last-child > li:nth-child(5) > div.ads-creative.ac::text',
                'big_sitelink_6': 'ul:last-child > li:nth-child(6) > h3 > a::text',
                'big_sitelink_6_description': 'ul:last-child > li:nth-child(6) > div.ads-creative.ac::text'
            },
            'de_ip': {
                'container': 'li.ads-ad',
                'link': 'h3 > a+a:first-child::attr(href)',
                'snippet': '.ads-creative::text',
                'title': 'h3 > a+a:first-child::text',
                'visible_link': '.ads-visurl cite::text',
                'google_star_rating': 'span._uEc::text',
                'address': 'div._wnd > div._H2b:last-child > a._vnd::text',
                'phone_number': 'div._wnd > div._H2b:last-child > div._K2b > span._xnd::text',
                'small_sitelink_1': 'ul:last-child > li:nth-child(1) > a::text',
                'small_sitelink_2': 'ul:last-child > li:nth-child(2) > a::text',
                'small_sitelink_3': 'ul:last-child > li:nth-child(3) > a::text',
                'small_sitelink_4': 'ul:last-child > li:nth-child(4) > a::text',
                'small_sitelink_5': 'ul:last-child > li:nth-child(5) > a::text',
                'small_sitelink_6': 'ul:last-child > li:nth-child(6) > a::text',
                'big_sitelink_1': 'ul:last-child > li:nth-child(1) > h3 > a::text',
                'big_sitelink_1_description': 'ul:last-child > li:nth-child(1) > div.ads-creative.ac::text',
                'big_sitelink_2': 'ul:last-child > li:nth-child(2) > h3 > a::text',
                'big_sitelink_2_description': 'ul:last-child > li:nth-child(2) > div.ads-creative.ac::text',
                'big_sitelink_3': 'ul:last-child > li:nth-child(3) > h3 > a::text',
                'big_sitelink_3_description': 'ul:last-child > li:nth-child(3) > div.ads-creative.ac::text',
                'big_sitelink_4': 'ul:last-child > li:nth-child(4) > h3 > a::text',
                'big_sitelink_4_description': 'ul:last-child > li:nth-child(4) > div.ads-creative.ac::text',
                'big_sitelink_5': 'ul:last-child > li:nth-child(5) > h3 > a::text',
                'big_sitelink_5_description': 'ul:last-child > li:nth-child(5) > div.ads-creative.ac::text',
                'big_sitelink_6': 'ul:last-child > li:nth-child(6) > h3 > a::text',
                'big_sitelink_6_description': 'ul:last-child > li:nth-child(6) > div.ads-creative.ac::text'
            }
        },
        'shopping_results (left)': {
            'us_ip': {
                'container': 'div.c.commercial-unit.commercial-unit-desktop-top',
                'result_container': 'div.pla-unit',
                'link': 'div._vT > a:first-child::attr(href)',
                'title': 'div._vT > a:first-child::text',
                'price': 'div._QD::text',
                'image_thumbnail': 'span._qYc',
                'visible_link': 'div._mC > span.a::text'
            },
            'de_ip': {
                'container': 'div.c.commercial-unit.commercial-unit-desktop-top',
                'result_container': 'div.pla-unit',
                'link': 'div._vT > a:first-child::attr(href)',
                'title': 'div._vT > a:first-child::text',
                'price': 'div._QD::text',
                'image_thumbnail': 'span._qYc',
                'visible_link': 'div._mC > span.a::text'
            }
        },
        'shopping_results (right)': {
            'us_ip': {
                'container': 'div.c.commercial-unit.commercial-unit-desktop-rhs.rhsvw',
                'result_container': 'div.pla-unit',
                'link': 'div._vT > a:first-child::attr(href)',
                'title': 'div._vT > a:first-child > span.rhsg4::text',
                'price': 'div._QD::text',
                'image_thumbnail': 'span._qYc',
                'visible_link': 'div._mC > span.rhsg4.a::text'
            },
            'de_ip': {
                'container': 'div.c.commercial-unit.commercial-unit-desktop-rhs.rhsvw',
                'result_container': 'div.pla-unit',
                'link': 'div._vT > a:first-child::attr(href)',
                'title': 'div._vT > a:first-child > span.rhsg4::text',
                'price': 'div._QD::text',
                'image_thumbnail': 'span._qYc',
                'visible_link': 'div._mC > span.rhsg4.a::text'
            }
        },
        'news_results': {
            'us_ip': {
                'container': 'div.mnr-c._yE',
                'result_container': 'li.g',
                'link': 'a._Dk::attr(href)',
                'snippet': 'span._dwd.st.s.std::text',
                'title': 'a._Dk::text',
                'image_thumbnail': 'div._K2._SYd',
                'visible_link': 'cite::text'
            },
            'de_ip': {
                'container': 'div.mnr-c._yE',
                'result_container': 'li.g',
                'link': 'a._Dk::attr(href)',
                'snippet': 'span._dwd.st.s.std::text',
                'title': 'a._Dk::text',
                'image_thumbnail': 'div._K2._SYd',
                'visible_link': 'cite::text'
            }
        },
        'in_depth_articles': {
            'us_ip': {
                'container': '#center_col',
                'result_container': 'li.g.card-section:not(li.card-section._df.g._mZd):not(li.g._Nn._wbb.card-section):not(li.g._Nn._Abb.card-section)',
                'link': 'h3.r > a:first-child::attr(href)',
                'snippet': 'div.s span.st::text',
                'title': 'h3.r > a:first-child::text',
                'image_thumbnail': 'div.th._lyb',
                'visible_link': 'cite::text',
            },
            'de_ip': {
                'container': '#center_col',
                'result_container': 'li.g.card-section:not(li.card-section._df.g._mZd):not(li.g._Nn._wbb.card-section):not(li.g._Nn._Abb.card-section)',
                'link': 'h3.r > a:first-child::attr(href)',
                'snippet': 'div.s span.st::text',
                'title': 'h3.r > a:first-child::text',
                'image_thumbnail': 'div.th._lyb',
                'visible_link': 'cite::text',
            }
        },
        'local_carousel': {
            'us_ip': {
                'container': '#extabar',
                'result_container': 'li',
                'link': 'a:first-child::attr(href)',
                'title': 'a:first-child::attr(title)',
                'image_thumbnail': 'div.klic'
            },
            'de_ip': {
                'container': '#extabar',
                'result_container': 'li',
                'link': 'a:first-child::attr(href)',
                'title': 'a:first-child::attr(title)',
                'image_thumbnail': 'div.klic'
            }
        },
        'local_pack_results': {
            'us_ip': {
                'container': 'li.g.no-sep',
                'result_container': 'div.intrlu',
                'link': 'h3.r > a:first-child::attr(href)',
                'title': 'h3.r > a:first-child::text',
                'visible_link': 'cite::text',
                'google_star_rating': 'span.rtng::text',
                'google_star_rating_reviews': 'a.fl::text',
                'address': 'div.g > div:last-child::text'
            },
            'de_ip': {
                'container': 'li.g.no-sep',
                'result_container': 'div.intrlu',
                'link': 'h3.r > a:first-child::attr(href)',
                'title': 'h3.r > a:first-child::text',
                'visible_link': 'cite::text',
                'google_star_rating': 'span.rtng::text',
                'google_star_rating_reviews': 'a.fl::text',
                'address': 'div.g > div:last-child::text'
            }
        },
        'list_carousel': {
            'us_ip': {
                'container': 'div._oL',
                'result_container': 'div._gt',
                'link': 'a:first-child::attr(href)',
                'snippet': 'span._ucf::text',
                'title': 'div._rl::text',
                'google_star_rating': 'span.rtng::text',
                'google_star_rating_reviews': 'span._Mnc.vk_lt::text',
                'schema_enhanced_listing': 'div._CRe > div::text',
                'price': 'div._Nl::text',
                'image_thumbnail': 'div._li'
            },
            'de_ip': {
                'container': 'div._oL',
                'result_container': 'div._gt',
                'link': 'a:first-child::attr(href)',
                'snippet': 'span._ucf::text',
                'title': 'div._rl::text',
                'google_star_rating': 'span.rtng::text',
                'google_star_rating_reviews': 'span._Mnc.vk_lt::text',
                'schema_enhanced_listing': 'div._CRe > div::text',
                'price': 'div._Nl::text',
                'image_thumbnail': 'div._li'
            }
        },
        'related_searches': {
            'us_ip': {
                'container': '#extrares',
                'result_container': 'p._e4b',
                'keyword': 'a:first-child::text',
                'link': 'a:first-child::attr(href)'
            },
            'de_ip': {
                'container': '#extrares',
                'result_container': 'p._e4b',
                'keyword': 'a:first-child::text',
                'link': 'a:first-child::attr(href)'
            }
        },
        'disambiguation_box': {
            'us_ip': {
                'container': 'div._OKe',
                'result_container': 'li.fwm._NXc._DJe.mod',
                'keyword': 'div._Z3 > div._Qqb._tX.ellip::text',
                'link': 'div.kno-fb-ctx > a:first-child::attr(href)',
                'snippet': 'div._Z3 > div._Adb > span.rhsg4::text',
                'snippet[0][0]': 'div._Z3 > div._Adb > div._mr.ellip:first-child > span:first-child::text',
                'snippet[0][1]': 'div._Z3 > div._Adb > div._mr.ellip:first-child > span:last-child::text',
                'snippet[1][0]': 'div._Z3 > div._Adb > div._mr.ellip:last-child > span:first-child::text',
                'snippet[1][1]': 'div._Z3 > div._Adb > div._mr.ellip:last-child > span:last-child::text'
            },
            'de_ip': {
                'container': 'div._OKe',
                'result_container': 'li.fwm._NXc._DJe.mod',
                'keyword': 'div._Z3 > div._Qqb._tX.ellip::text',
                'link': 'div.kno-fb-ctx > a:first-child::attr(href)',
                'snippet': 'div._Z3 > div._Adb > span.rhsg4::text',
                'snippet[0][0]': 'div._Z3 > div._Adb > div._mr.ellip:first-child > span:first-child::text',
                'snippet[0][1]': 'div._Z3 > div._Adb > div._mr.ellip:first-child > span:last-child::text',
                'snippet[1][0]': 'div._Z3 > div._Adb > div._mr.ellip:last-child > span:first-child::text',
                'snippet[1][1]': 'div._Z3 > div._Adb > div._mr.ellip:last-child > span:last-child::text'
            }
        },
        'knowledge_graph_trivia': {
            'us_ip': {
                'container': 'div._mr',
                'title': 'span:first-child::text',
                'link_title': 'a.fl:first-child::text',
                'fact': 'span:last-child::text',
                'link_fact': 'a.fl:last-child::text',
                'hours_title': 'div.lud-hourslabel::text',
                'hours_status': 'span._CK::text',
                'hours_status_grayscale': 'span._bC::text',
                'hours_morning': 'a.fl > span:first-child::text',
                'hours_afternoon': 'a.fl > span:last-child::text',
                'link': 'a.fl::attr(href)'
            },
            'de_ip': {
                'container': 'div._mr',
                'title': 'span:first-child::text',
                'link_title': 'a.fl:first-child::text',
                'fact': 'span:last-child::text',
                'link_fact': 'a.fl:last-child::text',
                'hours_title': 'div.lud-hourslabel::text',
                'hours_status': 'span._CK::text',
                'hours_status_grayscale': 'span._bC::text',
                'hours_morning': 'a.fl > span:first-child::text',
                'hours_afternoon': 'a.fl > span:last-child::text',
                'link': 'a.fl::attr(href)'
            }
        },
        'knowledge_graph_social_profiles': {
            'us_ip': {
                'container': 'ul._Ugf',
                'result_container': 'li.kno-vrt-t.kno-fb-ctx',
                'profile': 'a.fl::text',
                'link': 'a.fl::attr(href)'
            },
            'de_ip': {
                'container': 'ul._Ugf',
                'result_container': 'li.kno-vrt-t.kno-fb-ctx',
                'profile': 'a.fl::text',
                'link': 'a.fl::attr(href)'
            }
        },
        'knowledge_graph_google_plus_reviews': {
            'us_ip': {
                'container': 'div._PJb',
                'review': 'div._RJb::text',
                'link': 'img._NJb::attr(src)'
            },
            'de_ip': {
                'container': 'div._PJb',
                'review': 'div._RJb::text',
                'link': 'img._NJb::attr(src)'
            }
        },
        'knowledge_graph_features': {
            'us_ip': {
                'container': '#rhs li.g.mnr-c.rhsvw.g-blk',
                'institution': 'span._mP::text',
                'feature': '#pl_ffl > a.fl::text',
                'link': '#pl_ffl > a.fl::attr(href)'
            },
            'de_ip': {
                'container': '#rhs li.g.mnr-c.rhsvw.g-blk',
                'institution': 'span._mP::text',
                'feature': '#pl_ffl > a.fl::text',
                'link': '#pl_ffl > a.fl::attr(href)'
            }
        },
        'knowledge_graph_people_also_search_for': {
            'us_ip': {
                'container': 'div._c4',
                'result_container': 'div.kno-fb-ctx.kno-vrt-t',
                'keyword': 'a.fl.ellip._Wqb::text',
                'link': 'a.fl.ellip._Wqb::attr(href)'
            },
            'de_ip': {
                'container': 'div._c4',
                'result_container': 'div.kno-fb-ctx.kno-vrt-t',
                'keyword': 'a.fl.ellip._Wqb::text',
                'link': 'a.fl.ellip._Wqb::attr(href)'
            }
        },
        'knowledge_graph_slideshows': {
            'us_ip': {
                'container': '#rhs li.g.mnr-c.rhsvw.g-blk',
                'result_container': 'div.thumb',
                'slideshow': 'span.cptn::text',
                'link': 'a::attr(href)'
            },
            'de_ip': {
                'container': '#rhs li.g.mnr-c.rhsvw.g-blk',
                'result_container': 'div.thumb',
                'slideshow': 'span.cptn::text',
                'link': 'a::attr(href)'
            }
        }
    }

    image_search_selectors = {
        'results': {
            'de_ip': {
                'container': 'li#isr_mc',
                'result_container': 'div.rg_di',
                'link': 'a.rg_l::attr(href)'
            },
            'de_ip_raw': {
                'container': '.images_table',
                'result_container': 'tr td',
                'link': 'a::attr(href)',
                'visible_link': 'cite::text',
            }
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def after_parsing(self):
        """Clean the urls.

        A typical scraped results looks like the following:

        '/url?q=http://www.youtube.com/user/Apple&sa=U&ei=lntiVN7JDsTfPZCMgKAO&ved=0CFQQFjAO&usg=AFQjCNGkX65O-hKLmyq1FX9HQqbb9iYn9A'

        Clean with a short regex.
        """
        super().after_parsing()

        if self.searchtype == 'normal':
            if self.num_results > 0:
                self.no_results = False
            elif self.num_results <= 0:
                self.no_results = True

            if 'No results found for' in self.html or 'did not match any documents' in self.html:
                self.no_results = True

            # finally try in the snippets
            if self.no_results is True:
                for key, i in self.iter_serp_items():

                    if 'snippet' in self.search_results[key][i] and self.query:
                        if self.query.replace('"', '') in self.search_results[key][i]['snippet']:
                            self.no_results = False


        clean_regexes = {
            'normal': r'/url\?q=(?P<url>.*?)&sa=U&ei=',
            'image': r'imgres\?imgurl=(?P<url>.*?)&'
        }

        for key, i in self.iter_serp_items():
            result = re.search(
                clean_regexes[self.searchtype],
                self.search_results[key][i]['link']
            )
            if result:
                self.search_results[key][i]['link'] = unquote(result.group('url'))


class YandexParser(Parser):
    """Parses SERP pages of the Yandex search engine."""

    search_engine = 'yandex'

    search_types = ['normal', 'image']

    no_results_selector = ['.message .misspell__message::text']

    effective_query_selector = ['.misspell__message .misspell__link']

    num_results_search_selectors = ['.serp-adv .serp-item__wrap > strong']

    page_number_selectors = ['.pager__group .button_checked_yes span::text']

    autocorrect_selector = [] #TO DO
    autocorrect_forced_check_selector = [] #TO DO

    map_selector = [] #TO DO

    image_results_selector = [] #TO DO

    image_mega_block_selector = [] #TO DO

    answer_box_selector = [] #TO DO

    answer_box_multi_selector = [] #TO DO

    knowledge_graph_box_selector = [] #TO DO

    knowledge_graph_title_selector = [] #TO DO

    knowledge_graph_google_star_rating_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_selector = [] #TO DO

    knowledge_graph_google_star_rating_big_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_big_selector = [] #TO DO

    knowledge_graph_subtitle_selector = [] #TO DO

    knowledge_graph_location_subtitle_selector = [] #TO DO

    knowledge_graph_snippet_selector = [] #TO DO

    knowledge_graph_location_snippet_selector = [] #TO DO

    knowledge_graph_google_plus_recent_post_selector = [] #TO DO

    knowledge_graph_map_selector = [] #TO DO

    knowledge_graph_thumbnail_selector = [] #TO DO

    knowledge_graph_google_images_scrapbook_selector = [] #TO DO

    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': 'div.serp-list',
                'result_container': 'div.serp-item__wrap ',
                'link': 'a.serp-item__title-link::attr(href)',
                'snippet': 'div.serp-item__text::text',
                'title': 'a.serp-item__title-link::text',
                'visible_link': 'a.serp-url__link::attr(href)'
            }
        }
    }

    image_search_selectors = {
        'results': {
            'de_ip': {
                'container': '.page-layout__content-wrapper',
                'result_container': '.serp-item__preview',
                'link': '.serp-item__preview .serp-item__link::attr(onmousedown)'
            },
            'de_ip_raw': {
                'container': '.page-layout__content-wrapper',
                'result_container': '.serp-item__preview',
                'link': '.serp-item__preview .serp-item__link::attr(href)'
            }
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def after_parsing(self):
        """Clean the urls.

        Normally Yandex image search store the image url in the onmousedown attribute in a json object. Its
        pretty messsy. This method grabs the link with a quick regex.

        c.hit({"dtype":"iweb","path":"8.228.471.241.184.141","pos":69,"reqid":"1418919408668565-676535248248925882431999-ws35-986-IMG-p2"}, {"href":"http://www.thewallpapers.org/wallpapers/3/382/thumb/600_winter-snow-nature002.jpg"});

        Sometimes the img url is also stored in the href attribute (when requesting with raw http packets).
        href="/images/search?text=snow&img_url=http%3A%2F%2Fwww.proza.ru%2Fpics%2F2009%2F12%2F07%2F1290.jpg&pos=2&rpt=simage&pin=1">
        """
        super().after_parsing()

        if self.searchtype == 'normal':
            self.no_results = False

            if self.no_results_text:
                self.no_results = 'По вашему запросу ничего не нашлось' in self.no_results_text

            if self.num_results == 0:
                self.no_results = True

        if self.searchtype == 'image':
            for key, i in self.iter_serp_items():
                for regex in (
                    r'\{"href"\s*:\s*"(?P<url>.*?)"\}',
                    r'img_url=(?P<url>.*?)&'
                ):
                    result = re.search(regex, self.search_results[key][i]['link'])
                    if result:
                        self.search_results[key][i]['link'] = result.group('url')
                        break


class BingParser(Parser):
    """Parses SERP pages of the Bing search engine."""

    search_engine = 'bing'

    search_types = ['normal', 'image']

    no_results_selector = ['#b_results > .b_ans::text']

    num_results_search_selectors = ['.sb_count']

    effective_query_selector = ['#sp_requery a > strong']

    page_number_selectors = ['.sb_pagS::text']

    autocorrect_selector = [] #TO DO
    autocorrect_forced_check_selector = [] #TO DO

    map_selector = [] #TO DO

    image_results_selector = [] #TO DO

    image_mega_block_selector = [] #TO DO

    answer_box_selector = [] #TO DO

    answer_box_multi_selector = [] #TO DO

    knowledge_graph_box_selector = [] #TO DO

    knowledge_graph_title_selector = [] #TO DO

    knowledge_graph_google_star_rating_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_selector = [] #TO DO

    knowledge_graph_google_star_rating_big_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_big_selector = [] #TO DO

    knowledge_graph_subtitle_selector = [] #TO DO

    knowledge_graph_location_subtitle_selector = [] #TO DO

    knowledge_graph_snippet_selector = [] #TO DO

    knowledge_graph_location_snippet_selector = [] #TO DO

    knowledge_graph_google_plus_recent_post_selector = [] #TO DO

    knowledge_graph_map_selector = [] #TO DO

    knowledge_graph_thumbnail_selector = [] #TO DO

    knowledge_graph_google_images_scrapbook_selector = [] #TO DO

    normal_search_selectors = {
        'results': {
            'us_ip': {
                'container': '#b_results',
                'result_container': '.b_algo',
                'link': 'h2 > a::attr(href)',
                'snippet': '.b_caption > p::text',
                'title': 'h2::text',
                'visible_link': 'cite::text'
            },
            'de_ip': {
                'container': '#b_results',
                'result_container': '.b_algo',
                'link': 'h2 > a::attr(href)',
                'snippet': '.b_caption > p::text',
                'title': 'h2::text',
                'visible_link': 'cite::text'
            },
            'de_ip_news_items': {
                'container': 'ul.b_vList li',
                'link': ' h5 a::attr(href)',
                'snippet': 'p::text',
                'title': ' h5 a::text',
                'visible_link': 'cite::text'
            },
        },
        'ads_main': {
            'us_ip': {
                'container': '#b_results .b_ad',
                'result_container': '.sb_add',
                'link': 'h2 > a::attr(href)',
                'snippet': '.sb_addesc::text',
                'title': 'h2 > a::text',
                'visible_link': 'cite::text'
            },
            'de_ip': {
                'container': '#b_results .b_ad',
                'result_container': '.sb_add',
                'link': 'h2 > a::attr(href)',
                'snippet': '.b_caption > p::text',
                'title': 'h2 > a::text',
                'visible_link': 'cite::text'
            }
        }
    }

    image_search_selectors = {
        'results': {
            'ch_ip': {
                'container': '#dg_c .imgres',
                'result_container': '.dg_u',
                'link': 'a.dv_i::attr(m)'
            },
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    def after_parsing(self):
        """Clean the urls.

        The image url data is in the m attribute.

        m={ns:"images.1_4",k:"5018",mid:"46CE8A1D71B04B408784F0219B488A5AE91F972E",
        surl:"http://berlin-germany.ca/",imgurl:"http://berlin-germany.ca/images/berlin250.jpg",
        oh:"184",tft:"45",oi:"http://berlin-germany.ca/images/berlin250.jpg"}
        """
        super().after_parsing()

        if self.searchtype == 'normal':

            self.no_results = False
            if self.no_results_text:
                self.no_results = self.query in self.no_results_text\
                                  or 'Do you want results only for' in self.no_results_text

        if self.searchtype == 'image':
            for key, i in self.iter_serp_items():
                for regex in (
                    r'imgurl:"(?P<url>.*?)"',
                ):
                    result = re.search(regex, self.search_results[key][i]['link'])
                    if result:
                        self.search_results[key][i]['link'] = result.group('url')
                        break


class YahooParser(Parser):
    """Parses SERP pages of the Yahoo search engine."""

    search_engine = 'yahoo'

    search_types = ['normal', 'image']

    no_results_selector = []

    # yahooo doesn't have such a thing :D
    effective_query_selector = ['']

    num_results_search_selectors = ['#pg > span:last-child']

    page_number_selectors = ['#pg > strong::text']

    autocorrect_selector = [] #TO DO
    autocorrect_forced_check_selector = [] #TO DO

    map_selector = [] #TO DO

    image_results_selector = [] #TO DO

    image_mega_block_selector = [] #TO DO

    answer_box_selector = [] #TO DO

    answer_box_multi_selector = [] #TO DO

    knowledge_graph_box_selector = [] #TO DO

    knowledge_graph_title_selector = [] #TO DO

    knowledge_graph_google_star_rating_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_selector = [] #TO DO

    knowledge_graph_google_star_rating_big_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_big_selector = [] #TO DO

    knowledge_graph_subtitle_selector = [] #TO DO

    knowledge_graph_location_subtitle_selector = [] #TO DO

    knowledge_graph_snippet_selector = [] #TO DO

    knowledge_graph_location_snippet_selector = [] #TO DO

    knowledge_graph_google_plus_recent_post_selector = [] #TO DO

    knowledge_graph_map_selector = [] #TO DO

    knowledge_graph_thumbnail_selector = [] #TO DO

    knowledge_graph_google_images_scrapbook_selector = [] #TO DO

    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': '#main',
                'result_container': '.res',
                'link': 'div > h3 > a::attr(href)',
                'snippet': 'div.abstr::text',
                'title': 'div > h3 > a::text',
                'visible_link': 'span.url::text'
            }
        },
    }

    image_search_selectors = {
        'results': {
            'ch_ip': {
                'container': '#results',
                'result_container': '#sres > li',
                'link': 'a::attr(href)'
            },
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    def after_parsing(self):
        """Clean the urls.

        The url is in the href attribute and the &imgurl= parameter.

        <a id="yui_3_5_1_1_1419284335995_1635" aria-label="<b>Matterhorn</b> sunrise"
        href="/images/view;_ylt=AwrB8phvj5hU7moAFzOJzbkF;_ylu=X3oDMTIyc3ZrZ3RwBHNlYwNzcgRzbGsDaW1nBG9pZANmNTgyY2MyYTY4ZmVjYTI5YmYwNWZlM2E3ZTc1YzkyMARncG9zAzEEaXQDYmluZw--?
        .origin=&back=https%3A%2F%2Fimages.search.yahoo.com%2Fsearch%2Fimages%3Fp%3Dmatterhorn%26fr%3Dyfp-t-901%26fr2%3Dpiv-web%26tab%3Dorganic%26ri%3D1&w=4592&h=3056&
        imgurl=www.summitpost.org%2Fimages%2Foriginal%2F699696.JPG&rurl=http%3A%2F%2Fwww.summitpost.org%2Fmatterhorn-sunrise%2F699696&size=5088.0KB&
        name=%3Cb%3EMatterhorn%3C%2Fb%3E+sunrise&p=matterhorn&oid=f582cc2a68feca29bf05fe3a7e75c920&fr2=piv-web&
        fr=yfp-t-901&tt=%3Cb%3EMatterhorn%3C%2Fb%3E+sunrise&b=0&ni=21&no=1&ts=&tab=organic&
        sigr=11j056ue0&sigb=134sbn4gc&sigi=11df3qlvm&sigt=10pd8j49h&sign=10pd8j49h&.crumb=qAIpMoHvtm1&fr=yfp-t-901&fr2=piv-web">
        """
        super().after_parsing()

        if self.searchtype == 'normal':

            self.no_results = False
            if self.num_results == 0:
                self.no_results = True

            if len(self.dom.xpath(self.css_to_xpath('#cquery'))) >= 1:
                self.no_results = True

            for key, i in self.iter_serp_items():
                if self.search_results[key][i]['visible_link'] is None:
                    del self.search_results[key][i]

        if self.searchtype == 'image':
            for key, i in self.iter_serp_items():
                for regex in (
                    r'&imgurl=(?P<url>.*?)&',
                ):
                    result = re.search(regex, self.search_results[key][i]['link'])
                    if result:
                        # TODO: Fix this manual protocol adding by parsing "rurl"
                        self.search_results[key][i]['link'] = 'http://' + unquote(result.group('url'))
                        break

class BaiduParser(Parser):
    """Parses SERP pages of the Baidu search engine."""

    search_engine = 'baidu'

    search_types = ['normal', 'image']

    num_results_search_selectors = ['#container .nums']

    no_results_selector = []

    # no such thing for baidu
    effective_query_selector = ['']

    page_number_selectors = ['.fk_cur + .pc::text']

    autocorrect_selector = [] #TO DO
    autocorrect_forced_check_selector = [] #TO DO

    map_selector = [] #TO DO

    image_results_selector = [] #TO DO

    image_mega_block_selector = [] #TO DO

    answer_box_selector = [] #TO DO

    answer_box_multi_selector = [] #TO DO

    knowledge_graph_box_selector = [] #TO DO

    knowledge_graph_title_selector = [] #TO DO

    knowledge_graph_google_star_rating_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_selector = [] #TO DO

    knowledge_graph_google_star_rating_big_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_big_selector = [] #TO DO

    knowledge_graph_subtitle_selector = [] #TO DO

    knowledge_graph_location_subtitle_selector = [] #TO DO

    knowledge_graph_snippet_selector = [] #TO DO

    knowledge_graph_location_snippet_selector = [] #TO DO

    knowledge_graph_google_plus_recent_post_selector = [] #TO DO

    knowledge_graph_map_selector = [] #TO DO

    knowledge_graph_thumbnail_selector = [] #TO DO

    knowledge_graph_google_images_scrapbook_selector = [] #TO DO

    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': '#content_left',
                'result_container': '.result-op',
                'link': 'h3 > a.t::attr(href)',
                'snippet': '.c-abstract::text',
                'title': 'h3 > a.t::text',
                'visible_link': 'span.c-showurl::text'
            },
            'nojs': {
                'container': '#content_left',
                'result_container': '.result',
                'link': 'h3 > a::attr(href)',
                'snippet': '.c-abstract::text',
                'title': 'h3 > a::text',
                'visible_link': 'span.g::text'
            }
        },
    }

    image_search_selectors = {
        'results': {
            'ch_ip': {
                'container': '#imgContainer',
                'result_container': '.pageCon > li',
                'link': '.imgShow a::attr(href)'
            },
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    def after_parsing(self):
        """Clean the urls.

        href="/i?ct=503316480&z=&tn=baiduimagedetail&ipn=d&word=matterhorn&step_word=&ie=utf-8&in=9250&
        cl=2&lm=-1&st=&cs=3326243323,1574167845&os=1495729451,4260959385&pn=0&rn=1&di=69455168860&ln=1285&
        fr=&&fmq=1419285032955_R&ic=&s=&se=&sme=0&tab=&width=&height=&face=&is=&istype=&ist=&jit=&
        objurl=http%3A%2F%2Fa669.phobos.apple.com%2Fus%2Fr1000%2F077%2FPurple%2Fv4%2F2a%2Fc6%2F15%2F2ac6156c-e23e-62fd-86ee-7a25c29a6c72%2Fmzl.otpvmwuj.1024x1024-65.jpg&adpicid=0"
        """
        super().after_parsing()

        if self.search_engine == 'normal':
            if len(self.dom.xpath(self.css_to_xpath('.hit_top_new'))) >= 1:
                self.no_results = True

        if self.searchtype == 'image':
            for key, i in self.iter_serp_items():
                for regex in (
                    r'&objurl=(?P<url>.*?)&',
                ):
                    result = re.search(regex, self.search_results[key][i]['link'])
                    if result:
                        self.search_results[key][i]['link'] = unquote(result.group('url'))
                        break


class DuckduckgoParser(Parser):
    """Parses SERP pages of the Duckduckgo search engine."""

    search_engine = 'duckduckgo'

    search_types = ['normal']

    num_results_search_selectors = []

    no_results_selector = []

    effective_query_selector = ['']

    # duckduckgo is loads next pages with ajax
    page_number_selectors = ['']

    autocorrect_selector = [] #TO DO
    autocorrect_forced_check_selector = [] #TO DO

    map_selector = [] #TO DO

    image_results_selector = [] #TO DO

    image_mega_block_selector = [] #TO DO

    answer_box_selector = [] #TO DO

    answer_box_multi_selector = [] #TO DO

    knowledge_graph_box_selector = [] #TO DO

    knowledge_graph_title_selector = [] #TO DO

    knowledge_graph_google_star_rating_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_selector = [] #TO DO

    knowledge_graph_google_star_rating_big_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_big_selector = [] #TO DO

    knowledge_graph_subtitle_selector = [] #TO DO

    knowledge_graph_location_subtitle_selector = [] #TO DO

    knowledge_graph_snippet_selector = [] #TO DO

    knowledge_graph_location_snippet_selector = [] #TO DO

    knowledge_graph_google_plus_recent_post_selector = [] #TO DO

    knowledge_graph_map_selector = [] #TO DO

    knowledge_graph_thumbnail_selector = [] #TO DO

    knowledge_graph_google_images_scrapbook_selector = [] #TO DO

    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': '#links',
                'result_container': '.result',
                'link': '.result__title > a::attr(href)',
                'snippet': 'result__snippet::text',
                'title': '.result__title > a::text',
                'visible_link': '.result__url__domain::text'
            }
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    def after_parsing(self):
        super().after_parsing()

        if self.searchtype == 'normal':

            try:
                if 'No more results.' in self.dom.xpath(self.css_to_xpath('.no-results'))[0].text_content():
                    self.no_results = True
            except:
                pass

            if self.num_results > 0:
                self.no_results = False
            elif self.num_results <= 0:
                self.no_results = True


class AskParser(Parser):
    """Parses SERP pages of the Ask search engine."""

    search_engine = 'ask'

    search_types = ['normal']

    num_results_search_selectors = []

    no_results_selector = []

    effective_query_selector = ['#spell-check-result > a']

    page_number_selectors = ['.pgcsel .pg::text']

    autocorrect_selector = [] #TO DO
    autocorrect_forced_check_selector = [] #TO DO

    map_selector = [] #TO DO

    image_results_selector = [] #TO DO

    image_mega_block_selector = [] #TO DO

    answer_box_selector = [] #TO DO

    answer_box_multi_selector = [] #TO DO

    knowledge_graph_box_selector = [] #TO DO

    knowledge_graph_title_selector = [] #TO DO

    knowledge_graph_google_star_rating_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_selector = [] #TO DO

    knowledge_graph_google_star_rating_big_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_big_selector = [] #TO DO

    knowledge_graph_subtitle_selector = [] #TO DO

    knowledge_graph_location_subtitle_selector = [] #TO DO

    knowledge_graph_snippet_selector = [] #TO DO

    knowledge_graph_location_snippet_selector = [] #TO DO

    knowledge_graph_google_plus_recent_post_selector = [] #TO DO

    knowledge_graph_map_selector = [] #TO DO

    knowledge_graph_thumbnail_selector = [] #TO DO

    knowledge_graph_google_images_scrapbook_selector = [] #TO DO

    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': '#midblock',
                'result_container': '.ptbs.ur',
                'link': '.abstract > a::attr(href)',
                'snippet': '.abstract::text',
                'title': '.txt_lg.b::text',
                'visible_link': '.durl span::text'
            }
        },
    }


class BlekkoParser(Parser):
    """Parses SERP pages of the Blekko search engine."""

    search_engine = 'blekko'

    search_types = ['normal']

    effective_query_selector = ['']

    no_results_selector = []

    num_results_search_selectors = []

    autocorrect_selector = [] #TO DO
    autocorrect_forced_check_selector = [] #TO DO

    map_selector = [] #TO DO

    image_results_selector = [] #TO DO

    image_mega_block_selector = [] #TO DO

    answer_box_selector = [] #TO DO

    answer_box_multi_selector = [] #TO DO

    knowledge_graph_box_selector = [] #TO DO

    knowledge_graph_title_selector = [] #TO DO

    knowledge_graph_google_star_rating_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_selector = [] #TO DO

    knowledge_graph_google_star_rating_big_selector = [] #TO DO

    knowledge_graph_google_star_rating_numbers_big_selector = [] #TO DO

    knowledge_graph_subtitle_selector = [] #TO DO

    knowledge_graph_location_subtitle_selector = [] #TO DO

    knowledge_graph_snippet_selector = [] #TO DO

    knowledge_graph_location_snippet_selector = [] #TO DO

    knowledge_graph_google_plus_recent_post_selector = [] #TO DO

    knowledge_graph_map_selector = [] #TO DO

    knowledge_graph_thumbnail_selector = [] #TO DO

    knowledge_graph_google_images_scrapbook_selector = [] #TO DO

    normal_search_selectors = {
        'results': {
            'de_ip': {
                'container': '#links',
                'result_container': '.result',
                'link': '.result__title > a::attr(href)',
                'snippet': 'result__snippet::text',
                'title': '.result__title > a::text',
                'visible_link': '.result__url__domain::text'
            }
        },
    }



def get_parser_by_url(url):
    """Get the appropriate parser by an search engine url.

    Args:
        url: The url that was used to issue the search

    Returns:
        The correct parser that can parse results for this url.

    Raises:
        UnknowUrlException if no parser could be found for the url.
    """
    parser = None

    if re.search(r'^http[s]?://www\.google', url):
        parser = GoogleParser
    elif re.search(r'^http://yandex\.ru', url):
        parser = YandexParser
    elif re.search(r'^http://www\.bing\.', url):
        parser = BingParser
    elif re.search(r'^http[s]?://search\.yahoo.', url):
        parser = YahooParser
    elif re.search(r'^http://www\.baidu\.com', url):
        parser = BaiduParser
    elif re.search(r'^https://duckduckgo\.com', url):
        parser = DuckduckgoParser
    if re.search(r'^http[s]?://[a-z]{2}?\.ask', url):
        parser = AskParser
    if re.search(r'^http[s]?://blekko', url):
        parser = BlekkoParser
    if not parser:
        raise UnknowUrlException('No parser for {}.'.format(url))

    return parser


def get_parser_by_search_engine(search_engine):
    """Get the appropriate parser for the search_engine

    Args:
        search_engine: The name of a search_engine.

    Returns:
        A parser for the search_engine

    Raises:
        NoParserForSearchEngineException if no parser could be found for the name.
    """
    if search_engine == 'google':
        return GoogleParser
    elif search_engine == 'yandex':
        return YandexParser
    elif search_engine == 'bing':
        return BingParser
    elif search_engine == 'yahoo':
        return YahooParser
    elif search_engine == 'baidu':
        return BaiduParser
    elif search_engine == 'duckduckgo':
        return DuckduckgoParser
    elif search_engine == 'ask':
        return AskParser
    elif search_engine == 'blekko':
        return BlekkoParser
    else:
        raise NoParserForSearchEngineException('No such parser for {}'.format(search_engine))


def parse_serp(html=None, parser=None, scraper=None, search_engine=None, query=''):
        """Store the parsed data in the sqlalchemy session.

        If no parser is supplied then we are expected to parse again with
        the provided html.

        This function may be called from scraping and caching.
        When called from caching, some info is lost (like current page number).

        Args:
            TODO: A whole lot

        Returns:
            The parsed SERP object.
        """

        if not parser and html:
            parser = get_parser_by_search_engine(search_engine)
            parser = parser(query=query)
            parser.parse(html)

        serp = SearchEngineResultsPage()

        if query:
            serp.query = query

        if parser:
            serp.set_values_from_parser(parser)
        if scraper:
            serp.set_values_from_scraper(scraper)

        return serp

if __name__ == '__main__':
    """Originally part of https://github.com/NikolaiT/GoogleScraper.

    Only for testing purposes: May be called directly with an search engine
    search url. For example:

    python3 parsing.py 'http://yandex.ru/yandsearch?text=GoogleScraper&lr=178&csg=82%2C4317%2C20%2C20%2C0%2C0%2C0'

    Please note: Using this module directly makes little sense, because requesting such urls
    directly without imitating a real browser (which is done in my GoogleScraper module) makes
    the search engines return crippled html, which makes it impossible to parse.
    But for some engines it nevertheless works (for example: yandex, google, ...).
    """
    import requests
    assert len(sys.argv) >= 2, 'Usage: {} url/file'.format(sys.argv[0])
    url = sys.argv[1]
    if os.path.exists(url):
        raw_html = open(url, 'r').read()
        parser = get_parser_by_search_engine(sys.argv[2])
    else:
        raw_html = requests.get(url).text
        parser = get_parser_by_url(url)

    parser = parser(raw_html)
    parser.parse()
    print(parser)

    with open('/tmp/testhtml.html', 'w') as of:
        of.write(raw_html)
