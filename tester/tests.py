#!/usr/bin/env python3
"""generates CloudFormation yaml file for DynamoDB tables from DB_SCHEMA JSON file
"""
# dependencies ------------------------------------------------------------------------
import os
import unittest
import requests


# constants --------------------------------------------------------------------------
SAMPLE_TEST_RECORD = {
    'posted_date': '2025-08-01',
    'position': 'Data Engineer',
    'company_name': 'ACME Corp',
    'url': 'https://acme.com/jobs/abc123',
    'load_status': 0
}


# module variables --------------------------------------------------------------------
BASE_URL = os.environ.get('DB_API_URL', 'http://localhost:8000')  # Use env var for flexibility


# classes -----------------------------------------------------------------------------
class TestDatabaseAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = 'job'
        cls.job_id = ''
        cls.test_record = SAMPLE_TEST_RECORD

    def test_01_post_valid(self):
        """POST Create new job (positive)"""
        payload = self.__class__.test_record.copy()
        response = requests.post(f"{BASE_URL}/{self.table}", json=payload)
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text}')
        response_body = response.json()
        self.assertIn('ids', response_body)
        job_id = response_body.get('ids', [''])[0]
        self.__class__.job_id = job_id  # save for later tests

    def test_02_get_existing(self):
        """GET Fetch a single job (positive)"""
        response = requests.get(f"{BASE_URL}/{self.table}/{self.job_id}")
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text}')
        job_record = response.json()
        for f in [
            'posted_date',
            'position',
            'company'
        ]:            
            expected = self.__class__.test_record.get(f, '')
            test_value = job_record.get(f, '')
            self.assertEqual(expected, test_value, f'expected job field {f} value {expected}, got {test_value}')

    def test_03_put_update(self):
        """PUT Update a single job (positive)"""
        updated = self.__class__.test_record.copy()
        updated['position'] = 'Data Engineer Contract'
        response = requests.put(f"{BASE_URL}/{self.table}/{self.job_id}", json=updated)
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text}')

    def test_04_post_invalid_missing_required(self):
        """POST with missing required field (negative)"""
        bad_payload = {
            'posted_date': '2025-08-01',
            'load_status': 0
        }
        response = requests.post(f"{BASE_URL}/{self.table}", json=bad_payload)
        self.assertEqual(response.status_code, 400, f'expected status code 400, got {response.status_code}. {response.text}')
        self.assertIn('position', response.text)

    def test_05_post_invalid_type(self):
        """POST with invalid data type (negative)"""
        bad_payload = self.__class__.test_record.copy()
        bad_payload['load_status'] = 'zero'
        response = requests.post(f"{BASE_URL}/{self.table}", json=bad_payload)
        self.assertEqual(response.status_code, 400, f'expected status code 400, got {response.status_code}. {response.text}')
        self.assertIn('load_status', response.text)

    def test_06_post_invalid_date(self):
        """POST with bad date format (negative)"""
        bad_payload = self.__class__.test_record.copy()
        bad_payload['posted_date'] = 'May 24, 2025'
        response = requests.post(f"{BASE_URL}/{self.table}", json=bad_payload)
        self.assertEqual(response.status_code, 400, f'expected status code 400, got {response.status_code}. {response.text}')
        self.assertIn('posted_date', response.text)

    def test_07_get_nonexistent_job(self):
        """GET non-existent job (negative)"""
        response = requests.get(f"{BASE_URL}/{self.table}/nonexistent_id")
        self.assertEqual(response.status_code, 404, f'expected status code 404, got {response.status_code}. {response.text}')
        self.assertIn('job', response.text)

    def test_08_get_nonexistent_table(self):
        """GET non-existent table (negative)"""
        response = requests.get(f"{BASE_URL}/nonexistent_table/some_id")
        self.assertEqual(response.status_code, 404, f'expected status code 404, got {response.status_code}. {response.text}')
        self.assertIn('table', response.text)

    def test_09_delete_existing(self):
        """DELETE existing job (positive)"""
        response = requests.delete(f"{BASE_URL}/{self.table}/{self.job_id}")
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text}')

    def test_10_confirm_deleted(self):
        """GET job after deletion (negative)"""
        response = requests.get(f"{BASE_URL}/{self.table}/{self.job_id}")
        self.assertEqual(response.status_code, 404, f'expected status code 404, got {response.status_code}. {response.text}')

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
        response = requests.post(f"{BASE_URL}/{self.table}/batch", json=payload)
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text}')
        response_body = response.json()
        self.assertTrue(isinstance(response_body, list), f"expected response type 'list'. ")
        self.assertEqual(len(response_body), 2, f'Expected 2 items in response, found {len(response_body)}')
        first_item = response_body[0]
        self.assertIn('id', first_item, f"Expected response job records to contain key 'id'. 'id' key not found.")

    def test_12_get_search_by_posted_date(self):
        """GET search by posted_date (positive)"""
        response = requests.get(f"{BASE_URL}/{self.table}/search", params={'posted_date': '2025-08-02'})
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text}')
        self.assertTrue(isinstance(response.json(), list))
        self.assertGreaterEqual(len(response.json()), 1)
        found_ids = [rec['id'] for rec in res.json()]
        self.assertTrue(any(i in found_ids for i in self.batch_ids))

    def test_13_post_batch_delete(self):
        """POST delete batch of jobs (positive)"""
        res = requests.post(f"{BASE_URL}/{self.table}/delete", json=self.batch_ids)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), 1)

    @classmethod
    def tearDownClass(cls):
        # Clean up all test jobs
        test_ids = [cls.job_id, getattr(cls, "job_id_2", None), "job_test_missing", "job_test_invalid_type", "job_test_invalid_date"]
        test_ids = [x for x in test_ids if x]
        res = requests.post(f"{BASE_URL}/{cls.table}/delete", json=test_ids)
        assert response.status_code in [200, 204], "Cleanup failed"

if __name__ == "__main__":
    unittest.main()
