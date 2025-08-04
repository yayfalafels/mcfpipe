""" automate applications through MyCareerFutures website
process steps
1. login google sheets download list of jobs to apply
       - identify the job track
       - identify the CV to apply associated with the job track
2. connect to existing authenticated session, or exit and return error message
3. apply to jobs
       load job url
       find and submit the apply button
       find and select the CV
       page through the 1-click application pages
       exit if run into a questionnaire
 """

# dependencies -----------------------------------------------
import json
from playwright.sync_api import sync_playwright
import pandas as pd
import database as db


# constants -----------------------------------------------
JOB_SITE = 'MyCareerFutures'
USER_PROFILE_DEFAULT_PATH = r'C:\Users\taylo\AppData\Local\Google\Chrome\User Data'
JOB_URL_SAMPLE = 'https://www.mycareersfuture.gov.sg/job/information-technology/data-engineer-singapore-geco-asia-3db999d67abd067752ad5eb59330e1d7'
#JOB_URL_SAMPLE = 'https://www.mycareersfuture.gov.sg/job/information-technology/data-engineer-dna-infotech-0a5a1235196f5385595c3d6b85e8a95c'
#JOB_URL_SAMPLE = 'https://www.mycareersfuture.gov.sg/job/information-technology/data-engineer-apar-technologies-a1d1c92309fabdaf66601ecce3cdf09b'
#JOB_URL_SAMPLE = 'https://www.mycareersfuture.gov.sg/job/information-technology/gen-ai-enterprise-architect-joule-sap-asia-409337eab78651a131dca55afbd609dd'
JOB_SLUG_SAMPLE = '/information-technology/data-engineer-python-ci-cd-devops-data-fabric-randstad-042ff768f5bf95bbceca4ac9936510d2'
COOKIES_JSON_FILE = 'cookies_mcf.json'
LOGGING_LEVEL = 1
BROWSER_HEADLESS = True
MAX_RETRY = 5
PAGE_DELAY_MS = 500
RETRY_DELAY_MS = 5000
TO_APPLY_GSHEET = 'apply_in_process'
RESULTS_GSHEET = 'apply_results'
TO_APPLY_FIELDS = [
    'jobid',
    'url',
    'cv_version'
]

SITE_ELEMENTS = [
    {
        'site': 'MyCareerFutures',
        'domain': '.mycareersfuture.gov.sg',
        'homepage': 'https://www.mycareersfuture.gov.sg/',
        'page_elements': [
            {
                'page': 'job_post',
                'element': 'apply_button',
                'button_selector': 'button#job-details-apply-button',
                'click_delay_ms': PAGE_DELAY_MS
            },
            {
                'page': 'job_post',
                'element': 'apply_message',
                'message_selector': 'p[data-testid="job-apply-error"]'
            },
            {
                'page': 'job_apply',
                'element': 'page_advance',
                'button_locator': 'button#application-details-save-button',
                'click_delay_ms': PAGE_DELAY_MS
            },
            {
                'page': 'cv_select',
                'element': 'cv_cards',
                'element_locator': 'div[data-testid="resume-card"]'
            },
            {
                'page': 'cv_select',
                'element': 'cv_radio',
                'element_locator': 'input[type="radio"]'
            },
            {
                'page': 'apply_review',
                'element': 'submit',
                'button_locator': 'button#job-application-review__submit-button'
            }
        ]
    }
]


