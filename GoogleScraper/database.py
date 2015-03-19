# -*- coding: utf-8 -*-

"""
The database schema of GoogleScraper.

There are four entities:

    ScraperSearch: Represents a call to GoogleScraper. A search job.
    SearchEngineResultsPage: Represents a SERP result page of a search_engine
    Link: Represents a LINK on a SERP
    Proxy: Stores all proxies and their statuses.

Because searches repeat themselves and we avoid doing them again (caching), one SERP page
can be assigned to more than one ScraperSearch. Therefore we need a n:m relationship.
"""

import datetime
from GoogleScraper.config import Config
from urllib.parse import urlparse
from sqlalchemy import Column, String, Integer, ForeignKey, Table, DateTime, Enum, Boolean, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy import create_engine, UniqueConstraint
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

scraper_searches_serps = Table('scraper_searches_serps', Base.metadata,
    Column('scraper_search_id', Integer, ForeignKey('scraper_search.id')),
    Column('serp_id', Integer, ForeignKey('serp.id'))
)

class ScraperSearch(Base):
    __tablename__ = 'scraper_search'

    id = Column(Integer, primary_key=True)
    keyword_file = Column(String)
    number_search_engines_used = Column(Integer)
    used_search_engines = Column(String)
    number_proxies_used = Column(Integer)
    number_search_queries = Column(Integer)
    started_searching = Column(DateTime, default=datetime.datetime.utcnow)
    stopped_searching = Column(DateTime)

    serps = relationship(
        'SearchEngineResultsPage',
        secondary=scraper_searches_serps,
        backref=backref('scraper_searches', uselist=True)
    )

    def __str__(self):
        return '<ScraperSearch[{id}] scraped for {number_search_queries} unique keywords. Started scraping: {started_searching} and stopped: {stopped_searching}>'.format(**self.__dict__)

    def __repr__(self):
        return self.__str__()

