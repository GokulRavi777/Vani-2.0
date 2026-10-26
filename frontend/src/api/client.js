/**
 * API client for Vani 2.0 POC backend.
 */

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");

export function getWebSocketBaseUrl() {
  const wsEnv = import.meta.env.VITE_WS_BASE_URL;
  if (wsEnv && wsEnv.trim()) return wsEnv.trim().replace(/\/+$/, "");

  if (API_BASE) {
    return API_BASE
      .replace(/^https:\/\//i, "wss://")
      .replace(/^http:\/\//i, "ws://")
      .replace(/\/+$/, "");
  }

  const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${wsProtocol}//${window.location.host}`;
}


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

export async function createAssessment({ skills, language = "en-IN", questionCount = 2, sttMode = "sarvam" }) {
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

export async function transcribeAudioBlob(blob, { language = "en-IN", questionId = null } = {}) {
  const formData = new FormData();
  const rawType = (blob.type || "").split(";")[0].trim() || "audio/webm";
  const ext = rawType.includes("webm") ? "webm" : rawType.includes("mp4") ? "mp4" : "wav";
  const cleanBlob = new Blob([blob], { type: rawType });
  formData.append("file", cleanBlob, `recorded_audio.${ext}`);


  const query = new URLSearchParams({ language_code: language });
  if (questionId) query.append("question_id", questionId);

  const res = await fetch(`${API_BASE}/api/stt/transcribe?${query.toString()}`, {
    method: "POST",
    body: formData
  });
  return handleResponse(res);
}