# classes -----------------------------------------------
class ChromeBrowser(object):
    pw = None
    pwb = None
    session = None
    page = None
    errors = ''
    cookies_json_file = COOKIES_JSON_FILE
    cookie_domain = ''
    config = {
        'headless': BROWSER_HEADLESS
    }
    def __init__(self, browser_config={}, **kwargs):
        for k in browser_config:
            self.config.update({k: browser_config[k]})
        for k in kwargs:
            setattr(self, k, kwargs[k])

    def __enter__(self):
        self.pw = sync_playwright().start()
        self.session_connect()
        return self

    def _exception_handle(self, msg='', exception=None, re_raise=True, fatal=True):
        if exception:
            ex_msg = f'ERROR. {msg}. {str(exception)}'
        else:
            ex_msg = msg
        self.errors = ex_msg
        if re_raise and exception:
            print(ex_msg)
            raise exception
        if fatal:
            self._safe_exit()

    def errors_refresh(self):
        self.errors = ''

    def __exit__(self, exc_type, exc_value, traceback):
        self._safe_exit()

    def _safe_exit(self):
        self.page_close()
        self.session_close()
        if self.pw:
            self.pw.stop()
            self.pw = None

    def session_close(self):
        if self.pwb:
            self.pwb.close()
            self.pwb = None
        if self.session:
            try:
                self.session.close()
            except:
                pass
            self.session = None

    def page_close(self):
        if self.page:
            if not self.page.is_closed():
                self.page.close()
            self.page = None

    def session_connect(self):
        cookies_loaded = False
        connect_success = False
        connect_fail_msg = 'failed to connect to Chrome browser session'
        cookie_fail_msg = 'failed to load cookies'
        try:
            self.pwb = self.pw.chromium.launch(headless=self.config['headless'])
            self.session = self.pwb.new_context()
            try:
                pw_cookies = get_pwcookies(self.cookies_json_file)
            except Exception as e:
                self._exception_handle(msg=cookie_fail_msg, exception=e)
            else:
                if pw_cookies:
                    self.session.add_cookies(pw_cookies)
                    for c in self.session.cookies():
                        if not cookies_loaded:
                            cookies_loaded = c['domain'] == self.cookie_domain
                    if cookies_loaded:
                        if LOGGING_LEVEL == 0:
                            print(f'cookies loaded for domain {self.cookie_domain}')
                    else:
                        self._exception_handle(msg=connect_fail_msg)
                else:
                    self._exception_handle(msg=cookie_fail_msg)
        except Exception as e:
            self._exception_handle(msg=connect_fail_msg, exception=e)            
        connect_success = self.session is not None and cookies_loaded        
        if LOGGING_LEVEL < 2:
            con_success_str = 'success' if connect_success else 'failed'
            print(f'INFO. browser connected? {con_success_str}')
        if not connect_success:
            self._exception_handle(msg=connect_fail_msg)
        return connect_success 

    def page_refresh(self):
        page_success = False
        if self.session:
            self.page = self.session.new_page()
            page_success = self.page is not None
        else:
            connect_success = self.session_connect()
            if connect_success:
                page_success = self.page_refresh()
        return page_success