class SearchEngineResultsPage(Base):
    __tablename__ = 'serp'

    id = Column(Integer, primary_key=True)
    status = Column(String, default='successful')
    search_engine_name = Column(String)
    scrape_method = Column(String)
    page_number = Column(Integer)
    requested_at = Column(DateTime, default=datetime.datetime.utcnow)
    requested_by = Column(String, default='127.0.0.1')

    # The string in the SERP that indicates how many results we got for the search term.
    num_results_for_query = Column(String)

    # Whether we got any results at all. This is the same as len(serp.links)
    num_results = Column(Integer, default=-1)

    query = Column(String)

    # if the query was modified by the search engine because there weren't any
    # results, this variable is set to the query that was used instead.
    # Otherwise it remains empty.
    effective_query = Column(String, default='')

    # Whether the search engine has no results.
    # This is not the same as num_results, because some search engines
    # automatically search other similar search queries when they find no results.
    # Sometimes they have results for the query, but detect a spelling mistake and only
    # suggest an alternative. This is another case!
    # If no_results is true, then there weren't ANY RESULTS FOUND FOR THIS QUERY!!!
    no_results = Column(Boolean, default=False)

    # Autocomplete Results
    autocorrect_forced = Column(String)
    autocorrect_suggested = Column(String)

    # Map result
    map_result = Column(Boolean)

    # Image results
    image_results = Column(Boolean)
    image_mega_block = Column(Boolean)

    # Answer box
    answer_box = Column(Boolean)

    # Knowledge Graph
    knowledge_graph_box = Column(Boolean)

    # Searches related to the query in question
    related_searches = Column(String)

    # Disambiguation results
    disambiguation_results = Column(String)

    # Autocomplete Results
    autocomplete_results = Column(String)

    # Average Monthly Search Volume
    average_monthly_search_volume = Column(String)

    # CPC
    average_cpc = Column(String)

    # Competition
    competition = Column(String)

    # Monthly Search Volumes
    monthly_search_volumes = Column(String)

    def __str__(self):
        return '<SERP[{search_engine_name}] has [{num_results}] link results for query "{query}">'.format(**self.__dict__)

    def __repr__(self):
        return self.__str__()

    def has_no_results_for_query(self):
        return self.num_results == 0 or self.effective_query


    def set_values_from_parser(self, parser):
        """Populate itself from a parser object.

        Args:
            A parser object.
        """

        self.num_results_for_query = parser.num_results_for_query
        self.num_results = parser.num_results
        self.effective_query = parser.effective_query
        self.no_results = parser.no_results
        self.autocorrect_forced = (parser.autocorrect if parser.autocorrect_forced_check is not None else None)
        self.autocorrect_suggested = (parser.autocorrect if parser.autocorrect_forced_check is None else None)
        self.map_result  = parser.map_result
        self.image_results = parser.image_results
        self.image_mega_block = parser.image_mega_block
        self.answer_box = parser.answer_box
        self.related_seaches = None
        self.disambiguation_results = None
        self.knowledge_graph_box = parser.knowledge_graph_box

        related_searches = []
        disambiguation_results = []
        knowledge_graph_trivia = []
        knowledge_graph_social_profiles = []
        knowledge_graph_google_reviews = []
        knowledge_graph_features = []
        knowledge_graph_people_also_search_for = []
        knowledge_graph_slideshows = []

        for key, value in parser.search_results.items():
            if isinstance(value, list):
                for link in value:
                    parsed = urlparse(link['link'])

                    # fill with nones to prevent key errors
                    [link.update({key: None}) for key in ('snippet', 'title', 'visible_link', 'price', 'google_star_rating', 'google_star_rating_reviews', 'address', 'phone_number', 'search_bar', 'schema_enhanced_listing', 'image_thumbnail', 'video_thumbnail', 'small_sitelink_1', 'small_sitelink_2', 'small_sitelink_3', 'small_sitelink_4', 'small_sitelink_5', 'small_sitelink_6', 'big_sitelink_1', 'big_sitelink_2', 'big_sitelink_3', 'big_sitelink_4', 'big_sitelink_5', 'big_sitelink_6', 'keyword', 'slideshow') if key not in link]

                    if key == 'related_searches' and link['keyword'] is not None:
                        related_searches.append(link['keyword'])

                    elif (key == 'knowledge_graph_trivia'):
                        if link['hours_title'] is not None:
                            if (link['hours_morning'] is None and link['hours_afternoon'] is None):
                                if (link['hours_status'] is not None):
                                    knowledge_graph_trivia.append(link['hours_title'] + ' ' + link['hours_status'])
                                else:
                                    knowledge_graph_trivia.append(link['hours_title'] + ' ' + link['hours_status_grayscale'])
                            elif link['hours_morning'] == link['hours_afternoon']:
                                knowledge_graph_trivia.append(link['hours_title'] + ' ' + link['hours_status'] + ' ' + link['hours_afternoon'])
                            else:
                                knowledge_graph_trivia.append(link['hours_title'] + ' ' + link['hours_status'] + ' ' + link['hours_morning'] + ' ' + link['hours_afternoon'])
                        else:
                            temp_link = (link['title'] if link['title'] is not None else link['link_title'])
                            temp_fact = (link['fact'] if link['fact'] is not None else link['link_fact'])
                            knowledge_graph_trivia.append(temp_link + ' ' + temp_fact)

                    elif (key == 'knowledge_graph_social_profiles'):
                        knowledge_graph_social_profiles.append(link['profile'])

                    elif (key == 'knowledge_graph_google_plus_reviews'):
                        knowledge_graph_google_reviews.append(link['review'])

                    elif (key == 'knowledge_graph_features'):
                        knowledge_graph_features.append(link['institution'] + ': ' + link['feature'])

                    elif (key == 'knowledge_graph_people_also_search_for'):
                        knowledge_graph_people_also_search_for.append(link['keyword'])

                    elif (key == 'knowledge_graph_slideshows'):
                        if link['slideshow'] is not None:
                            knowledge_graph_slideshows.append(link['slideshow'])

                    elif (key == 'disambiguation_box'):
                        if (link['snippet'] is not None):
                            disambiguation_results.append(link['keyword'] + ' - ' + link['snippet'])
                        elif (link['snippet[0][0]'] is not None and link['snippet[0][1]'] is not None and link['snippet[1][0]'] is not None and link['snippet[1][1]'] is not None):
                            disambiguation_results.append(link['keyword'] + ' - ' + link['snippet[0][0]'] + link['snippet[0][1]'] + ' ' + link['snippet[1][0]'] + link['snippet[1][1]'])
                        else:
                            disambiguation_results.append(link['keyword'])

                    else:
                        # Google Star Ratings Check
                        google_star_rating = None
                        if key == 'organic_results' and link['google_star_rating'] is not None:
                            google_star_rating = link['google_star_rating'] + ' - ' + link['google_star_rating_reviews']
                        elif key == 'paid_results' and link['google_star_rating'] is not None:
                            google_star_rating = link['google_star_rating']
                        elif key == 'local_pack_results' and link['google_star_rating'] is not None:
                            google_star_rating = link['google_star_rating'] + ' - ' + link['google_star_rating_reviews']
                        elif key == 'list_carousel' and link['google_star_rating'] is not None:
                            google_star_rating = link['google_star_rating'] + ' - ' + link['google_star_rating_reviews']

                        # Adding phone number to address in paid results
                        address = link['address']
                        if key == 'paid_results' and link['address'] is not None and link['phone_number'] is not None:
                            address = address + ' ' + link['phone_number']

                        # Search Bar Check
                        search_bar = None
                        if link['search_bar'] is not None:
                            search_bar = True
                        elif key == 'organic_results':
                            search_bar = False

                        # Schema Enhanced Listing Check
                        schema_enhanced_listing = (None if not link['schema_enhanced_listing'] else link['schema_enhanced_listing'])

                        # Image Thumbnail Check
                        image_thumbnail = None
                        if link['image_thumbnail'] is not None:
                            image_thumbnail = True
                        elif key == 'organic_results' or key == 'news_results' or key == 'in_depth_articles' or key == 'shopping_results (left)' or key == 'shopping_results (right)' or key == 'local_carousel' or key == 'list_carousel':
                            image_thumbnail = False

                        # Video Thumbnail Check
                        video_thumbnail = None
                        if link['video_thumbnail'] is not None:
                            video_thumbnail = True
                        elif key == 'organic_results':
                            video_thumbnail = False

                        # Small Sitelinks Check
                        small_sitelinks = []
                        for i in range(1, 7):
                            if (link['small_sitelink_' + str(i)] is not None):
                                small_sitelinks.append(link['small_sitelink_' + str(i)])
                        small_sitelinks = ('; '.join(small_sitelinks) if small_sitelinks else None)

                        # Big Sitelinks Check
                        big_sitelinks = []
                        for i in range(1, 7):
                            if (link['big_sitelink_' + str(i)] is not None):
                                big_sitelinks.append(link['big_sitelink_' + str(i)] + ' - ' + link['big_sitelink_' + str(i) + '_description'])
                        big_sitelinks = ('; '.join(big_sitelinks) if big_sitelinks else None)

                        # Social Site Check
                        social_sites = [
                            'www.facebook.com',
                            'twitter.com',
                            'www.linkedin.com',
                            'www.pinterest.com',
                            'plus.google.com',
                            'www.tumblr.com',
                            'instagram.com',
                            'vk.com',
                            'www.flickr.com',
                            'vine.co',
                            'www.meetup.com',
                            'www.tagged.com',
                            'ask.fm',
                            'www.meetme.com',
                            'www.classmates.com'
                        ]
                        social_site = False
                        if parsed.netloc in social_sites:
                            social_site = True

                        # HTTPS Check
                        https = False
                        if link['link'].startswith('https'):
                            https = True

                        # M-dot Check
                        m_dot = False
                        if link['link'].find('//m.') != -1:
                            m_dot = True

                        l = Link(
                            link=link['link'],
                            snippet=link['snippet'],
                            title=link['title'],
                            visible_link=link['visible_link'],
                            domain=parsed.netloc,
                            rank=link['rank'],
                            serp=self,
                            link_type=key,
                            google_star_rating=google_star_rating,
                            address=address,
                            search_bar=search_bar,
                            schema_enhanced_listing=schema_enhanced_listing,
                            image_thumbnail=image_thumbnail,
                            video_thumbnail=video_thumbnail,
                            small_sitelinks=small_sitelinks,
                            big_sitelinks=big_sitelinks,
                            price=link['price'],
                            social_site=social_site,
                            https=https,
                            m_dot=m_dot
                        )

        # Joining together the related searches for database entry
        if len(related_searches) > 1:
            self.related_searches = '; '.join(related_searches)
        elif len(related_searches) == 1:
            self.related_searches = related_searches[0]

        # Joining together the disambiguation results for database entry
        if (len(disambiguation_results) > 1):
            self.disambiguation_results = '; '.join(disambiguation_results)
        elif (len(disambiguation_results) == 1):
            self.disambiguation_results = disambiguation_results[0]


        knowledge_graph_trivia = ('; '.join(knowledge_graph_trivia) if len(knowledge_graph_trivia) > 0 else None)
        knowledge_graph_social_profiles = ('; '.join(knowledge_graph_social_profiles) if len(knowledge_graph_social_profiles) > 0 else None)
        knowledge_graph_google_reviews = ('; '.join(knowledge_graph_google_reviews) if len(knowledge_graph_google_reviews) > 0 else None)
        knowledge_graph_features = ('; '.join(knowledge_graph_features) if len(knowledge_graph_features) > 0 else None)
        knowledge_graph_people_also_search_for = ('; '.join(knowledge_graph_people_also_search_for) if len(knowledge_graph_people_also_search_for) > 0 else None)
        knowledge_graph_slideshows = ('; '.join(knowledge_graph_slideshows) if len(knowledge_graph_slideshows) > 0 else None)
        if (self.knowledge_graph_box):
            k = KnowledgeGraph(
                title=parser.knowledge_graph_title,
                google_star_rating=(parser.knowledge_graph_google_star_rating if parser.knowledge_graph_google_star_rating is not None else parser.knowledge_graph_google_star_rating_big),
                google_star_rating_number_of_reviews=(parser.knowledge_graph_google_star_rating_numbers if parser.knowledge_graph_google_star_rating_numbers is not None else parser.knowledge_graph_google_star_rating_numbers_big),
                google_reviews=knowledge_graph_google_reviews,
                subtitle=(parser.knowledge_graph_subtitle if parser.knowledge_graph_subtitle is not None else parser.knowledge_graph_location_subtitle),
                snippet=(parser.knowledge_graph_snippet if parser.knowledge_graph_snippet is not None else parser.knowledge_graph_location_snippet),
                trivia=knowledge_graph_trivia,
                social_profiles=knowledge_graph_social_profiles,
                google_plus_recent_post=parser.knowledge_graph_google_plus_recent_post,
                knowledge_graph_features=knowledge_graph_features,
                people_also_search_for=knowledge_graph_people_also_search_for,
                google_map=parser.knowledge_graph_map,
                thumbnail=parser.knowledge_graph_thumbnail,
                slideshows=knowledge_graph_slideshows,
                google_images_scrapbook=parser.knowledge_graph_google_images_scrapbook,
                serp=self
            )

    def set_values_from_scraper(self, scraper):
        """Populate itself from a scraper object.

        A scraper may be any object of type:

            - SelScrape
            - HttpScrape
            - AsyncHttpScrape

        Args:
            A scraper object.
        """

        self.query = scraper.query
        self.search_engine_name = scraper.search_engine_name
        self.scrape_method = scraper.scrape_method
        self.page_number = scraper.page_number
        self.requested_at = scraper.requested_at
        self.requested_by = scraper.requested_by
        self.status = scraper.status
        self.autocomplete_results = scraper.autocomplete

    def was_correctly_requested(self):
        return self.status == 'successful'


