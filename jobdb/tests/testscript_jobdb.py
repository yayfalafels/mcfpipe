#!/usr/bin/env python3
"""unit tests for DB API
"""
# dependencies ------------------------------------------------------------------------
import os
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from jobdb import handler

# constants --------------------------------------------------------------------------
SAMPLE_TEST_RECORD = {
    'posted_date': '2025-08-01',
    'position': 'Data Engineer',
    'company_name': 'ACME Corp',
    'url': 'https://acme.com/jobs/abc123',
    'load_status': 0
}


# module variables --------------------------------------------------------------------
ALT_BASE_URL = 'http://localhost:8000'
BASE_URL = os.environ.get('DB_API_URL', '')  # Use env var for flexibility
PARAMS = {
    'table': 'job',
    'job_id': '',
    'batch_ids': [],
    'test_record': SAMPLE_TEST_RECORD
}

# helper method --------------------------------------------------------------------
def url_handle(url, method:str = 'GET', payload: dict ={}):
    event = {
        'httpMethod': method,
        'path': url,
        'body': payload
    }
    context = {}
    return handler.lambda_handler(event, context)


# unit tests -----------------------------------------------------------------------------

def test_00_endpoint_valid():
    print(__name__)
    url = f"{BASE_URL}"
    response = url_handle(url)
    assert 'statusCode' in response, f"expected key 'statusCode' in response, found {response.keys()}"
    assert response.get('statusCode', None) == 200, f'expected status code 200, got {response.get('statusCode', None)}. {response} from BASE_URL: {BASE_URL}'
    print(response)

def test_01_post_valid():
    global PARAMS
    """POST Create new job (positive)"""
    payload = PARAMS.get('test_record', {}).copy()
    url = f"{BASE_URL}/{PARAMS.get('table', '')}"
    response = url_handle(url, method='POST', payload=payload)
    assert response.get('statusCode', None) == 200, f'expected status code 200, got {response.get('statusCode', None)}. {response}'
    assert 'payload' in response, f"expected key 'payload' in response. found {response.keys()}"
    response_body = response.get('payload', {})
    assert 'ids' in response_body, f"expected key 'ids' in response body, found {response_body.keys()}"
    job_id = response_body.get('id', [''])[0]
    PARAMS['job_id'] = job_id  # save for later tests
    print(response)

def test_02_get_existing():
    """GET Fetch a single job (positive)"""
    url = f"{BASE_URL}/{PARAMS.get('table', '')}/{PARAMS.get('job_id', '')}"
    response = url_handle(url)
    assert response.get('statusCode', None) == 200, f'expected status code 200, got {response.get('statusCode', None)}. {response}'
    assert 'payload' in response, f"expected key 'payload' in response. found {response.keys()}"
    job_record = response.get('payload', {})
    for f in [
        'posted_date',
        'position',
        'company'
    ]:            
        expected = PARAMS.get('test_record', {}).get(f, '')
        test_value = job_record.get(f, '')
        assert expected == test_value, f'expected job field {f} value {expected}, got {test_value}'
    print(response)


# entry point ---------------------------------------------------------------------
def run_tests():
    test_00_endpoint_valid()
    #test_01_post_valid()
    #test_02_get_existing()


if __name__ == "__main__":
    run_tests()