class MCFSiteBrowser(ChromeBrowser):
    domain = ''
    homepage = ''
    site_config = {}
    page_elements = []
    def __init__(self, browser_config={}, site_config={}, **kwargs):
        super().__init__(browser_config=browser_config, **kwargs)
        self._set_site_config(site_config=site_config)

    def _set_site_config(self, site_config={}):
        if not site_config:
            site_config = [c for c in SITE_ELEMENTS if c['site'] == 'MyCareerFutures'][0]
        self.site_config = site_config
        self.homepage = self.site_config.get('homepage', '')
        self.domain = self.site_config.get('domain', '')
        self.page_elements = self.site_config.get('page_elements', [])

    def job_page_url(self, slug):
        url = f'{self.homepage}job{slug}'
        return url

    def homepage_load(self):
        self.page.goto(self.homepage)

    def page_load(self, slug='', url=''):
        if not url:
            url = self.job_page_url(slug)
        self.page.goto(url)

    def get_page_element(self, page, element):
        page_element = {}
        page_element_search = [e for e in self.page_elements if (e['page'] == page) & (e['element'] == element)]
        page_element = page_element_search[0] if page_element_search else {}
        return page_element

    def apply_page_advance(self):
        success = True
        errors = ''
        try:
            page_element = self.get_page_element('job_apply', 'page_advance')
            advance_locator = page_element.get('button_locator', '')
            click_delay_ms = page_element.get('click_delay_ms', 500)
            self.page.locator(advance_locator).click()
            self.page.wait_for_timeout(click_delay_ms)
        except Exception as e:
            success = False
            errors = f'ERROR. failed to advance to next page. {e}'
        return success, errors

    def apply_start(self):
        success = False
        apply_status = ''
        errors = ''

        try:
            page_element = self.get_page_element('job_post', 'apply_button')
            apply_selector = page_element.get('button_selector', '')
            click_delay_ms = page_element.get('click_delay_ms', 500)

            for attempt in range(MAX_RETRY):
                try:
                    self.page.wait_for_selector(apply_selector, timeout=5000)
                    submit_locator = self.page.locator(apply_selector)
                    # Case 1: Apply button is present → proceed with click
                    if submit_locator.is_visible() and submit_locator.is_enabled():
                        success = True
                        apply_status = '01_applied'
                        submit_locator.click()
                        self.page.wait_for_timeout(click_delay_ms)
                        break
                    else:
                        # Case 2: Apply button not found — check page content for closed or already applied
                        apply_msg_text = ''
                        page_element = self.get_page_element('job_post', 'apply_message')
                        message_selector = page_element.get('message_selector', '')
                        apply_msg_locator = self.page.locator(message_selector)
                        if apply_msg_locator:
                            apply_msg_text = apply_msg_locator.inner_text().lower()

                        if 'already' in apply_msg_text or 'applied' in apply_msg_text:
                            #message: "you have already applied for this job"
                            success = True
                            apply_status = '01_applied'
                            errors = 'INFO. Job already applied.'
                            break
                        elif 'closed' in apply_msg_text or 'no longer' in apply_msg_text:
                            # message: "applications have closed for this job"
                            apply_status = '07_post_closed'
                            errors = 'INFO. Application has closed.'
                            break

                except Exception:
                    self.page.wait_for_timeout(RETRY_DELAY_MS)

            if apply_status == '':
                apply_status = '04_unable_to_apply'
                errors = f'WARNING. Apply button not found and no matching message detected after {MAX_RETRY} retry attempts.'

        except Exception as e:
            apply_status = '04_unable_to_apply'
            errors = f'ERROR. Exception occurred while starting application: {e}'

        return success, apply_status, errors

    def apply_submit(self):
        success = True
        errors = ''
        try:
            page_element = self.get_page_element('apply_review', 'submit')
            submit_selector = page_element.get('button_locator', '')
            self.page.wait_for_selector(submit_selector, timeout=3000)
            submit_locator = self.page.locator(submit_selector)
            if submit_locator.is_visible() and submit_locator.is_enabled():
                submit_locator.click()
            else:
                success = False
                errors = 'ERROR. Submit button present but not clickable.'
        except Exception as e:
            success = False
            errors = f'ERROR. failed to start application. {e}'
        return success, errors

    def cv_select(self, cv_version):
        select_success = True
        select_errors = ''
        try:
            cards_element = self.get_page_element('cv_select', 'cv_cards')
            cards_selector = cards_element.get('element_locator', '')
            self.page.wait_for_selector(cards_selector, timeout=3000)
            cv_cards = self.page.locator(cards_selector)
        except Exception as e:
            select_success = False
            select_errors = f'ERROR. failed to locate cv cards on page. {e}'

        if select_success:
            select_success = False
            cv_options = []
            for i in range(cv_cards.count()):
                card = cv_cards.nth(i)
                title_elem = card.locator('a.resume-link')
                title_str = title_elem.inner_text()
                cv_options.append(title_str)
                if cv_version in title_str:
                    select_success = True
                    try:
                        radio_element = self.get_page_element('cv_select', 'cv_radio')
                        radio_locator = radio_element.get('element_locator', '')
                        card.locator(radio_locator).click()
                    except Exception as e:
                        select_success = False
                        select_errors = f'ERROR. failed to locate and select the radio button for cv {cv_version}. {e}'
                    break
            if not select_success:
                select_errors = f'ERROR. cv {cv_version} not found among options {cv_options}.'

        if select_success:
            select_success, select_errors = self.apply_page_advance()

        return select_success, select_errors


# module variables ----------------------------------------
browser = None
apply_results = []
jobs_to_apply = []
#jobs_to_apply = [
#    {
#        'jobid': 'MyCareerFutures-3db999d67abd067752ad5eb59330e1d7-2025-05-14',
#        'slug': '',
#        'url': JOB_URL_SAMPLE,
#        'cv_version': '11.4',
#        'success': False,
#        'apply_status': '',
#        'errors': ''
#    }
#]


def get_pwcookies(cookies_json_file):
    pw_cookies = []
    with open(cookies_json_file, 'r') as f:
        cookies = json.load(f)

    for c in cookies:
        same_site = c.get("sameSite", "").lower()
        if same_site == "no_restriction":
            same_site = "None"
        elif same_site == "lax":
            same_site = "Lax"
        elif same_site == "strict":
            same_site = "Strict"
        else:
            same_site = "Lax"  # default fallback if missing or unrecognized

        pw_cookies.append({
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c["path"],
            "secure": c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
            "sameSite": same_site
        })
    return pw_cookies