# Alias as a shorthand for working in the shell
SERP = SearchEngineResultsPage

class Link(Base):
    __tablename__= 'link'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    snippet = Column(String)
    link = Column(String)
    domain = Column(String)
    visible_link = Column(String)
    rank = Column(Integer)
    link_type = Column(String)
    google_star_rating = Column(String)
    address = Column(String)
    search_bar = Column(Boolean)
    schema_enhanced_listing=Column(String)
    image_thumbnail = Column(Boolean)
    video_thumbnail = Column(Boolean)
    small_sitelinks = Column(String)
    big_sitelinks = Column(String)
    price = Column(String)
    social_site = Column(Boolean)
    https = Column(Boolean)
    m_dot = Column(Boolean)

    serp_id = Column(Integer, ForeignKey('serp.id'))
    serp = relationship(SearchEngineResultsPage, backref=backref('links', uselist=True))

    def __str__(self):
        return '<Link at rank {rank} has url: {link}>'.format(**self.__dict__)

    def __repr__(self):
        return self.__str__()

class KnowledgeGraph(Base):
    __tablename__= 'knowledge_graph'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    subtitle = Column(String)
    snippet = Column(String)
    trivia = Column(String)
    google_star_rating = Column(Integer)
    google_star_rating_number_of_reviews = Column(String)
    google_reviews = Column(String)
    social_profiles = Column(String)
    google_plus_recent_post = Column(String)
    knowledge_graph_features = Column(String)
    people_also_search_for = Column(String)
    google_map = Column(Boolean)
    thumbnail = Column(Boolean)
    slideshows = Column(String)
    google_images_scrapbook = Column(Boolean)
    serp_id = Column(Integer, ForeignKey('serp.id'))
    serp = relationship(SearchEngineResultsPage, backref=backref('knowledge_graph', uselist=False))

