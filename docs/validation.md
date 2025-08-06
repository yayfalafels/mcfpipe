# Validation

## Test cases

### Database API

__Pre test setup__

- load schema and API config 

__Tests__

| id | test type | feature to test | test method | expected outcome |
| - | - | - | - | - |
| 01 | positive | POST Create new job | position="Data Engineer" | list of ids with single item |
| 02 | positive | GET Fetch a single job | fetch by id for the job from step 01 | job record as json |
| 03 | positive | PUT Update a single job | update the position title to "Data Engineer contract" | non-empty list of ids |
| 04 | positive | DELETE Delete a single job | delete the job from step 01 | status=1 |
| 05 | positive | POST Batch insert new jobs | add a batch of jobs including one with posted_date=2025-08-02 | return set of ids |
| 06 | positive | GET Query using secondary keys | posted_date=2025-08-02 | should return non-empty ids |
| 07 | positive | DELETE delete a batch of jobs | delete batch of jobs by job id | status=1 |
| 08 | negative | POST job with missing required field | post job with missing field `position` | 400 Bad Request and response text includes "required" and "position" |
| 10 | negative | POST job with invalid data type | post job with load_status "zero" | 400 Bad Request and error description includes "type", "integer"  "load_status" |
| 09 | negative | POST job with invalid date format | post job with `posted_date` = "May 24, 2025" | 400 Bad Request and error description includes  "date", "format", "%Y-%m-%d" and "posted_date" |
| 11 | negative | GET non-existent job | fetch non-existent `jobid` | 404 Not Found and error description includes "job", "not exist" |
| 12 | negative | GET non-existent table | fetch non-existent `table_name` | 404 Not Found and error description includes "table", "not exist" |