# main -----------------------------------------------------
def run():
    global browser
    no_jobs = 0
    to_apply_success, to_apply_errors = fetch_jobs_to_apply()
    if to_apply_success:
        no_jobs = len(jobs_to_apply)

    apply_success = False
    apply_errors = ''
    if to_apply_success and no_jobs > 0:
        site_config = [c for c in SITE_ELEMENTS if c['site'] == JOB_SITE][0]
        domain = site_config.get('domain', '')
        try:
            with MCFSiteBrowser(
                site_config=site_config, 
                cookie_domain=domain, 
                cookies_json_file=COOKIES_JSON_FILE
                ) as browser:
                load_success, load_errors = site_load()
                if load_success:
                    apply_success, apply_errors = jobs_apply()
                else:
                    print(f'ERROR. failed to load Chrome Browser. {load_errors}')
        except Exception as e:
            ex_msg = browser.errors if browser is not None else ''
            print(f'ERROR. Exception encountered during browswer session. {ex_msg}. {e}')
    else:
        if to_apply_success:
            if LOGGING_LEVEL < 2:
                print(f'INFO. no jobs to apply.')
        else:
            print(f'ERROR. failed to fetch job posts to apply from google sheets. {to_apply_errors}')

    post_success = False
    post_errors = ''
    if apply_success:
        if LOGGING_LEVEL == 0:
            print(f'jobs applied results: {apply_results}')
        post_success, post_errors = results_post()
    elif apply_errors:
        print(f'ERROR. problem applying for jobs. {apply_errors}')
    if post_success:
        if LOGGING_LEVEL == 0:
            print(f'INFO. posted results to google sheets.')
    if post_errors:
        print(f'ERROR. failed to post results to Google Sheets. {post_errors}')


def fetch_jobs_to_apply():
    global jobs_to_apply, apply_results
    fetch_success = True
    fetch_errors = ''
    to_apply_count = 0
    if LOGGING_LEVEL == 0:
        print(f'INFO. fetching jobs to apply from google sheets ...')

    try:
        db.load()
        in_process = db.get_sheet(TO_APPLY_GSHEET)
        prior_results = db.get_sheet(RESULTS_GSHEET)
    except Exception as e:
        fetch_success = False
        extra_info = 'blank column in google sheet. consider adding empty string to errors' if 'passed, passed' in str(e) else ''
        fetch_errors = f'ERROR. problem fetching jobs to apply from google sheet {TO_APPLY_GSHEET} and in process from {RESULTS_GSHEET}. {extra_info} {e}'
    else:
        if LOGGING_LEVEL == 0:
            print(f'INFO. fetched google sheet {TO_APPLY_GSHEET}. processing jobs from table ...')
        open_attempts_df = in_process.copy()
        applied_exclude = []
        applied_count = 0
        if len(prior_results) > 0:
            already_applied = list(set(prior_results[prior_results['applied'] == '1']['jobid']))
            applied_count = len(already_applied)
        if applied_count > 0:
            try:
                applied_exclude = in_process[in_process['jobid'].isin(already_applied)].copy()
                open_attempts_df = in_process[~in_process['jobid'].isin(already_applied)].copy()
            except Exception as e:
                print(f"""WARNING. found {applied_count} application{'s' if applied_count>1 else ''} 
                      already completed but failed to exclude them. 
                      \n Including them in the list of jobs to apply. {e}""")
            else:
                if len(applied_exclude) > 0:
                    if LOGGING_LEVEL == 0:
                        print(f'INFO. excluding {len(applied_exclude)} jobs which have already been applied.')
                    to_exclude = applied_exclude.to_dict(orient='records')
                    for j in to_exclude:
                        apply_result = {
                            'jobid': j.get('jobid', '*'),
                            'applied': 1,
                            'apply_result': '01_applied',
                            'errors': 'INFO. already applied.'
                        }
                        apply_results.append(apply_result)
                if len(open_attempts_df) == 0:
                    fetch_errors = 'all open jobs already applied for'
        to_apply_unvalidated = open_attempts_df.to_dict(orient='records')
        to_apply_count = len(to_apply_unvalidated)

    if fetch_success:
        if to_apply_count > 0:
            if LOGGING_LEVEL == 0:
                print(f'INFO. found {to_apply_count} job{"s" if to_apply_count > 1 else ""} from google sheet {TO_APPLY_GSHEET}')
            for j in to_apply_unvalidated:
                is_valid, apply_result = to_apply_validation(j)
                if is_valid:
                    jobs_to_apply.append(j)
                else:
                    if LOGGING_LEVEL < 2:
                        print(f'WARNING. invalid job input {apply_result}. skipping job.')
                    apply_results.append(apply_result)
        else:
            fetch_errors = f'INFO. no jobs to apply found from google sheet. {fetch_errors}'

    return fetch_success, fetch_errors


def to_apply_validation(job_config):
    is_valid = True
    validation_errors = []
    apply_result = {}
    for f in TO_APPLY_FIELDS:
        non_null = True if job_config.get(f, '') else False
        if not non_null:
            validation_errors.append(f'empty field {f}')
        is_valid = non_null if is_valid else is_valid        

    if not is_valid:
        apply_result = {
            'jobid': job_config.get('jobid', '*'),
            'applied': 0,
            'apply_result': '91_invalid_input',
            'errors': ','.join(validation_errors)
        }
    return is_valid, apply_result