class Proxy(Base):
    __tablename__= 'proxy'

    id = Column(Integer, primary_key=True)
    ip = Column(String)
    hostname = Column(String)
    port = Column(Integer)
    proto = Column(Enum('socks5', 'socks4', 'http'))
    username = Column(String)
    password = Column(String)

    online = Column(Boolean)
    status = Column(String)
    checked_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    city = Column(String)
    region = Column(String)
    country = Column(String)
    loc = Column(String)
    org = Column(String)
    postal = Column(String)

    UniqueConstraint(ip, port, name='unique_proxy')

    def __str__(self):
        return '<Proxy {ip}>'.format(**self.__dict__)

    def __repr__(self):
        return self.__str__()

db_Proxy = Proxy


class SearchEngine(Base):
    __tablename__ = 'search_engine'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    http_url = Column(String)
    selenium_url = Column(String)
    image_url = Column(String)


class SearchEngineProxyStatus(Base):
    """Stores last proxy status for the given search engine.

    A proxy can either work on a search engine or not.
    """

    __tablename__ = 'search_engine_proxy_status'

    id = Column(Integer, primary_key=True)
    proxy_id = Column(Integer, ForeignKey('proxy.id'))
    search_engine_id = Column(Integer, ForeignKey('search_engine.id'))
    available = Column(Boolean)
    last_check = Column(DateTime)


