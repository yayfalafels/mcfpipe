#!/usr/bin/env python3
"""unit tests for DB API
"""
# dependencies ------------------------------------------------------------------------
import os
import json
import unittest
import requests


# constants --------------------------------------------------------------------------
SAMPLE_TEST_RECORD = {
    'post_source_id': '0',
    'posted_date': '2025-08-01',
    'position': 'Data Engineer',
    'company_name': 'ACME Corp',
    'url': 'https://acme.com/jobs/abc123',
    'status': 0
}


# module variables --------------------------------------------------------------------
BASE_URL = os.environ.get('DB_API_URL', 'http://localhost:8000')  # Use env var for flexibility


# classes -----------------------------------------------------------------------------
class TestDatabaseAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = 'post'
        cls.sort_key = 'posted_date'
        cls.pk = ''
        cls.sk = ''
        cls.batch_ids = []
        cls.test_record = SAMPLE_TEST_RECORD

    def test_001_endpoint_valid(self):
        response = requests.get(f"{BASE_URL}")
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text} from BASE_URL: {BASE_URL}')

    def test_002_health_valid(self):
        response = requests.get(f"{BASE_URL}/__admin/health")
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text} from BASE_URL: {BASE_URL}')
        content_type = response.headers.get('Content-Type', '').lower()
        self.assertEqual(content_type, 'application/json', f'expected JSON content type, received {content_type}')
        response_body = response.json()
        self.assertNotEqual(response_body, {}, f"empty response body")
        self.assertIn('success',response_body, f"expected key 'success' in response body, found {response_body.keys()}")
        self.assertTrue(response_body.get('success', False), f'unexpected result success=False')

    def test_003_engine_reload_valid(self):
        response = requests.get(f"{BASE_URL}/__admin/refresh")
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text} from BASE_URL: {BASE_URL}')
        content_type = response.headers.get('Content-Type', '').lower()
        self.assertEqual(content_type, 'application/json', f'expected JSON content type, received {content_type}')
        response_body = response.json()
        self.assertNotEqual(response_body, {}, f"empty response body")
        self.assertIn('reloaded_at',response_body, f"expected key 'reloaded_at' in response body, found {response_body.keys()}")

    def test_01_post_valid(self):
        """POST Create new post (positive)"""
        payload = self.__class__.test_record.copy()
        response = requests.post(f"{BASE_URL}/table/{self.table}", json=payload)
        self.assertEqual(response.status_code, 201, f'expected status code 201, got {response.status_code}. {response.text}')
        content_type = response.headers.get('Content-Type', '').lower()
        self.assertEqual(content_type, 'application/json', f'expected JSON content type, received {content_type}')
        response_body = response.json()
        self.assertIn('id', response_body)
        post_id = response_body.get('id', '')
        posted_date = payload.get('posted_date', '')
        self.__class__.pk = post_id
        self.__class__.sk = posted_date  # save for later tests

    def test_02_get_existing(self):
        """GET Fetch a single post (positive)"""
        response = requests.get(f"{BASE_URL}/table/{self.table}/{self.pk}?{self.sort_key}={self.sk}")
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text}')
        post_record = response.json()
        for f in [
            'posted_date',
            'position',
            'company'
        ]:            
            expected = self.__class__.test_record.get(f, '')
            test_value = post_record.get(f, '')
            self.assertEqual(expected, test_value, f'expected post field {f} value {expected}, got {test_value}')

    def test_03_put_update(self):
        """PUT Update a single post (positive)"""
        updated = self.__class__.test_record.copy()
        updated['position'] = 'Data Engineer Contract'
        response = requests.put(f"{BASE_URL}/table/{self.table}/{self.pk}?{self.sort_key}={self.sk}", json=updated)
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text}')

    @unittest.skip("TEMPORARY SKIP TEST")
    def test_04_post_invalid_missing_required(self):
        """POST with missing required field (negative)"""
        bad_payload = {
            'posted_date': '2025-08-01',
            'load_status': 0
        }
        response = requests.post(f"{BASE_URL}/table/{self.table}", json=bad_payload)
        self.assertEqual(response.status_code, 400, f'expected status code 400, got {response.status_code}. {response.text}')
        self.assertIn('position', response.text)

    @unittest.skip("TEMPORARY SKIP TEST")
    def test_05_post_invalid_type(self):
        """POST with invalid data type (negative)"""
        bad_payload = self.__class__.test_record.copy()
        bad_payload['load_status'] = 'zero'
        response = requests.post(f"{BASE_URL}/table/{self.table}", json=bad_payload)
        self.assertEqual(response.status_code, 400, f'expected status code 400, got {response.status_code}. {response.text}')
        self.assertIn('load_status', response.text)

    @unittest.skip("TEMPORARY SKIP TEST")
    def test_06_post_invalid_date(self):
        """POST with bad date format (negative)"""
        bad_payload = self.__class__.test_record.copy()
        bad_payload['posted_date'] = 'May 24, 2025'
        response = requests.post(f"{BASE_URL}/table/{self.table}", json=bad_payload)
        self.assertEqual(response.status_code, 400, f'expected status code 400, got {response.status_code}. {response.text}')
        self.assertIn('posted_date', response.text)

    @unittest.skip("TEMPORARY SKIP TEST")
    def test_07_get_nonexistent_job(self):
        """GET non-existent job (negative)"""
        response = requests.get(f"{BASE_URL}/table/{self.table}/nonexistent_id")
        self.assertEqual(response.status_code, 404, f'expected status code 404, got {response.status_code}. {response.text}')
        self.assertIn('job', response.text)

    @unittest.skip("TEMPORARY SKIP TEST")
    def test_08_get_nonexistent_table(self):
        """GET non-existent table (negative)"""
        response = requests.get(f"{BASE_URL}/table/nonexistent_table/some_id")
        self.assertEqual(response.status_code, 404, f'expected status code 404, got {response.status_code}. {response.text}')
        self.assertIn('table', response.text)

    @unittest.skip("TEMPORARY SKIP TEST")
    def test_09_delete_existing(self):
        """DELETE existing post (positive)"""
        response = requests.delete(f"{BASE_URL}/table/{self.table}/{self.pk}?{self.sort_key}={self.sk}")
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text}')

    @unittest.skip("TEMPORARY SKIP TEST")
    def test_10_confirm_deleted(self):
        """GET post after deletion (negative)"""
        response = requests.get(f"{BASE_URL}/table/{self.table}/{self.pk}?{self.sort_key}={self.sk}")
        self.assertEqual(response.status_code, 404, f'expected status code 404, got {response.status_code}. {response.text}')

    @unittest.skip("TEMPORARY SKIP TEST")
    def test_11_post_batch_insert(self):
        """POST batch insert (positive)"""
        payload = [
            {
                "posted_date": "2025-08-02",
                "position": "ML Engineer",
                "load_status": 0
            },
            {
                "posted_date": "2025-08-05",
                "position": "Data Analyst",
                "load_status": 0
            }
        ]
        response = requests.post(f"{BASE_URL}/table/{self.table}/batch", json=payload)
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text}')
        response_body = response.json()
        self.assertTrue(isinstance(response_body, list), f"expected response type 'list'. ")
        self.assertEqual(len(response_body), 2, f'Expected 2 items in response, found {len(response_body)}')
        first_item = response_body[0]
        self.assertIn('id', first_item, f"Expected response post records to contain key 'id'. 'id' key not found.")
        batch_ids = [{'id': r.get('id', ''), 'posted_date': r.get('posted_date', '')} for r in response_body]
        self.__class__.batch_ids = batch_ids

    @unittest.skip("TEMPORARY SKIP TEST")
    def test_12_get_search_by_posted_date(self):
        """GET search by posted_date (positive)"""
        response = requests.get(f"{BASE_URL}/table/{self.table}/search", params={'posted_date': '2025-08-02'})
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text}')
        response_body = response.json()
        self.assertTrue(isinstance(response_body, list))
        self.assertGreaterEqual(len(response_body), 1)
        found_ids = [rec['id'] for rec in response_body]
        ref_ids = [ck.get('id') for ck in self.__class__.batch_ids]
        self.assertTrue(any(i in found_ids for i in ref_ids))

    @unittest.skip("TEMPORARY SKIP TEST")
    def test_13_post_batch_delete(self):
        """POST delete batch of posts (positive)"""
        batch_ids = [
            {'id': '3472e1c3737746dfb92a56e408daacfd', 'posted_date': self.pk},
            {'id': '7771d3f4b87c4d88ae3a06245e656af1', 'posted_date': self.pk},
            {'id': '23334f3ef83c49a58cb3008470c9f29b', 'posted_date': self.pk},
            {'id': '703a228e557244a8994d3f6490020b42', 'posted_date': self.pk},
            {'id': '3452380d0e2f4e9494e100ed183be261', 'posted_date': self.pk},
            {'id': '1a1f60fcb3274dc4a8c1245a33fc5a66', 'posted_date': self.pk},
            {'id': '5dae2a431fb04c7eabd8e6f01aca1261', 'posted_date': self.pk},
            {'id': 'a0ace42d1f0848ac9fd784de0c95c9bf', 'posted_date': self.pk}
        ]
        response = requests.post(f"{BASE_URL}/table/{self.table}/delete", json=batch_ids)
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text}')
        response_body = response.json()
        self.assertEqual(response_body.get('success', 0), len(batch_ids))        

    @classmethod
    def tearDownClass(cls):
        # Clean up all test jobs
        test_ids = [x for x in [{'id': cls.pk, cls.sort_key: cls.sk}] + cls.batch_ids if x]
        response = requests.post(f"{BASE_URL}/table/{cls.table}/delete", json=test_ids)
        response_body = response.json()
        success = response_body.get('success', 0)
        fail_error = response_body.get('failed')
        if response.status_code not in [200, 204] or success < len(test_ids) or fail_error:
            raise AssertionError(f"Cleanup failed to delete ids {test_ids}. number succeeded {success}: {response.status_code} {response.text} {fail_error}")

if __name__ == "__main__":
    unittest.main()
