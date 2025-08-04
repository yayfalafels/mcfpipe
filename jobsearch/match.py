#----------------------------------------------------
#Module dependencies
#----------------------------------------------------
import pandas as pd
import numpy as np
import datetime as dt

import database as db
import mcf_profile as prf
import text as tx
import report

#----------------------------------------------------
#Static variables
#----------------------------------------------------
TODAY_DATE = ''
TITLE_SCORE_BATCH = 500
SALARY_PCT_DEFAULT = 0
profiles = None
matches = None
screened = None

SEARCH_CONFIG = {}

#----------------------------------------------------
#Setup, initialization
#----------------------------------------------------

def load():
    db.load()
    tx.load()
    load_config()

def load_config():
    global SEARCH_CONFIG, TODAY_DATE
    SEARCH_CONFIG = db.CONFIG_FILES['search']['data']
    TODAY_DATE = dt.datetime.now().date()


def load_job_profiles():
    'load job profiles from sql, append fields from job card and group by industry'
    global profiles
    def get_profiles_by_ic(profiles, ic):
        hasic = profiles[~profiles.industry_classification.isnull()].copy()
        subset = hasic[hasic.industry_classification.str.contains(ic)]
        return subset

    #01 load jobs tbl
    jobs_all = db.get_jobs()
    #01b filter for past 90 days
    cutoff_date = dt.datetime.now().date() - dt.timedelta(days=90)
    jobs_all['posted_date_dt'] = jobs_all.posted_date.apply(
        lambda x: dt.datetime.strptime(x, '%Y-%m-%d').date())
    jobs = jobs_all[jobs_all.posted_date_dt > cutoff_date].copy()
    del jobs['posted_date_dt']
    #02 load profiles tbl
    prf.load(db_only=True)
    profiles = prf.profiles.copy()
    #03 merge, group by industry and save to profiles
    profiles = pd.merge(profiles, jobs, on='jobid')
    #convert date format to datetime.date
    profiles['closing_date'] = profiles['closing_date'].apply(lambda x: x.date())
    #ics = get_ics('focus')
    #subsets = []
    #for ic in ics:
    #    subset = get_profiles_by_ic(profiles, ic)
    #    ss_wo_salary = subset[pd.isnull(subset.salaryHigh)].copy()
    #    if len(ss_wo_salary) > 0:
    #        ss_w_salary = subset[not pd.isnull(subset.salaryHigh)].copy()
    #        if len(ss_w_salary) > 0:
    #            ss_w_salary['salary_pct'] = ss_w_salary.salaryHigh.rank(pct=True)
    #            ss_w_salary['ic'] = ic
    #            subsets.append(ss_w_salary)
    #        ss_wo_salary['ic'] = ic
    #        subsets.append(ss_wo_salary)
    #    else:
    #        subset['salary_pct'] = subset.salaryHigh.rank(pct=True)
    #        subset['ic'] = ic
    #        subsets.append(subset)
    #
    #profiles = pd.concat(subsets)
    profiles['salary_pct'] = SALARY_PCT_DEFAULT
    profiles.drop_duplicates(subset=['jobid'], inplace=True)
    profiles.set_index('jobid', inplace=True)

#----------------------------------------------------
#Reports
#----------------------------------------------------

def screen_jobs():
    ''' Screens jobs based on qualification match by keyword tags
    and job post age (in weeks) The inputs are the job and tag tables
     and there are two outputs - an updated sqlite table ‘match’
     and the screened jobs posted to gsheet.

     The process is divided into two general steps - scoring and filtering.
     Scoring cleans up and deranks the title and extract bigram tags,
     calculates match_auto from the clean,deranked title from the
     extracted tags and the role rank : salary_pct.

     The screened table filters based on the match score and
      current applications based on number of weeks from today to
      the posted_date.'''

    #01 update manual evaluations
    prf.update_evaluations()

    #02 cleanup title, extract tags, score title
    #03 store the match_auto score in the sqlite match table
    update_matches()

    if profiles is not None:
        if len(profiles) > 0:
            #04 drop the jobs below min match score, filter for most recent posts
            #05 push update to gsheet
            update_screened()


