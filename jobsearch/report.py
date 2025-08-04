### this is a script for running reports using agent.JobSearchWebsite
###

# load packages
import ctypes
import sys
import math
import time
import datetime as dt
import bs4
import re
import pandas as pd

import database as db
import mcf_profile
import agent
import match
import post

# load an instance of JobSearchWebsite --> jobsite
jobsite = None
qryResult = None
DATE_FORMAT = '%Y-%m-%d'
SEARCH_CONFIG = {}


def load_job_agent():
    global jobsite
    if jobsite is None:
        jobsite = agent.JobSearchWebsite()


def load(db_only=False):
    db.load()
    load_config()
    if not db_only:
        load_job_agent()


def load_config():
    global SEARCH_CONFIG
    SEARCH_CONFIG = db.CONFIG_FILES['search']['data']


# 01.01 run one qry
def run_searchQry(salaryLevel, category):
    global qryResult
    qryResult= jobsite.jobsearchQuery(salaryLevel, category, jobsite.employmentType)


def sample_qry():
    salaryLevel = 5000; category = 'Engineering'
    run_searchQry(salaryLevel,category)


def get_pagesource(salaryLevel,category,page=0):
    global jobsite
    qryURL = jobsite.jobsearch_URLquery(salaryLevel, category, jobsite.employmentType,
                                   page=page)
    jobsite.driver.get(qryURL)
    time.sleep(2)
    pageStr = jobsite.driver.page_source
    return pageStr


# 01.03 run screening report
def run_screening_report():
    load()
    #set the job type categories and salary levels for the report
    categories = ['Consulting', 'Data%20Analyst', 'Data%20Scientist',
                  'Data%20Engineer', 'Machine%20Learning', 'Python']
    #categories = ['Sciences%20%2F%20Laboratory%20%2F%20R%26D', 'Consulting', 'Engineering', 'Design']
    #categories = ['Consulting','Engineering','Design','Sciences / Laboratory / R&D','Education and Training','Manufacturing',
    #              'Information Technology','Healthcare / Pharmaceutical', 'Logistics / Supply Chain',
    #              'Risk Management','Others']
    salaryLevels = [3000, 5000, 7000, 9000, 11000, 13000, 15000]
    jobsite.set_report_parameters(salaryLevels, categories)
    jobsite.run_report()
    nowtimeStr = dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S')
    print('report created at %s' % nowtimeStr)


# 01.04 run job records report
#def update_jobRecords():
#    ctypes.windll.user32.MessageBoxW(0, "Hello world.", "Message box", 1)


def update_jobRecords(notifications=True, page_max=None):
    load(db_only=True)
    starttime = time.time()
    jobCount_i = len(db.get_jobs())
    keywords = SEARCH_CONFIG['search']['keywords']
    salary_min = SEARCH_CONFIG['search']['salary_min']
    load_job_agent()
    jobsite.set_report_parameters([salary_min], keywords)
    jobsite.update_jobRecords(page_max, notifications)
    if notifications:
        nowtimeStr = dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S')
        new_jobs = len(db.get_jobs()) - jobCount_i
        elapsed = time.time() - starttime
        e_min = math.floor(elapsed / 60)
        e_sec = elapsed - e_min * 60
        print('added %d new jobs in %d min :%d sec at %s' % (new_jobs, e_min, e_sec, nowtimeStr))


def update_jobs_report():
    #01 query job openings from MyCareerFutures website
        starttime = time.time()
        load()
        jobCount_i = len(db.get_jobs())
        keywords = SEARCH_CONFIG['search']['keywords']
        salary_min = SEARCH_CONFIG['search']['salary_min']
        jobsite.set_report_parameters([salary_min], keywords)
        jobsite.update_jobRecords()
        screen_jobs()
        new_jobs = len(db.get_jobs())-jobCount_i
        elapsed = time.time()-starttime
        e_min = math.floor(elapsed/60)
        e_sec = elapsed-e_min*60
        print('added %d new jobs in %d min :%d sec' % (new_jobs, e_min, e_sec))


def screen_jobs():
    match.load()
    match.screen_jobs()
    post.update_post_report()


def update_job_profiles(limit=200, screen=True, progress_updates=False):
    #200 records ~ 15 minute runtime
    mcf_profile.load()
    mcf_profile.update_job_profiles(limit, progress_updates)
    if screen:
        screen_jobs()


def get_monday(dateValue):
    return dateValue-dt.timedelta(days=dateValue.weekday())


def get_mondays(date_series):
    return date_series.apply(lambda x:x-dt.timedelta(days=x.weekday()))


def get_weeknums(date_str_series):
    def get_monday(dateValue):
        return dateValue-dt.timedelta(days=dateValue.weekday())
    def get_weeknum(dateValue,this_monday):
        return 1/7*(this_monday-(dateValue-dt.timedelta(days=dateValue.weekday()))).days
    def convert_date_series(date_series):
        return date_series.apply(lambda x:dt.datetime.strptime(x,DATE_FORMAT).date())
    this_monday = get_monday(dt.datetime.now().date())
    date_series = convert_date_series(date_str_series)
    weeknums = date_series.apply(lambda x: get_weeknum(x, this_monday))
    return weeknums


def get_openings_byweek():
    load(db_only=True)
    jobs = db.get_jobs()
    jobs['date'] = jobs.apply(lambda x: dt.datetime.strptime(
        x.posted_date, '%Y-%m-%d').date(),axis=1)
    del jobs['posted_date']
    jobs.rename(columns={'date': 'posted_date'}, inplace=True)
    jobs['monday'] = get_mondays(jobs['posted_date'])
    byweek = pd.pivot_table(jobs, index='monday', aggfunc='size')
    return byweek

# customize how this script runs

def autorun():
    if len(sys.argv) > 1:
        process_name = sys.argv[1]
        if process_name == 'update_jobs_report':
            update_jobs_report()
        elif process_name == 'update_jobRecords':
            if len(sys.argv) > 2:
                notifications = (sys.argv[2] == 'True')
                if len(sys.argv) > 3:
                    page_max = int(sys.argv[3])
                    update_jobRecords(notifications, page_max)
                else:
                    update_jobRecords(notifications)
            else:
                update_jobRecords()
        elif process_name == 'screen_jobs':
            screen_jobs()
        elif process_name == 'update_new_posts':
            post.load()
            post.update_new_posts()
        elif process_name == 'update_job_profiles':
            if len(sys.argv) > 2:
                limit = int(sys.argv[2])
                if len(sys.argv) > 3:
                    screen = (sys.argv[3] == 'True')
                    print('limit %s profiles, score and screen? %s' % (limit, screen))
                    if len(sys.argv) > 4:
                        progress_updates = (sys.argv[4] == 'True')
                        update_job_profiles(limit, screen, progress_updates)
                    else:
                        update_job_profiles(limit, screen)
                else:
                    print('limit %s profiles' % limit)
                    update_job_profiles(limit)
            else:
                update_job_profiles()
        elif process_name == 'run_screening_report':
            run_screening_report()
        else:
            print('report name not found')
    else:
        print('no report specified')


if __name__ == "__main__":
    autorun()