def get_engine(path=None):
    """Return the sqlalchemy engine.

    Args:
        path: The path/name of the database to create/read from.

    Returns:
        The sqlalchemy engine.
    """
    db_path = path if path else Config['OUTPUT'].get('database_name', 'google_scraper') + '.db'
    echo = True if (Config['GLOBAL'].getint('verbosity', 0) >= 4) else False
    engine = create_engine('sqlite:///' + db_path, echo=echo, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)

    return engine


def get_session(scoped=False, engine=None, path=None):
    if not engine:
        engine = get_engine(path=path)

    session_factory = sessionmaker(
        bind=engine,
        autoflush=True,
        autocommit=False,
    )

    if scoped:
        ScopedSession = scoped_session(session_factory)
        return ScopedSession
    else:
        return session_factory


def fixtures(session):
    """Add some base data."""

    for se in Config['SCRAPING'].get('supported_search_engines', '').split(','):
        if se:
            search_engine = session.query(SearchEngine).filter(SearchEngine.name == se).first()
            if not search_engine:
                session.add(SearchEngine(name=se))

    session.commit()

def set_values_from_adwords(session, traffic):
    """Populate database with AdWords traffic results"""
    for keyword in traffic:
        serp_page = session.query(SearchEngineResultsPage).filter(SearchEngineResultsPage.query == keyword).order_by(desc(SearchEngineResultsPage.id)).first()
        serp_page.average_monthly_search_volume = traffic.get(keyword).get('average_monthly_search_volume')
        serp_page.average_cpc = traffic.get(keyword).get('average_cpc')
        serp_page.competition = traffic.get(keyword).get('competition')
        serp_page.monthly_search_volumes = ('; '.join(traffic.get(keyword).get('monthly_search_volumes')) if traffic.get(keyword).get('monthly_search_volumes') != [] else None)
    session.commit()
