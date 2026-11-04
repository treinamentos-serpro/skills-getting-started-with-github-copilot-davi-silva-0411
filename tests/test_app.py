from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src import app as api


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.fixture
def isolated_activities(monkeypatch):
    activities = deepcopy(api.activities)
    monkeypatch.setattr(api, "activities", activities)
    return activities


def test_root_redirects_to_static_index(client):
    # Arrange
    expected_location = "/static/index.html"

    # Act
    response = client.get("/", follow_redirects=False)

    # Assert
    assert response.status_code == 307
    assert response.headers["location"] == expected_location


def test_get_activities_returns_all_activities(client, isolated_activities):
    # Arrange
    expected_activities = deepcopy(isolated_activities)

    # Act
    response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.json() == expected_activities


def test_signup_adds_student_to_activity(client, isolated_activities):
    # Arrange
    email = "student@mergington.edu"

    # Act
    response = client.post(
        "/activities/Basketball Team/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {
        "message": f"Signed up {email} for Basketball Team"
    }
    assert email in isolated_activities["Basketball Team"]["participants"]


def test_signup_rejects_duplicate_student(client, isolated_activities):
    # Arrange
    email = "michael@mergington.edu"
    participants_before = list(isolated_activities["Chess Club"]["participants"])

    # Act
    response = client.post(
        "/activities/Chess Club/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Student already signed up for this activity"
    }
    assert isolated_activities["Chess Club"]["participants"] == participants_before


def test_signup_returns_not_found_for_unknown_activity(client, isolated_activities):
    # Arrange
    email = "student@mergington.edu"

    # Act
    response = client.post(
        "/activities/Unknown Club/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}


def test_unregister_removes_student_from_activity(client, isolated_activities):
    # Arrange
    email = "michael@mergington.edu"

    # Act
    response = client.delete(
        "/activities/Chess Club/unregister",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {
        "message": f"Unregistered {email} from Chess Club"
    }
    assert email not in isolated_activities["Chess Club"]["participants"]


def test_unregister_returns_not_found_for_unregistered_student(client, isolated_activities):
    # Arrange
    email = "student@mergington.edu"

    # Act
    response = client.delete(
        "/activities/Chess Club/unregister",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 404
    assert response.json() == {
        "detail": "Student is not signed up for this activity"
    }


def test_unregister_returns_not_found_for_unknown_activity(client, isolated_activities):
    # Arrange
    email = "student@mergington.edu"

    # Act
    response = client.delete(
        "/activities/Unknown Club/unregister",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}

def test_concurrent_duplicate_signups_register_student_once(client, isolated_activities):
    # Arrange
    email = "student@mergington.edu"
    attempts = 20

    # Act
    with ThreadPoolExecutor(max_workers=attempts) as executor:
        responses = list(executor.map(
            lambda _: client.post(
                "/activities/Basketball Team/signup",
                params={"email": email},
            ),
            range(attempts),
        ))

    # Assert
    status_codes = sorted(response.status_code for response in responses)
    assert status_codes == [200] + [400] * (attempts - 1)
    assert isolated_activities["Basketball Team"]["participants"].count(email) == 1


def test_concurrent_unregisters_return_not_found_instead_of_error(client, isolated_activities):
    # Arrange
    email = "michael@mergington.edu"
    attempts = 20

    # Act
    with ThreadPoolExecutor(max_workers=attempts) as executor:
        responses = list(executor.map(
            lambda _: client.delete(
                "/activities/Chess Club/unregister",
                params={"email": email},
            ),
            range(attempts),
        ))

    # Assert
    status_codes = sorted(response.status_code for response in responses)
    assert status_codes == [200] + [404] * (attempts - 1)
    assert email not in isolated_activities["Chess Club"]["participants"]
