from selenium import webdriver
import bs4
import pandas as pd
import re
import timeit
import numpy as np

import os
import sys
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import SessionNotCreatedException
from selenium.webdriver.remote.remote_connection import LOGGER
import logging

import datetime as dt
from timeit import default_timer as timer
import time
import database


LOGGER.setLevel(logging.WARNING)

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--silent")
chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
chrome_options.add_argument('--log-level=3')
#chrome_options.binary_location = '/Applications/Google Chrome

files = {'job_openings': 'jobopenings.csv'}
CHROMEDRIVER_DOWNLOAD_URL = 'https://chromedriver.chromium.org/downloads'
EXECUTION_TABLENAME = 'execution_log'
JOBBATCH_TABLENAME = 'job_batch'


class JobSearchWebsite(object):
    report_folder = ''
    data = None
    data_source = ''
    report = None
    driver = None
    pageSoup = None
    name = ''
    run_timestamp = ''
    mainURL = 'https://'
    parserStr = "html5lib"
    resultElementTag = 'span'
    resultTag = 'search-results'
    resultMarkers = ['<div data-cy="search-result-headers">', 'jobs found']
    cardTag = 'job-card-'
    jobs = {'records': None, 'filename': None}
    cardsPerPage = 20
    searchFieldsd = {}
    search_defaults = {}
    salaryLevels = []
    categories = []
    employmentType = ''
    location = ''
    reportFields = ['date', 'source', 'job location', 'employment type', 'job category',
                    'monthly salary', 'matching jobs', 'total jobs']

    def __init__(self, name='MyCareerFutures', mainURL='https://www.mycareersfuture.gov.sg/',
                 searchFields={'salary', 'employmentType', 'category'},
                 search_defaults={'sort': 'new_posting_date', 'page': 0},
                 load_driver=True,data_source='db'):
        global files
        self.name = name
        self.mainURL = mainURL
        self.searchFields = searchFields
        self.search_defaults = search_defaults
        self.data_source = data_source
        self.run_timestamp = dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S')
        self.jobs['filename'] = files['job_openings']
        database.load()
        if load_driver:
            self.loadDriver()
        if os.path.exists(self.jobs['filename']):
            if data_source == 'db':
                self.jobs['records'] = database.get_jobs().copy()
            elif data_source == 'csv':
                self.jobs['records'] = pd.read_csv(self.jobs['filename'])

    def __del__(self):
        try:
            self.driver.quit()
        except:
            pass

    def loadDriver(self):
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except SessionNotCreatedException as exc:
            if 'version' in exc.msg.lower():
                msgStr = 'download the latest chrome webdriver at \n' + CHROMEDRIVER_DOWNLOAD_URL
                print(msgStr)
            raise
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def set_report_parameters(self, salaryLevels, categories, employmentType='Full%20Time',
                              location='Singapore',
                              report_folder='C:\\Users\\taylo\\Helva\\05 Business Development\\03 active income'):
        self.salaryLevels = salaryLevels
        self.categories = categories
        self.employmentType = employmentType
        self.location = location
        self.report_folder = report_folder

    def run_report(self):
        # create list of job search records using jobsearchQuery()
        data = []
        report_date = dt.datetime.now().date()
        report_start = timer()
        for search in self.categories:
            for salary in self.salaryLevels:
                checkpoint = timer()
                #          date ,     source, location,         emp type, category, salary, matching jobs, jobs total
                qryResult = self.jobsearchQuery(salary, search)
                queryJobs = qryResult['query jobs']
                totalJobs = qryResult['total jobs']
                rcdRow = [report_date, self.name, self.location, self.employmentType, search, salary, queryJobs, totalJobs]
                data.append(rcdRow)
            print('query complete for job %s in %.2f seconds' % (search, timer() - checkpoint))
        # create pandas dataframe for job search records and export to csv
        self.data = pd.DataFrame.from_records(data, columns=self.reportFields)
        self.data.to_csv(self.report_folder + '\\jobsearchdata.csv')

        # create pandas pivot table report from job search data and export to csv
        self.report = pd.pivot_table(self.data, index='job category', columns='monthly salary',
                                     values=['matching jobs'])
        self.report.to_csv(self.report_folder + '\\jobsearchreport.csv')
        print('job report complete in %.2f min' % (1 / 60 * (timer() - report_start)))

    def jobsearchQuery(self, salary=7000, search='Professional Services'):
        qryURL = self.jobsearch_URLquery(salary, search, page=self.search_defaults['page'])
        qryResult = self.get_searchResults(qryURL)
        return qryResult

    def url_query(self, main, filters=None, sort='new_posting_date', page=0):
        if not filters is None:
            queryFilters = [key + '=' + str(filters[key]).replace(' ', '%20') for key in filters]
            queryStr = '&'.join(queryFilters)
        else:
            queryStr = ''
        qURL = main + 'search?' + queryStr + '&sort=' + sort + '&page=' + str(page)
        return qURL

    def jobsearch_URLquery(self, salary, search, page=0):
        filters = {}
        filters['search'] = search
        filters['salary'] = salary
        filters['employmentType'] = self.employmentType
        qryURL = self.url_query(self.mainURL, filters, sort=self.search_defaults['sort'], page=page)
        return qryURL

    def refresh_pageSoup(self, qryURL):
        self.driver.get(qryURL)
        time.sleep(15)
        pageStr = self.driver.page_source
        self.pageSoup = bs4.BeautifulSoup(pageStr, self.parserStr)

    def get_searchResults(self, qryURL):
        self.refresh_pageSoup(qryURL)
        return self.searchresults_fromSoup(self.pageSoup)

    def searchresults_fromSoup(self, soupObj):
        elmList = soupObj.findAll(self.resultElementTag)
        search_result_div = [str(x.div) for x in elmList if self.resultTag in str(x)]
        if len(search_result_div) > 0:
            divStr = search_result_div[0]
            markers = [divStr.find(self.resultMarkers[x]) for x in [0, 1]]
            resultStr = divStr[markers[0] + len(self.resultMarkers[0]):markers[1] - 1]
            if 'of' in resultStr:
                strPairs = [x.strip().replace(',', '') for x in resultStr.split('of')]
            else:
                strPairs = [x.strip().replace(',', '') for x in [resultStr,resultStr]]
            resPair = [0 if x == '' else int(x) for x in strPairs]
            if len(resPair) == 2:
                resDict = {'query jobs': resPair[0], 'total jobs': resPair[1]}
            else:
                resDict = {'query jobs': resPair[0], 'total jobs': resPair[0]}
        else:
            resDict = {'query jobs': 0, 'total jobs': 0}
        return resDict

    def get_jobRecord_fromcard(self, cardObj):
        def get_tags(soup_obj, tag_name, attr_name, keyword, as_list=False):
            tag_container = soup_obj.find(tag_name, {attr_name: keyword})
            if as_list:
                tags = tag_container.find_all(tag_name) if tag_container else []
            else:
                tags = tag_container
            return tags
        # salary
        def get_salaryHigh(cardObj):
            salaryHigh = None
            attr_name = 'data-testid'
            keyword = 'salary-range'
            tag_spans = get_tags(cardObj, 'span', attr_name, keyword, as_list=True)
            if tag_spans:
                dollar_spans = [span for span in tag_spans if '$' in span.get_text()]
                salaryHighStr = dollar_spans[-1].get_text(strip=True)
                match = re.search(r'\$([\d,]+)', salaryHighStr)
                if match:
                    salaryHigh = int(match.group(1).replace(',', '')) # 8000 type int
            return salaryHigh

        # title
        def get_position_title(cardObj):
            titleStr = None
            attr_name = 'data-testid'
            keyword = 'job-card__job-title'  # unique tag identifier
            title_tag = get_tags(cardObj, 'span', attr_name, keyword)
            if title_tag:
                titleStr = title_tag.get_text(separator=' ', strip=True)
            return titleStr

        # posted date
        def get_posted_date(cardObj):
            postedDate = None
            postedDate_str = None
            postedStr = ''
            attr_name = 'data-cy'
            keyword = 'job-card-date-info'
            posted_prefix = 'Posted'
            posted_tag = get_tags(cardObj, 'span', attr_name, keyword)
            if posted_tag:
                postedStr = posted_tag.get_text(strip=True)
                match = re.search(rf'{posted_prefix} (.*)', postedStr)
                if match:
                    daysStr_1 = match.group(1).strip().lower()
                else:
                    daysStr_1 = 'ERROR'
                    urlid = get_urlid(cardObj)
                    print(f'ERROR. Unexpected format for date posted substring: {postedStr}. expecting Posted <> from url {urlid}')

                if daysStr_1 != 'ERROR':
                    # convert from x days ago to datetime.date
                    todayDate = dt.datetime.today().date()
                    dayShift = 0

                    if daysStr_1 == 'today':
                        postedDate = todayDate
                    elif daysStr_1 == 'yesterday':
                        dayShift = 1
                    else:
                        rightbloc2 = ' days ago'
                        try:
                            dayShift = int(re.search('(.*)' + rightbloc2, daysStr_1).group(1))
                        except:
                            urlid = get_urlid(cardObj)
                            print('ERROR. problem parsing posted date. urlid: %s, original: %s, left filter: %s' % (urlid, postedStr, daysStr_1))

                    postedDate = todayDate - dt.timedelta(days=dayShift)

            if postedDate is not None:
                postedDate_str = postedDate.strftime('%Y-%m-%d')

            return postedDate_str

        # company name
        def get_company_name(cardObj):
            #company_keyword = 'company-hire-info__company'  # unique tag identifier
            #companyP = [y for y in cardObj.find_all('p') if company_keyword in str(y)][0]
            #leftbloc = '>'
            #rightbloc = '</p>'
            #companyStr = re.search(leftbloc + '(.*)' + rightbloc, str(companyP)).group(1)
            companyStr = None
            attr_name = 'data-testid'
            keyword = 'company-hire-info'
            company_tag = get_tags(cardObj, 'p', attr_name, keyword)
            if company_tag:
                companyStr = company_tag.get_text(separator=' ', strip=True)
            return companyStr

        # url id
        def get_urlid(cardObj):
            prjidStr = None
            link_tag = cardObj.find('a', href=True)
            if link_tag:
                href = link_tag['href']
                # strip out query string
                prjidStr = href.split('?', 1)[0]
                # drop /job/ if present
                prjidStr = prjidStr.replace('/job/', '')
            return prjidStr

        # job id
        def get_jobid(job_dict):
            jobid = '-'.join([job_dict['source'],
                              job_dict['urlid'][-32:],
                              job_dict['posted_date']])
            return jobid

        jobRecord = {}
        jobRecord['salaryHigh'] = get_salaryHigh(cardObj) #2025-05-01 15:31
        jobRecord['position_title'] = get_position_title(cardObj) #2025-05-01 16:02
        jobRecord['posted_date'] = get_posted_date(cardObj) #2025-05-01 16:28
        jobRecord['company_name'] = get_company_name(cardObj) #2025-05-01 16:48
        jobRecord['urlid'] = get_urlid(cardObj) #2025-05-01 16:53
        jobRecord['source'] = self.name
        jobRecord['jobid'] = get_jobid(jobRecord)
        jobRecord['src_methodid'] = 0 # web scraping
        return jobRecord

    def jobRecords_query(self, salary, search, page_max=None, notifications=True):
        cardcount = 1; page = 0; jobs = None
        if page_max is None:
            query_condition = (cardcount > 0)
        else:
            query_condition = ((cardcount > 0) and (page <= page_max))
        while query_condition:
            qryURL = self.jobsearch_URLquery(salary, search, page)
            self.refresh_pageSoup(qryURL)
            time.sleep(4)

            # list of cards using the tag 'job-card-'
            cards = [y for y in [x for x in self.pageSoup.find_all('div')
                                 if x.has_attr('id')] if self.cardTag in y['id']]
            cardcount = len(cards)
            if cardcount > 0:
                # create DataFrame object from card objects
                rcds = []
                for x in cards:
                    #try:
                        rcd = self.get_jobRecord_fromcard(x)
                        rcds.append(rcd)
                    #except:
                    #    if notifications:
                    #        print('error encountered for card %s on page %d' % (x['id'], page))
                morejobs = pd.DataFrame.from_records(rcds)
                if page == 0:
                    jobs = morejobs
                else:
                    jobs = jobs.append(morejobs)
            if notifications:
                print('captured %s cards on page %s' % (cardcount, page))
            page = page + 1
            if page_max is None:
                query_condition = (cardcount > 0)
            else:
                query_condition = ((cardcount > 0) and (page <= page_max))

        return jobs

    def update_jobRecords(self, page_max=None, notifications=True):
        qrycount=0; jobset = []
        for salary in self.salaryLevels:
            for search in self.categories:
                qryjobs = self.jobRecords_query(salary, search, page_max, notifications)
                if not qryjobs is None:
                    jobset.append(qryjobs)
        if len(jobset) == 0:
            raise ValueError('query did not return any job cards')
        else:
            jobs = pd.concat(jobset)
            #post new jobs to csv file
            if not jobs is None:
                jobs.to_csv(self.jobs['filename'], index=False)

                #update database with new jobs
                njid = set(jobs['jobid'])
                if self.jobs['records'] is None:
                    new_jobids = list(njid)
                else:
                    ejid = set(self.jobs['records']['jobid'])
                    new_jobids = list(njid.difference(njid.intersection(ejid)))

                if self.jobs['records'] is None:
                    self.jobs['records'] = jobs
                else:
                    self.jobs['records'] = self.jobs['records'].append(jobs)
                    self.jobs['records'].drop_duplicates(subset=['jobid'], inplace=True)
                    self.jobs['records'].reset_index(inplace=True)
                    del self.jobs['records']['index']
                database.add_jobs(self.jobs['records'], append=False)

                #update run batch
                log_rcd = {'id': 0,
                           'function': 'new_jobcards',
                           'timestamp': self.run_timestamp}
                if database.table_exists(EXECUTION_TABLENAME):
                    ex_log_tbl = database.get_table(EXECUTION_TABLENAME)
                    log_rcd['id'] = len(ex_log_tbl)
                    new_log = pd.DataFrame.from_records([log_rcd])
                    database.update_table(new_log, EXECUTION_TABLENAME, append=True)
                else:
                    new_log = pd.DataFrame.from_records([log_rcd])
                    database.update_table(new_log, EXECUTION_TABLENAME, append=False)

                #update job-batch table
                new_jobs = jobs[jobs['jobid'].isin(new_jobids)].copy()
                new_jobs['batchid'] = log_rcd['id']
                new_jb = new_jobs[['jobid', 'batchid']]
                if database.table_exists(JOBBATCH_TABLENAME):
                    database.update_table(new_jb, JOBBATCH_TABLENAME, append=True)
                else:
                    database.update_table(new_jb, JOBBATCH_TABLENAME, append=False)
