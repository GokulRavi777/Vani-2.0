import pytest
from unittest.mock import MagicMock
from app.main import app
from app.schemas.assessment import QuestionModel
from app.services.question_generator import (
    QuestionGenerationError,
    get_question_generator,
    validate_question_list,
    HybridQuestionGenerator
)


def test_empty_skill_selection_rejected(client):
    """Test that submitting an empty skills list is rejected with 422."""
    payload = {
        "skills": [],
        "question_count": 2,
        "language": "en-IN"
    }
    response = client.post("/api/assessments", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_unsupported_skills_rejected(client):
    """Test that selecting skills outside the supported set is rejected with 422."""
    payload = {
        "skills": ["Rust", "Go"],
        "question_count": 2,
        "language": "en-IN"
    }
    response = client.post("/api/assessments", json=payload)
    assert response.status_code == 422
    assert "Unsupported skills" in str(response.json())


def test_invalid_question_count_rejected(client):
    """Test that requesting a question count other than 2 is rejected."""
    payload = {
        "skills": ["Python"],
        "question_count": 5,
        "language": "en-IN"
    }
    response = client.post("/api/assessments", json=payload)
    assert response.status_code == 422
    assert "strictly requires exactly 2 questions" in str(response.json())


def test_valid_assessment_creation_single_skill(client):
    """Test creating an assessment with a single valid skill."""
    payload = {
        "skills": ["Python"],
        "question_count": 2,
        "language": "en-IN"
    }
    response = client.post("/api/assessments", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["assessment_id"].startswith("asm_")
    assert data["skills"] == ["Python"]
    assert data["language"] == "en-IN"
    assert data["question_generation_mode"] == "fallback"
    assert len(data["questions"]) == 2

    # Verify questions target the selected skill
    for q in data["questions"]:
        assert "Python" in q["skills"]
        assert len(q["text"]) > 15
        assert q["text"].endswith("?")


def test_valid_assessment_creation_all_skills(client):
    """Test creating an assessment with all four skills."""
    skills = ["Python", "SQL", "Java", "Machine Learning"]
    payload = {
        "skills": skills,
        "question_count": 2,
        "language": "en-IN"
    }
    response = client.post("/api/assessments", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert len(data["questions"]) == 2
    # Verify that question IDs are unique
    q1 = data["questions"][0]
    q2 = data["questions"][1]
    assert q1["question_id"] != q2["question_id"]
    assert q1["text"] != q2["text"]

    # Verify every question is relevant to the selected skills
    all_selected = set(skills)
    for q in data["questions"]:
        assert len(set(q["skills"]).intersection(all_selected)) > 0


def test_unique_assessment_and_question_ids(client):
    """Test that consecutive assessment creations yield unique assessment and question IDs."""
    payload = {"skills": ["SQL"], "question_count": 2}
    r1 = client.post("/api/assessments", json=payload).json()
    r2 = client.post("/api/assessments", json=payload).json()

    assert r1["assessment_id"] != r2["assessment_id"]
    q_ids_1 = {q["question_id"] for q in r1["questions"]}
    q_ids_2 = {q["question_id"] for q in r2["questions"]}
    assert len(q_ids_1.intersection(q_ids_2)) == 0


def test_reading_assessment_does_not_regenerate_questions(client):
    """Test that GET /api/assessments/{id} returns the exact existing questions without regenerating."""
    create_payload = {
        "skills": ["Java", "SQL"],
        "question_count": 2
    }
    create_res = client.post("/api/assessments", json=create_payload)
    assert create_res.status_code == 201
    created_data = create_res.json()
    asm_id = created_data["assessment_id"]

    # First read
    read1 = client.get(f"/api/assessments/{asm_id}")
    assert read1.status_code == 200
    read1_data = read1.json()

    # Second read
    read2 = client.get(f"/api/assessments/{asm_id}")
    assert read2.status_code == 200
    read2_data = read2.json()

    # Verify exact equality
    assert created_data == read1_data == read2_data
    assert read1_data["questions"][0]["question_id"] == created_data["questions"][0]["question_id"]
    assert read1_data["questions"][1]["question_id"] == created_data["questions"][1]["question_id"]


def test_session_not_found_response(client):
    """Test that requesting a non-existent assessment returns 404."""
    response = client.get("/api/assessments/asm_does_not_exist_999")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


def test_multi_session_isolation(client):
    """Test that two separate sessions preserve their own skills and questions independently."""
    s1 = client.post("/api/assessments", json={"skills": ["Python"], "question_count": 2}).json()
    s2 = client.post("/api/assessments", json={"skills": ["Java"], "question_count": 2}).json()

    read_s1 = client.get(f"/api/assessments/{s1['assessment_id']}").json()
    read_s2 = client.get(f"/api/assessments/{s2['assessment_id']}").json()

    assert read_s1["skills"] == ["Python"]
    assert read_s2["skills"] == ["Java"]
    assert read_s1["questions"][0]["question_id"] != read_s2["questions"][0]["question_id"]


def test_question_generation_failure_behavior(client):
    """Test that if the question generator fails, a 500 error is returned with clear details."""
    mock_generator = MagicMock()
    mock_generator.generate.side_effect = QuestionGenerationError("Simulated LLM outage")

    app.dependency_overrides[get_question_generator] = lambda: mock_generator
    try:
        response = client.post("/api/assessments", json={"skills": ["Python"], "question_count": 2})
        assert response.status_code == 500
        data = response.json()
        assert "Simulated LLM outage" in data["detail"]
    finally:
        app.dependency_overrides.clear()


def test_validate_question_list_catches_invalid_output():
    """Unit test for the question validator ensuring bad output is rejected."""
    # Test wrong count
    with pytest.raises(QuestionGenerationError, match="Expected exactly 2 questions"):
        validate_question_list([], ["Python"])

    # Test missing question mark
    bad_questions = [
        QuestionModel(question_id="q1", text="Explain Python generators", skills=["Python"]),
        QuestionModel(question_id="q2", text="What is GIL in Python?", skills=["Python"])
    ]
    with pytest.raises(QuestionGenerationError, match="must end with a question mark"):
        validate_question_list(bad_questions, ["Python"])

    # Test irrelevant skill
    irrelevant_questions = [
        QuestionModel(question_id="q1", text="How does garbage collection work in Java?", skills=["Java"]),
        QuestionModel(question_id="q2", text="What is an index in SQL?", skills=["SQL"])
    ]
    with pytest.raises(QuestionGenerationError, match="does not match any selected skill"):
        validate_question_list(irrelevant_questions, ["Python"])


@pytest.mark.parametrize("skill,expected_substrs", [
    ("Python", ["difference between a list and a tuple", "handle exceptions when reading a file"]),
    ("SQL", ["second-highest salary", "INNER JOIN and a LEFT JOIN"]),
    ("Java", ["interface and an abstract class", "exception handling works in Java"]),
    ("Machine Learning", ["supervised and unsupervised learning", "overfitting in machine learning"])
])
def test_all_four_skills_return_exact_questions(client, skill, expected_substrs):
    """Verify each of the 4 skills returns exactly its two predefined questions."""
    res = client.post("/api/assessments", json={"skills": [skill], "question_count": 2})
    assert res.status_code == 201
    data = res.json()
    assert len(data["questions"]) == 2
    assert expected_substrs[0] in data["questions"][0]["text"]
    assert expected_substrs[1] in data["questions"][1]["text"]


def test_submit_answer_workflow(client):
    """Verify submitting an answer against an assessment question works and is persisted."""
    create_res = client.post("/api/assessments", json={"skills": ["Python"], "question_count": 2})
    assert create_res.status_code == 201
    assessment = create_res.json()
    assessment_id = assessment["assessment_id"]
    q1 = assessment["questions"][0]

    # Submit answer
    answer_payload = {
        "question_id": q1["question_id"],
        "transcript": "Lists are mutable while tuples are immutable in Python.",
        "latency_ms": 350.5,
        "provider": "google"
    }
    sub_res = client.post(f"/api/assessments/{assessment_id}/answers", json=answer_payload)
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["status"] == "success"
    assert sub_data["answer"]["transcript"] == answer_payload["transcript"]
    assert sub_data["answer"]["question_id"] == q1["question_id"]

    # Re-fetch assessment to ensure answer persistence
    fetch_res = client.get(f"/api/assessments/{assessment_id}")
    assert fetch_res.status_code == 200
    fetched_data = fetch_res.json()
    assert q1["question_id"] in fetched_data["answers"]
    assert fetched_data["answers"][q1["question_id"]]["transcript"] == answer_payload["transcript"]

    # Test submitting answer for non-existent question
    bad_answer = {
        "question_id": "non_existent_q_id",
        "transcript": "Some invalid answer"
    }
    bad_res = client.post(f"/api/assessments/{assessment_id}/answers", json=bad_answer)
    assert bad_res.status_code == 400
    assert "does not belong" in bad_res.json()["detail"]


def test_websocket_stt_unconfigured_provider_returns_error(client, monkeypatch):
    """Verify WebSocket STT reports clear configuration error when provider credentials are missing."""
    monkeypatch.setenv("SARVAM_API_KEY", "")
    from app.config import settings
    monkeypatch.setattr(settings, "SARVAM_API_KEY", "")

    with client.websocket_connect("/ws/stt/en-IN?provider=sarvam&question_id=q_test") as ws:
        data = ws.receive_json()
        assert data["type"] == "error"
        assert data["question_id"] == "q_test"
        assert "Sarvam AI API key" in data["error"]


def test_sarvam_adapter_transcribe_sdk(monkeypatch):
    """Verify that SarvamSTTAdapter sends mode='transcribe' and auto-detects language via the official SDK."""
    from unittest.mock import MagicMock
    from app.services.stt.base import SarvamSTTAdapter

    adapter = SarvamSTTAdapter(api_key="test_key_123")
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.transcript = "பைதான் list mutable, ஆனால் tuple immutable."
    mock_response.language_code = "ta-IN"
    mock_client.speech_to_text.transcribe.return_value = mock_response
    monkeypatch.setattr(adapter, "get_client", lambda: mock_client)

    result = adapter.transcribe_audio_bytes(
        audio_bytes=b"dummy_pcm",
        filename="test.wav",
        language_code="unknown",
        mime_type="audio/wav",
        model="saaras:v4",
    )

    assert result["transcript"] == "பைதான் list mutable, ஆனால் tuple immutable."
    assert result["model"] == "saaras:v4"
    assert result["language_code"] == "ta-IN"
    mock_client.speech_to_text.transcribe.assert_called_once()
    _, kwargs = mock_client.speech_to_text.transcribe.call_args
    assert kwargs.get("mode") == "transcribe"
    assert kwargs.get("language_code") == "unknown"
    assert kwargs.get("model") == "saaras:v4"


def test_sarvam_adapter_transcribe_rest_fallback(monkeypatch):
    """Verify that SarvamSTTAdapter sends mode='transcribe' and auto-detects language via direct REST fallback."""
    from unittest.mock import MagicMock
    from app.services.stt import base
    from app.services.stt.base import SarvamSTTAdapter

    adapter = SarvamSTTAdapter(api_key="test_key_123")
    # Simulate SDK unavailable to force REST fallback
    monkeypatch.setattr(base, "SarvamAI", None)

    mock_post = MagicMock()
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "transcript": "SQL query ல index use பண்ணினா lookup O(1) or O(log n) ஆகும்.",
        "language_code": "ta-IN"
    }
    mock_post.return_value = mock_res
    monkeypatch.setattr(base.requests, "post", mock_post)

    result = adapter.transcribe_audio_bytes(
        audio_bytes=b"dummy_pcm",
        filename="test.wav",
        language_code="unknown",
        mime_type="audio/wav",
        model="saaras:v4",
    )

    assert result["transcript"] == "SQL query ல index use பண்ணினா lookup O(1) or O(log n) ஆகும்."
    assert result["language_code"] == "ta-IN"
    assert result["model"] == "saaras:v4"
    assert "latency_ms" in result
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["data"]["mode"] == "transcribe"
    assert kwargs["data"]["language_code"] == "unknown"
    assert kwargs["data"]["model"] == "saaras:v4"
    assert kwargs["headers"]["api-subscription-key"] == "test_key_123"


