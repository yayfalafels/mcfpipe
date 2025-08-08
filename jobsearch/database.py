import json
import pandas as pd
import datetime as dt
from sqlalchemy import create_engine
from sqlalchemy import bindparam
from sqlalchemy import text as sqla_text
from sqlalchemy.engine.reflection import Inspector
import gsheet.api as gs

import agent

engine = None
inspector = None
gs_engine = None
CONFIG_FILES = {'search':{'filename':'search_config.json',
                          'data':None},
                'gsheet':{'filename':'gsheet_config.json',
                          'data':None},
                }
NUMERIC_TYPES = ['int','float']
SQL_DB_NAME = 'sqlite:///jobs.db'
GSHEET_CONFIG = {}

table_names = []

sources = [
    {'name':'MyCareerFutures','url':'https://www.mycareersfuture.sg/'},
]

#sqlite db

def load(loadsheet=True):
    global engine, SQL_DB_NAME, table_names
    load_config_files()
    if engine is None:
        engine = create_engine(SQL_DB_NAME, echo=False)
        load_inspector()

    if loadsheet:
        load_gsheet()
        update_config()

def load_config_files():
    global GSHEET_CONFIG
    for f in CONFIG_FILES:
        with open(CONFIG_FILES[f]['filename']) as config_file:
            CONFIG_FILES[f]['data'] = json.load(config_file)
    GSHEET_CONFIG = CONFIG_FILES['gsheet']['data'].copy()


def update_config():
    #search config
    cfg = get_search_config()
    with open(CONFIG_FILES['search']['filename'], 'w') as f:
        json.dump(cfg, f)

    load_config_files()

def get_search_config():
    'update search config settings from gsheet'
    cfg = {
        'search':{
            'salary_min':None,
            'keywords':None
        },
        'match':{
          'match_score_min':None,
          'age_weeks':None
        }
    }
    params = get_sheet('config')
    for grp in cfg:
        for p in cfg[grp]:
            cfg[grp][p] = params[(params['group']==grp) & (params['parameter']==p)]['value'].iloc[0]
    #convert data types
    #salary int
    cfg['search']['salary_min'] = int(cfg['search']['salary_min'])
    #keywords as comma delimited list
    cfg['search']['keywords'] = cfg['search']['keywords'].split(', ')
    #match score min as float
    cfg['match']['match_score_min'] = float(cfg['match']['match_score_min'])
    #change age weeks max to int
    cfg['match']['age_weeks'] = int(cfg['match']['age_weeks'])
    return cfg

def load_inspector():
    global inspector, table_names
    inspector = Inspector.from_engine(engine)
    table_names = inspector.get_table_names()

def setup():
    'this script is used to initialize the database for the first time'
    global sources, engine
    # add sources
    s = pd.DataFrame(sources)
    s.to_sql('source', con=engine, if_exists='replace', index=False)
    # add jobs
    jobs = pd.read_csv(agent.files['job_openings'])
    add_jobs(jobs,append=False)

def table_exists(tableName):
    global inspector, table_names
    load_inspector()
    return tableName in table_names


def update_table(tbl, tblname, append=True):
    global engine
    if append:
        ifex = 'append'
    else:
        ifex = 'replace'
    tbl.to_sql(tblname, con=engine, if_exists=ifex, index=False)

def add_jobs(jobs,append=True):
    global engine
    if append:
        ifex = 'append'
    else:
        ifex = 'replace'
    jobs.to_sql('job', con=engine, if_exists=ifex, index=False)


def update_match(new_matches, update=True):
    global engine
    match = get_table('match')
    if match is None:
        match = new_matches
    else:
        new_matches.set_index('jobid', inplace=True)
        match.set_index('jobid', inplace=True)
        match.update(new_matches)
        match.reset_index(inplace=True)
    match.to_sql('match', con=engine, if_exists='replace', index=False)

def get_sources():
    global engine
    s = pd.read_sql_table('source',con=engine)
    return s

def get_jobs():
    global engine
    jobs = pd.read_sql_table('job',con=engine)
    return jobs


def remove_jobs(jobids):
    if jobids:
        stmt = sqla_text("DELETE FROM job WHERE jobid IN :ids").bindparams(
            bindparam("ids", expanding=True)
        )
        # this works for sqlite but not necessarily for other backend
        with engine.connect() as conn:
            conn.execute(stmt, {"ids": jobids})


def get_table(tableName):
    if table_exists(tableName):
        tbl = pd.read_sql_table(tableName,con=engine)
    else:
        tbl = None
    return tbl

#gsheet

def load_gsheet():
    global gs_engine
    if gs_engine is None:
        gs_engine = gs.SheetsEngine()

def post_to_gsheet(df,rng_code,input_option='RAW'):
    #values is a 2D list [[]]
    wkbid = GSHEET_CONFIG['wkbid']
    rngid = GSHEET_CONFIG[rng_code]['data']
    values = df.values.astype('str').tolist()
    gs_engine.clear_rangevalues(wkbid,rngid)
    #write values - this method writes everything as a string
    gs_engine.set_rangevalues(wkbid,rngid,values,input_option)

#----------------------------------------------------------------------------------------
#Work in progress
#----------------------------------------------------------------------------------------

def get_sheet(rng_code):
    wkbid = GSHEET_CONFIG['wkbid']
    rng_config = GSHEET_CONFIG[rng_code]
    rngid = rng_config['data']; hdrid = rng_config['header']
    valueList = gs_engine.get_rangevalues(wkbid,rngid)
    header = gs_engine.get_rangevalues(wkbid,hdrid)[0]
    rng = pd.DataFrame(valueList, columns=header)
    if 'data_types' in rng_config:
        data_types = rng_config['data_types']
        for field in data_types:
            typeId = data_types[field]
            if not typeId in ['str','date']:
                if typeId in NUMERIC_TYPES:
                    #to deal with conversion from '' to nan
                    if typeId in ['float']: #nan compatible
                        rng[field] = pd.to_numeric(rng[field]).astype(typeId)
                    else: #nan incompatible types
                        rng[field] = pd.to_numeric(rng[field]).fillna(0).astype(typeId)
                else:
                    rng[field] = rng[field].astype(typeId)
            if typeId == 'date':
                if 'date_format' in rng_config:
                    rng[field] = rng[field].fillna('')
                    rng[field] = rng[field].apply(
                        lambda x: dt.datetime.strptime(x, rng_config['date_format'])
                    if len(x) > 0 else None)
    return rng

def get_tags():
    print('temporarily out of service')
    return None
#    tags = pd.read_sql_table('tag',con=engine)
#    return tags

def update_tags():
    print('temporarily out of service')
#    wkbid = GSHEET_CONFIG['wkbid']
#    rngid = GSHEET_CONFIG['tags']
#    taglist = gs_engine.get_rangevalues(wkbid,rngid)
#    tags = pd.DataFrame(taglist, columns=['tag', 'tag_type','group','score'])
#    tags.to_sql('tag',con=engine,if_exists='replace',index=False)