def get_match_report():
    global jobs
    print('under construction')
    #tx.load_jobs(jobs)
    #tx.run_jobtitle_report()
    #titles = tx.jobs['titles'].copy()

#----------------------------------------------------
#Match score
#----------------------------------------------------

def update_matches():
    '''updates the match table from the titles table by dropping fields
    '''
    global profiles, matches
    #fields to keep : jobid, clean_title, match_auto
    fields = ['jobid', 'clean_title', 'match_auto']
    score_positions()
    if profiles is not None:
        if len(profiles) > 0:
            matches = profiles.reset_index()[fields].copy()
            db.update_match(matches)


def get_match_score_range():
    return profiles.match_score.unique()


def match_selectivity(score=0):
    pvt = pd.pivot_table(profiles,index='match_score',values='urlid',aggfunc='count')
    pvt['cum'] = pvt.urlid.cumsum()
    selectivity = 1 - pvt.loc[score].cum / pvt.urlid.sum()
    return selectivity

def score_positions():
    ''' scores positions using text.py to cleanup title, extract bigram tags
    and compute score from extracted tags
    '''
    global profiles
    score_profile_title()
    if profiles is not None:
        if len(profiles) > 0:
            profiles['match_auto'] = profiles.apply(
                lambda x: match_score(x['salary_pct'], x['title_score']), axis=1)


def match_score(pct, title_score):
    if title_score > 0:
        quantile = 3
        if not pd.isnull(pct):
            if pct < 1:
                quantile = 1+[pct < x for x in [0.25, 0.5, 0.75, 1]].index(True)
            else:
                quantile = 4
        score = 1/quantile*(1+title_score)
    else:
        score = 0
    return score


def score_profile_title(unscored=None):
    if unscored is None:
        global profiles

        #01 load job profiles from sql
        load_job_profiles()
        unscored = profiles.copy()
        profile_count = len(unscored)
        if profile_count == 0:
            print(f'WARNING: no job profiles to score.')
            scored = unscored.copy()
        elif profile_count <= TITLE_SCORE_BATCH:
            scored = score_profile_title(unscored)
        else:
            batch_ids = [i//TITLE_SCORE_BATCH
                         for i in list(range(0, profile_count))]
            batch_count = max(batch_ids) + 1
            unscored_batches = [unscored.iloc[batch_ids.index(i):batch_ids.index(i + 1)]
                       for i in range(batch_count - 1)] + [
                unscored.iloc[batch_ids.index(batch_count - 1):]]
            scored_batches = []
            for u in unscored_batches:
                s = score_profile_title(u)
                scored_batches.append(s)
            scored = pd.concat(scored_batches)

        profiles = scored.copy()
    else:
        scored = unscored.copy()
        #03 get bigram matrix from profiles
        tx.push_tag_gsheets_to_sql(skip=['title'])
        scored = tx.add_clean_deranked_titles(scored)
        #try:
        feature_names, X_v = tx.get_bigram_matrix(scored.deranked_title)
        title_tags = tx.tag_sheets['title']['data'].copy()
        feature_scores = pd.merge(pd.DataFrame({'tag': feature_names}),
                                  title_tags[['tag', 'score']], on='tag', how='left')['score'].values
        feature_scores = [0 if pd.isna(x) else x for x in feature_scores]
        title_scores = tx.np.array(tx.np.matmul(X_v.todense(),
                                                tx.np.array(feature_scores).transpose()))[0]
        scored['title_score'] = title_scores
        #except:
        #    pass
        return scored

#----------------------------------------------------
#Screening
#----------------------------------------------------

