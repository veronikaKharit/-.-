import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"


def test_health():
    response = requests.get(f"{BASE_URL}/health", timeout=10)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_training_flow():
    create_scenario = requests.post(
        f"{BASE_URL}/scenarios",
        json={"name": "Сценарий для CI", "difficulty": 2},
        timeout=10,
    )
    assert create_scenario.status_code == 200
    scenario = create_scenario.json()
    assert scenario["name"] == "Сценарий для CI"

    get_scenario = requests.get(f"{BASE_URL}/scenarios/{scenario['id']}", timeout=10)
    assert get_scenario.status_code == 200

    create_session = requests.post(
        f"{BASE_URL}/sessions",
        json={"userId": "usr-ci", "scenarioId": scenario["id"], "mode": "training"},
        timeout=10,
    )
    assert create_session.status_code == 200
    session = create_session.json()
    assert session["status"] == "ACTIVE"

    send_answer = requests.post(
        f"{BASE_URL}/sessions/{session['id']}/answer",
        json={"answerText": "Я хочу провести выявление потребностей клиента"},
        timeout=10,
    )
    assert send_answer.status_code == 200
    payload = send_answer.json()
    assert payload["lastEvaluation"]["correctness"] in (50, 100)

    finish = requests.put(f"{BASE_URL}/sessions/{session['id']}/finish", timeout=10)
    assert finish.status_code == 200
    assert finish.json()["status"] == "COMPLETED"


def test_chatbot_flow():
    response = requests.post(
        f"{BASE_URL}/chat/ask",
        json={"question": "Какие скидки доступны клиенту?"},
        timeout=10,
    )
    assert response.status_code == 200
    payload = response.json()
    assert "answer" in payload
    assert "context" in payload
