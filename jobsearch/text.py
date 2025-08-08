import re
import numpy as np
import pandas as pd
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import CountVectorizer

import database as db

#----------------------------------------------------
#Static variables
#----------------------------------------------------
MIN_DF = 5
tag_sheets = {}
tag_tbls = {}

#----------------------------------------------------
#Setup, initialization
#----------------------------------------------------

def load():
    'load tags and job profiles from gsheet and sql'
    db.load()
    load_gsheet()
    load_sql()

def load_gsheet():
    load_tags_gsheet()

def load_sql():
    load_tags_sql()

def load_tags_gsheet():
    global tag_sheets
    title_tags = db.get_sheet('title_tags')
    junk_tags = db.get_sheet('junk_tags')
    keep_tags = db.get_sheet('keep_tags')
    rank_tags = db.get_sheet('rank_tags')
    keyword_tags = db.get_sheet('keyword_tags')
    cv = db.get_sheet('cv')
    industries = db.get_sheet('industries')
    tag_sheets = {'title':{'data':title_tags,
                           'name':'title_tags'},
                  'rank':{'data':rank_tags,
                          'name':'rank_tags'},
                  'keep':{'data':keep_tags,
                          'name':'keep_tags'},
                  'junk':{'data':junk_tags,
                          'name':'junk_tags'},
                  'kw_profile':{'data':keyword_tags,
                          'name':'keyword_tags'},
                  'kw_cv':{'data':cv,
                          'name':'cv'},
                  'ic': {'data':industries,
                         'name':'industries'}
                  }

def load_tags_sql():
    global tag_tbls
    title_tbl = db.get_table('title_tag')
    junk_tbl = db.get_table('junk_tag')
    keep_tbl = db.get_table('keep_tag')
    rank_tbl = db.get_table('rank_tag')
    kw_profile_tbl = db.get_table('kw_profile')
    kw_cv_tbl = db.get_table('kw_cv')
    ic_tbl = db.get_table('industry_classification')
    tag_tbls = {'title':{'data':title_tbl,
                         'name':'title_tag'},
                'rank':{'data':rank_tbl,
                        'name':'rank_tag'},
                'keep':{'data':keep_tbl,
                        'name':'keep_tag'},
                'junk':{'data':junk_tbl,
                        'name':'junk_tag'},
                'kw_profile':{'data':kw_profile_tbl,
                        'name':'kw_profile'},
                'kw_cv':{'data':kw_cv_tbl,
                        'name':'kw_cv'},
                'ic': {'data':ic_tbl,
                       'name':'industry_classification'}
                }

# ----------------------------------------------------
# Procedures
# ----------------------------------------------------

def push_tag_gsheets_to_sql(skip=[]):
    for tag_type in tag_sheets:
        if not tag_type in skip:
            db.update_table(tag_sheets[tag_type]['data'],
                            tag_tbls[tag_type]['name'], append=False)
    load_tags_sql()

# ----------------------------------------------------
# Text analysis
# ----------------------------------------------------

def drop_paren(strValue,parentag='('):
    noparen = strValue
    retag = r''
    if parentag == '(':
        retag = r'\(([^\)]+)\)'
    elif parentag == '[':
        retag = r'\[(.*?)\]'
    parentk = re.search(retag,strValue)
    if not parentk is None:
        parentk = parentk[0]
        noparen = strValue.replace(parentk,'')
    return noparen

def selective_token_cleanup(strValue,cleanup_list,strict_word=False):
    for tag in cleanup_list:
        if tag in strValue:
            if strict_word:
                strValue = strValue.replace(' '+tag+' ',' ')
            else:
                if ' ' in tag:
                    strValue = re.sub(' ('+tag+')|('+tag+') ',' ',strValue)
                else:
                    strValue = re.sub('\\b'+tag+'\\b','',strValue)
    trimmed = strValue.strip()
    return trimmed

def remove_ampersand(strValue):
    strValue = strValue.replace('mampe','me') #mechanical and electrical
    strValue = strValue.replace('rampd','rd') #research and development
    strValue = strValue.replace('oampg','og') #oil and gas
    strValue = strValue = re.sub(' (amp)|(amp) ',' and ',strValue)
    trimmed = strValue.strip()
    return trimmed

def remove_stopwords(strValue,strict_word=False):
    keepList = tag_tbls['keep']['data']['tag'].values
    wordlist = [x for x in stopwords.words('english') if not x in keepList]
    cleanStr = selective_token_cleanup(strValue,wordlist,strict_word=strict_word)
    return cleanStr

def cleanup(strValue):
    # keep only alphabet characters
    letterStr = re.sub('[^a-zA-Z ]+','',strValue)
    # lower case only
    lowerStr = letterStr.lower()
    # remove ampersand &
    noamp = remove_ampersand(lowerStr)
    # remove extra spaces on ends (not inbetween)
    trimmed = noamp.strip()
    return trimmed

def remove_junk(strValue):
    cleanStr = cleanup(strValue)
    nostop = remove_stopwords(cleanStr)
    junkwords = tag_tbls['junk']['data']['tag'].values
    cleanStr = selective_token_cleanup(nostop,junkwords)
    trimmed = cleanStr.strip()
    return trimmed

def derank(strValue):
    rankwords = tag_tbls['rank']['data']['tag'].values
    cleanStr = selective_token_cleanup(strValue,rankwords)
    trimmed = cleanStr.strip()
    return trimmed

def add_clean_deranked_titles(profiles):
    #01 clean-up, dejunk title
    profiles['clean_title'] = profiles['position_title'].apply(lambda x:remove_junk(x))
    #02 derank title
    profiles['deranked_title'] = profiles['clean_title'].apply(lambda x:derank(x))
    return profiles

def get_bigram_matrix(titles):
    n_categories = len(set(titles))
    n_rows = len(titles)
    try:
        vect = CountVectorizer(min_df=MIN_DF, ngram_range=(2, 2), analyzer='word').fit(titles)
    except:
        print(f'WARNING. small dataset: {n_rows} rows and {n_categories} unique values. Reducing minimum document frequency setting from {MIN_DF} to 1.')
        try:
            vect = CountVectorizer(min_df=1, ngram_range=(2, 2), analyzer='word').fit(titles)
        except Exception as e:
            if 'pruning' in str(e):
                print(f'ERROR. dataset too small. Data contains {n_rows} rows and {n_categories} unique values.')
            raise e
    feature_names = np.array(vect.get_feature_names_out())
    X_v = vect.transform(titles)
    return (feature_names, X_v)

def get_new_bigrams(profiles,export=False):
    #01 clean-up, dejunk, derank title
    profiles = add_clean_deranked_titles(profiles)
    #03 get bigram matrix using CountVectorizer (sklearn)
    feature_names, X_v = get_bigram_matrix(profiles.deranked_title)
    #05 create the bigram table
    feature_counts = [np.sum(X_v[:, x]) for x in range(len(feature_names))]
    feature_counts = [x/np.sum(feature_counts) for x in feature_counts]
    bigrams = pd.DataFrame({'tag': feature_names, 'count': feature_counts})
    bigrams.sort_values('count', ascending=False, inplace=True)
    if export:
        bigrams.to_csv('bigrams.csv',index=False)
    return bigrams

# ----------------------------------------------------
# ***
# ----------------------------------------------------