def site_load():
    errors = ''
    if LOGGING_LEVEL == 0:
        print(f'INFO. connecting to Browser session. \n Ensure that you have an active authenticated session and updated cookies stored at cookies_mcf.json .')
    load_success = browser.page_refresh()
    if load_success:
        try:
            print(f'INFO. loading homepage {browser.homepage} ...')
            browser.homepage_load()
            #browser.page.screenshot(path="auth_check.png")
        except Exception as e:
            load_success = False
            errors = f'ERROR. problem loading job website {browser.homepage}. {str(e)}'
    else:
        errors = browser.errors
    return load_success, errors


def jobs_apply():
    global apply_results
    apply_success = True
    apply_errors = ''
    job_count = len(jobs_to_apply)
    if job_count > 0:
        if LOGGING_LEVEL < 2:
            print(f'INFO. attempting to apply for {job_count} job{"s" if job_count>1 else ""} ...')
        for j in jobs_to_apply:
            apply_result = apply_job(j)
            apply_results.append(apply_result)
    else:
        apply_errors = 'INFO. no jobs to apply'        
    return apply_success, apply_errors


def apply_job(job_config):
    apply_success = True
    apply_status = '01_applied'
    errors = ''
    jobid = job_config.get('jobid', '')
    slug = job_config.get('slug', '')
    url = job_config.get('url', '')
    cv_version = job_config.get('cv_version', '')

    if LOGGING_LEVEL == 0:
        print(f'INFO. applying to job {jobid} slug: {slug} url: {url} ')

    try:
        browser.page_load(slug=slug, url=url)
    except Exception as e:
        apply_success = False
        apply_status = '05_post_unavailable'
        errors = f'ERROR. failed to load job post page. {str(e)}'

    if apply_success:
        if LOGGING_LEVEL == 0:
            print(f'INFO. starting application ...')
        apply_success, apply_status, errors = browser.apply_start()

    if apply_success and not errors:
        if LOGGING_LEVEL == 0:
            print(f'attempting cv select ...')
        apply_success, errors = browser.cv_select(cv_version)
        if not apply_success:
            if 'not found' in errors:
                apply_status = '06_cv_not_found'
            else:
                apply_status = '03_cv_selector_error'

    if apply_success and not errors:
        if LOGGING_LEVEL == 0:
            print(f'cv {cv_version} selected.')
            print(f'attempting apply submit ...')
        apply_success, errors = browser.apply_submit()
        if not apply_success:            
            apply_status = '02_questionnaire'
            errors = f'ERROR. failed to complete job application process. Assuming questionnaire required. {errors}'
        
    apply_result = {
        'jobid': jobid,
        'applied': 1 if apply_success else 0,
        'apply_result': apply_status,
        'errors': errors
    }
    if LOGGING_LEVEL < 2:
        success_str = 'success' if apply_success else 'failed'
        print(f'INFO. apply results: {success_str}, status:{apply_status}, jobid:{jobid}  {errors}')
    if LOGGING_LEVEL == 0:
        print(f'INFO. full results: {apply_result}')
    return apply_result


def results_post():
    post_success = True
    post_errors = ''
    if apply_results:
        if LOGGING_LEVEL == 0:
            print(f'INFO. posting jobs applied results to google sheet {RESULTS_GSHEET} ...')
        try:
            db.load()
            prior_results = db.get_sheet(RESULTS_GSHEET).set_index('jobid')
        except Exception as e:
            post_success = False
            extra_info = 'blank column in google sheet. consider adding empty string to errors' if 'passed, passed' in str(e) else ''
            post_errors = f'ERROR. problem fetching current results from google sheet {RESULTS_GSHEET}. {extra_info} {e}'
 
        if post_success:
            try:
                new_results = pd.DataFrame.from_records(apply_results).set_index('jobid')
                new_results['errors'].fillna(' ', inplace=True)
                post_results = new_results.combine_first(prior_results).reset_index()
            except Exception as e:
                post_success = False
                post_errors = f'ERROR. problem converting results into pandas DataFrame and merging with existing results. {e}'

        if post_success:
            try:
                db.post_to_gsheet(post_results, RESULTS_GSHEET, input_option='USER_ENTERED')
            except Exception as e:
                post_success = False
                post_errors = f'ERROR. problem posting updated results to google sheet {RESULTS_GSHEET}. {e}'
    else:
        post_errors = 'INFO. no results to post.'
    return post_success, post_errors


if __name__ == '__main__':
    run()