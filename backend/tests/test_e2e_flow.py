"""End-to-End assessment lifecycle test.

Simulates the complete user workflow:
1. Check backend health.
2. Retrieve supported skills.
3. Candidate selects multiple skills (Python & SQL).
4. Candidate requests assessment creation.
5. Candidate views Question 1 and Question 2.
6. Candidate revisits Question 1 (verifies questions are not regenerated).
7. Verifies session status, IDs, and fallback mode.
"""

def test_full_candidate_assessment_workflow(client):
    # Step 1: Health check
    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"

    # Step 2: Fetch available skills
    skills_res = client.get("/api/skills")
    assert skills_res.status_code == 200
    available_skills = skills_res.json()["skills"]
    assert "Python" in available_skills
    assert "SQL" in available_skills

    # Step 3: Candidate starts assessment with Python and SQL
    start_payload = {
        "skills": ["Python", "SQL"],
        "language": "en-IN",
        "question_count": 2,
        "stt_mode": "google"
    }
    create_res = client.post("/api/assessments", json=start_payload)
    assert create_res.status_code == 201
    assessment_data = create_res.json()

    assessment_id = assessment_data["assessment_id"]
    assert assessment_id.startswith("asm_")
    assert assessment_data["question_generation_mode"] == "fallback"
    assert len(assessment_data["questions"]) == 2

    q1 = assessment_data["questions"][0]
    q2 = assessment_data["questions"][1]
    assert q1["question_id"] != q2["question_id"]
    assert len(q1["text"]) > 20
    assert len(q2["text"]) > 20

    # Step 4: Candidate navigates and re-reads assessment session
    fetch_res = client.get(f"/api/assessments/{assessment_id}")
    assert fetch_res.status_code == 200
    fetched_data = fetch_res.json()

    # Step 5: Verify exact persistence without question regeneration
    assert fetched_data["assessment_id"] == assessment_id
    assert fetched_data["questions"][0]["question_id"] == q1["question_id"]
    assert fetched_data["questions"][0]["text"] == q1["text"]
    assert fetched_data["questions"][1]["question_id"] == q2["question_id"]
    assert fetched_data["questions"][1]["text"] == q2["text"]
