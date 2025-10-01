Feature: User Login

  Scenario Outline: Valid user login
    Given user credentials from "<user_json>"
    And account type is "<account_type>"
    And description is "<description>"

    Examples:
      | user_json      | account_type | description                  |       |
      | test_user_001  | Silver       | user with gmail email        |
      | test_user_002  | Platinum     | user with highest balance    |