def update_screened():
    ''' drops the rejected positions and filters for recent based on posted_date
    '''
    global profiles, screened
    weeks = SEARCH_CONFIG['match']['age_weeks']
    match_score_min = SEARCH_CONFIG['match']['match_score_min']
    fields = ['match_auto','week','clean_title','company_name', 'jobid', 'url','salaryHigh','salary_pct',
              'years_experience','applicants','posted_date','closing_date','deranked_title',
              'position_title','description', 'src_methodid']

    screened = profiles.reset_index()[[x for x in fields if not x == 'week']]
    screened.fillna(0, inplace=True)
    screened = add_weeks(screened)
    recent = screened[(screened['week'] <= weeks) & (screened['closing_date'] != 0)].copy()
    recent = recent[recent['closing_date'] >= TODAY_DATE].copy()
    keep = recent[(recent.match_auto >= match_score_min) | (recent.src_methodid == 1)]
    screened = keep[fields].sort_values(['week', 'match_auto'], ascending=(True, False))
    #post to gsheet
    db.post_to_gsheet(screened, 'screened')


def add_weeks(df):
    df['date'] = df.apply(lambda x: dt.datetime.strptime(
        x.posted_date, report.DATE_FORMAT).date(),axis=1)
    del df['posted_date']
    df.rename(columns={'date': 'posted_date'}, inplace=True)
    df['monday'] = report.get_mondays(df['posted_date'])
    monday = report.get_monday(dt.datetime.today().date())
    df['week'] = df.apply(lambda x: int((monday - x.monday).days / 7), axis=1)
    del df['monday']
    return df

#----------------------------------------------------
#Tags
#----------------------------------------------------

def update_tags():
    'update tag library with new bigrams from job profiles'
    global profiles
    #01 load job profiles from sql
    load_job_profiles()
    #02 get new bigrams from job profiles
    tx.push_tag_gsheets_to_sql()
    bigrams = tx.get_new_bigrams(profiles,export=True).set_index('tag')
    #03 compare to current tag library and break into new and current
    if len(bigrams) > 0:
        lib = tx.tag_tbls['title']['data'].set_index('tag').copy()
        current_tags = list(set(bigrams.index).intersection(set(lib.index)))
        new_tags = list(set(bigrams.index).difference(set(lib.index)))
        #04 update current with new counts
        if len(current_tags) > 0:
            #current_bg = lib.loc[current_tags]
            lib.update(bigrams.loc[current_tags])
        if len(new_tags)>0:
            new_bg = bigrams.loc[new_tags]
        #05 append new bigram tags to current library
        scenario = 2*int(len(current_tags) > 0) + int(len(new_tags)>0)
        if scenario == 3:   # current + new (append)
            title = pd.concat([lib,new_bg])
        elif scenario == 2: # current only (title = current)
            title = lib
        else:               # new only (title = new)
            title = new_bg
            title['industry'] = np.nan
            title['score'] = np.nan
        #06 sort table by industry and score
        title.reset_index(inplace=True)
        title.sort_values(['industry', 'count'], ascending=[True,False], inplace=True)
        #07 push updates to sql and gsheet
        rng_code = tx.tag_sheets['title']['name']
        db.post_to_gsheet(title,rng_code,input_option='USER_ENTERED')


def get_ics(list_type='keep'):
    ic = tx.tag_sheets['ic']['data']
    field_name = 'industry_classification'
    if list_type == 'keep':
        ics = ic[ic.match >- 1][field_name].values
    elif list_type == 'focus':
        ics = ic[ic.match == 1][field_name].values
    elif list_type == 'drop':
        ics = ic[ic.match == -1][field_name].values
    return ics

#get frequency distribution of tags
def get_tag_counts(tag_type,norm=False):
    print('under construction')
#    #unpack the tags which are separated by colon and convert into a dataframe
#    tag_df  = pd.DataFrame({tag_type:[x for y in titles[tag_type].tolist()
#                                      for x in y.split(':') if not x=='']})
#    #pivot the dataframe
#    counts = pd.pivot_table(tag_df, index=tag_type, aggfunc='size').sort_values(ascending=False)
#    if norm:
#        counts = counts/sum(counts)
#    return counts

#----------------------------------------------------
#**
#----------------------------------------------------