/**
 * API client for Vani 2.0 POC backend.
 */

import { convertBlobToWav } from "./wavEncoder.js";

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

export async function fetchTtsVoices(provider = "gnani", language = "") {
  const query = new URLSearchParams({ provider });
  if (language) query.append("language", language);
  const res = await fetch(`${API_BASE}/api/tts/voices?${query.toString()}`);
  return handleResponse(res);
}

export async function enrollCustomVoice(audioBlob, voiceName = "My Voice", consent = true) {
  // Convert any audio blob (WebM, MP3, etc.) to 16kHz PCM WAV for Gnani Voice Clone API
  let wavBlob = audioBlob;
  try {
    wavBlob = await convertBlobToWav(audioBlob);
  } catch (convErr) {
    console.warn("Could not convert audio to WAV, uploading original:", convErr);
  }

  const formData = new FormData();
  formData.append("file", wavBlob, "voice_sample.wav");
  formData.append("voice_name", voiceName);
  formData.append("consent", consent ? "true" : "false");
  formData.append("language", "en-IN");

  const res = await fetch(`${API_BASE}/api/tts/voice-clone/enroll`, {
    method: "POST",
    body: formData
  });
  return handleResponse(res);
}

export async function fetchCustomVoices() {
  const res = await fetch(`${API_BASE}/api/tts/voice-clone/voices`);
  return handleResponse(res);
}

export async function fetchVadPresets() {
  const res = await fetch(`${API_BASE}/api/stt/vad-presets`);
  return handleResponse(res);
}

export function getQuestionAudioUrl(assessmentId, questionId, voice = null, provider = "gnani") {
  const query = new URLSearchParams({ provider });
  if (voice) query.append("voice", voice);
  return `${API_BASE}/api/tts/assessments/${encodeURIComponent(assessmentId)}/questions/${encodeURIComponent(questionId)}?${query.toString()}`;
}

export async function fetchQuestionAudioBlob(assessmentId, questionId, voice = null, provider = "gnani") {
  const url = getQuestionAudioUrl(assessmentId, questionId, voice, provider);
  const res = await fetch(url);
  if (!res.ok) {
    let errorMsg = `HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      errorMsg = errJson.detail || errorMsg;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }
  return res.blob();
}

export async function synthesizeText({ text, voice = null, provider = "gnani", language = "en-IN" }) {
  const res = await fetch(`${API_BASE}/api/tts/synthesize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      text,
      voice,
      provider,
      language
    })
  });
  if (!res.ok) {
    let errorMsg = `HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      errorMsg = errJson.detail || errorMsg;
    } catch {
      // fallback
    }
    throw new Error(errorMsg);
  }
  return res.blob();
}

export async function createAssessment({
  skills,
  language = "unknown",
  questionCount = 2,
  sttMode = "sarvam",
  provider = "sarvam",
  voice = null
}) {
  // If deployed backend has an older schema where stt_mode Literal only accepts ('google', 'sarvam', 'compare'),
  // safely map 'gnani' stt_mode to 'sarvam' while preserving provider="gnani" and voice
  const safeSttMode = sttMode === "gnani" ? "sarvam" : (sttMode || "sarvam");

  const res = await fetch(`${API_BASE}/api/assessments`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      skills,
      language: language || "unknown",
      question_count: questionCount,
      stt_mode: safeSttMode,
      provider: provider,
      voice: voice
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

export async function transcribeAudioBlob(blob, { language = "unknown", questionId = null, provider = "sarvam" } = {}) {
  const formData = new FormData();
  const rawType = (blob.type || "").split(";")[0].trim() || "audio/webm";
  const ext = rawType.includes("webm") ? "webm" : rawType.includes("mp4") ? "mp4" : "wav";
  const cleanBlob = new Blob([blob], { type: rawType });
  formData.append("file", cleanBlob, `recorded_audio.${ext}`);

  const query = new URLSearchParams({
    language_code: language,
    provider: provider || "sarvam"
  });
  if (questionId) query.append("question_id", questionId);

  const res = await fetch(`${API_BASE}/api/stt/transcribe?${query.toString()}`, {
    method: "POST",
    body: formData
  });
  return handleResponse(res);
}

