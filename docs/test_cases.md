# Nu-Mart Bookshop — Test Case Record

This table connects the six SRS features to repeatable tests. Record **actual result**, **pass/fail**, **tester**, and **date** after executing each case. Exact scenario IDs should be reconciled against the group's final SRS test-scenario table before submission.

| Test ID | Feature | Steps / Input | Expected result | Actual result | Status |
|---|---|---|---|---|---|
| TC-F1-01 | FR-01 | Rent Edition 2 book to Grade 10 student ST002 | Correct itemized printable receipt | | |
| TC-F1-02 | FR-01 | Attempt Edition 1 for Grade 12 student ST003 | Rental rejected; grade mapping enforced | | |
| TC-F2-01 | FR-02 | Search by exact ID BK002 | Only BK002 returned | | |
| TC-F2-02 | FR-02 | Search title Mathematics | Both matching books shown | | |
| TC-F3-01 | FR-03 | Add unique book BK099 | Book saved with Available status | | |
| TC-F3-02 | FR-03 | Add existing Book ID BK001 | Duplicate rejected; original unchanged | | |
| TC-F4-01 | FR-04 | Search ST002 | Correct name, grade and enrolment shown | | |
| TC-F4-02 | FR-04 | Try to rent to inactive ST004 | Rental refused; no inventory change | | |
| TC-F5-01 | FR-05 | Rent BK002 to ST002 | Rental Active; BK002 Rented | | |
| TC-F5-02 | FR-05 | Attempt to rent same copy a second time | Refused; only one active rental | | |
| TC-F5-03 | FR-05 | Return BK002 | Rental Returned; BK002 Available | | |
| TC-F6-01 | FR-06 | Set rental due within next 7 days | Appears in Due soon list | | |
| TC-F6-02 | FR-06 | Set due date before today in test data | Appears as Overdue; reminder generated | | |

Run the automated tests: `python -m pytest -v`. Manual test results must be completed with real observations, not assumed from the expected outcomes.
