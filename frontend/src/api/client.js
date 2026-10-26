/**
 * API client for Vani 2.0 POC backend.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const text = await response.text();
      try {
        const body = JSON.parse(text);
        if (body.detail) {
          if (typeof body.detail === "string") {
            errorDetail = body.detail;
          } else if (Array.isArray(body.detail)) {
            errorDetail = body.detail.map((d) => d.msg || JSON.stringify(d)).join(", ");
          }
        }
      } catch {
        // If response is HTML or plain text (e.g., Vite proxy ECONNREFUSED error page)
        if (text.includes("ECONNREFUSED") || response.status === 500) {
          errorDetail = "Backend connection failed. Please ensure the FastAPI server is running on port 8000.";
        }
      }
    } catch {
      // Fallback
    }
    throw new Error(errorDetail);
  }
  return response.json();
}

export async function checkHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return handleResponse(res);
}

export async function fetchSkills() {
  const res = await fetch(`${API_BASE}/api/skills`);
  return handleResponse(res);
}

export async function createAssessment({ skills, language = "en-IN", questionCount = 2, sttMode = "google" }) {
  const res = await fetch(`${API_BASE}/api/assessments`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      skills,
      language,
      question_count: questionCount,
      stt_mode: sttMode
    })
  });
  return handleResponse(res);
}

export async function getAssessment(assessmentId) {
  const res = await fetch(`${API_BASE}/api/assessments/${encodeURIComponent(assessmentId)}`);
  return handleResponse(res);
}

export async function submitAnswer(assessmentId, { questionId, transcript, audioMetadata, latencyMs, provider, comparisonResults }) {
  const res = await fetch(`${API_BASE}/api/assessments/${encodeURIComponent(assessmentId)}/answers`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      question_id: questionId,
      transcript: transcript || "",
      audio_metadata: audioMetadata || null,
      latency_ms: latencyMs || null,
      provider: provider || null,
      comparison_results: comparisonResults || null
    })
  });
  return handleResponse(res);
}
