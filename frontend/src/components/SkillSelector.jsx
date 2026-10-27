import React, { useState, useEffect, useRef } from "react";
import { fetchSkills, fetchTtsVoices, enrollCustomVoice } from "../api/client";
import { convertBlobToWav } from "../api/wavEncoder";

const DEFAULT_SKILLS = ["Python", "SQL", "Java", "Machine Learning"];

const DEFAULT_GNANI_VOICES = [
  { id: "Kaveri", name: "Kaveri (Female)", language: "en-IN", gender: "Female", description: "Firm, polished voice for technical assessment" },
  { id: "Pranav", name: "Pranav (Male)", language: "en-IN", gender: "Male", description: "Friendly, natural voice for interviews" },
  { id: "Devika", name: "Devika (Female)", language: "en-IN", gender: "Female", description: "Authoritative professional voice" },
  { id: "Shlok", name: "Shlok (Male)", language: "en-IN", gender: "Male", description: "Warm, conversational interview voice" },
  { id: "Girish", name: "Girish (Male)", language: "en-IN", gender: "Male", description: "Warm voice with natural cadence" },
  { id: "Trupti", name: "Trupti (Female)", language: "en-IN", gender: "Female", description: "Upbeat, articulate voice with maturity" },
  { id: "Nalini", name: "Nalini (Female)", language: "hi-IN", gender: "Female", description: "Friendly conversational voice" },
  { id: "Deepak", name: "Deepak (Male)", language: "hi-IN", gender: "Male", description: "Clear, measured corporate voice" }
];

export default function SkillSelector({
  onStartAssessment,
  isSubmitting,
  errorMessage,
  selectedProvider = "sarvam",
  initialVoice = "shubh",
  onChangeProvider
}) {
  const [availableSkills, setAvailableSkills] = useState(DEFAULT_SKILLS);
  const [selectedSkills, setSelectedSkills] = useState([]);
  const [validationError, setValidationError] = useState("");
  const [supportedVoices, setSupportedVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState(initialVoice || (selectedProvider === "sarvam" ? "shubh" : "Kaveri"));

  // Voice Cloning State (Phase 4 - Gnani)
  const [showClonePanel, setShowClonePanel] = useState(false);
  const [cloneVoiceName, setCloneVoiceName] = useState("My Voice");
  const [cloneConsent, setCloneConsent] = useState(true);
  const [isRecordingSample, setIsRecordingSample] = useState(false);
  const [sampleRecordTime, setSampleRecordTime] = useState(0);
  const [sampleAudioBlob, setSampleAudioBlob] = useState(null);
  const [isEnrollingVoice, setIsEnrollingVoice] = useState(false);
  const [enrollError, setEnrollError] = useState("");
  const [enrollSuccess, setEnrollSuccess] = useState("");

  const mediaRecorderRef = useRef(null);
  const recordIntervalRef = useRef(null);
  const audioChunksRef = useRef([]);

  const loadVoices = (provider = selectedProvider) => {
    fetchTtsVoices(provider)
      .then((res) => {
        if (res && Array.isArray(res.voices) && res.voices.length > 0) {
          setSupportedVoices(res.voices);
          // If default voice was Kaveri/shubh and a custom voice exists, select custom voice
          const customVoice = res.voices.find((v) => v.is_custom);
          if (customVoice && selectedVoice === "Kaveri") {
            setSelectedVoice(customVoice.id);
          } else {
            const hasCurrent = res.voices.some((v) => v.id === selectedVoice);
            if (!hasCurrent) {
              setSelectedVoice(res.default_voice || res.voices[0].id);
            }
          }
        }
      })
      .catch(() => {
        if (provider === "gnani") {
          setSupportedVoices(DEFAULT_GNANI_VOICES);
        }
      });
  };

  useEffect(() => {
    fetchSkills()
      .then((data) => {
        if (data && Array.isArray(data.skills) && data.skills.length > 0) {
          setAvailableSkills(data.skills);
        }
      })
      .catch(() => {
        // Fallback to DEFAULT_SKILLS
      });

    loadVoices(selectedProvider);
  }, [selectedProvider]);

  const handleStartSampleRecording = async () => {
    setEnrollError("");
    setEnrollSuccess("");
    setSampleAudioBlob(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = async () => {
        const rawBlob = new Blob(audioChunksRef.current, { type: recorder.mimeType || "audio/webm" });
        try {
          const wavBlob = await convertBlobToWav(rawBlob);
          setSampleAudioBlob(wavBlob);
        } catch (convErr) {
          console.warn("WAV conversion fallback:", convErr);
          setSampleAudioBlob(rawBlob);
        }
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorderRef.current = recorder;
      recorder.start(250);
      setIsRecordingSample(true);
      setSampleRecordTime(0);

      recordIntervalRef.current = setInterval(() => {
        setSampleRecordTime((t) => t + 1);
      }, 1000);
    } catch (err) {
      setEnrollError(`Microphone access failed: ${err.message}`);
    }
  };

  const handleStopSampleRecording = () => {
    if (recordIntervalRef.current) {
      clearInterval(recordIntervalRef.current);
      recordIntervalRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setIsRecordingSample(false);
  };

  const handleFileUpload = async (e) => {
    setEnrollError("");
    setEnrollSuccess("");
    const file = e.target.files?.[0];
    if (file) {
      try {
        const wavBlob = await convertBlobToWav(file);
        setSampleAudioBlob(wavBlob);
      } catch (convErr) {
        console.warn("Could not convert uploaded file to WAV:", convErr);
        setSampleAudioBlob(file);
      }
    }
  };

  const handleEnrollVoice = async () => {
    if (!sampleAudioBlob) {
      setEnrollError("Please record your voice or select an audio file first.");
      return;
    }
    if (sampleRecordTime > 0 && sampleRecordTime < 3) {
      setEnrollError("Recording is too brief (< 3 seconds). Gnani AI requires 5–30 seconds of speech for voice cloning.");
      return;
    }
    if (!cloneConsent) {
      setEnrollError("Please check the consent box to confirm this is your own voice.");
      return;
    }

    setIsEnrollingVoice(true);
    setEnrollError("");
    setEnrollSuccess("");

    try {
      const result = await enrollCustomVoice(sampleAudioBlob, cloneVoiceName, cloneConsent);
      const newVoiceId = result.voice?.voice_id;
      setEnrollSuccess(`Voice '${result.voice?.name || cloneVoiceName}' cloned and enrolled successfully!`);
      setShowClonePanel(false);
      setSampleAudioBlob(null);

      // Refresh voice list and select the new custom voice
      fetchTtsVoices("gnani").then((res) => {
        if (res && Array.isArray(res.voices)) {
          setSupportedVoices(res.voices);
          if (newVoiceId) {
            setSelectedVoice(newVoiceId);
          }
        }
      });
    } catch (err) {
      setEnrollError(err.message || "Failed to clone voice with Gnani AI.");
    } finally {
      setIsEnrollingVoice(false);
    }
  };

  const handleToggleSkill = (skill) => {
    setValidationError("");
    setSelectedSkills([skill]);
  };

  const handleStart = (e) => {
    e.preventDefault();
    if (selectedSkills.length === 0) {
      setValidationError("Please select at least one technical skill to begin the assessment.");
      return;
    }
    setValidationError("");
    onStartAssessment(selectedSkills, selectedVoice);
  };

  return (
    <section className="card" aria-labelledby="skill-selection-title">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "8px", marginBottom: "8px" }}>
        <div>
          <h2 id="skill-selection-title" className="card-title">
            Select Technical Skill
          </h2>
          <p className="card-subtitle" style={{ marginBottom: "12px" }}>
            Select exactly one skill for your interview assessment. Exactly two questions will be generated.
          </p>
        </div>
        {onChangeProvider && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onChangeProvider}
            style={{ fontSize: "0.8rem", padding: "4px 10px", marginBottom: "12px" }}
            title="Switch speech and assessment provider"
          >
            ← Change Provider ({selectedProvider === "gnani" ? "Gnani AI" : "Sarvam AI"})
          </button>
        )}
      </div>

      {selectedProvider === "gnani" && (
        <div className="gnani-placeholder-box" role="status">
          <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
            <span style={{ fontSize: "1.25rem", lineHeight: 1 }}>🎙️</span>
            <div>
              <strong style={{ color: "#6b21a8", display: "block", marginBottom: "4px" }}>
                Gnani AI Voice Assessment & Voice Cloning
              </strong>
              <span style={{ fontSize: "0.875rem", color: "#581c87", lineHeight: 1.45, display: "block" }}>
                Questions will be read aloud using Gnani Text-to-Speech synthesis. You can use standard interviewer voices or clone your own voice below.
              </span>
            </div>
          </div>
        </div>
      )}

      {selectedProvider === "sarvam" && (
        <div className="voice-selection-card" style={{
          background: "#f0f9ff",
          border: "1px solid #bae6fd",
          borderRadius: "var(--radius)",
          padding: "16px",
          marginBottom: "20px"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", flexWrap: "wrap", gap: "8px" }}>
            <label htmlFor="sarvam-voice-select" style={{ fontWeight: 600, fontSize: "0.95rem", color: "#0369a1" }}>
              🎙️ Interviewer Voice (Sarvam Bulbul TTS)
            </label>
            <span style={{ fontSize: "0.78rem", color: "#0284c7", background: "#e0f2fe", padding: "3px 8px", borderRadius: "12px", fontWeight: 600 }}>
              Official Sarvam AI Voices
            </span>
          </div>

          <select
            id="sarvam-voice-select"
            className="select-dropdown"
            value={selectedVoice}
            onChange={(e) => setSelectedVoice(e.target.value)}
            style={{ width: "100%", padding: "8px 12px", fontSize: "0.9rem", borderColor: "#38bdf8", borderRadius: "6px" }}
            disabled={isSubmitting}
          >
            {supportedVoices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name || v.id} — {v.gender} ({v.description || v.persona || v.language})
              </option>
            ))}
          </select>
          <p style={{ margin: "6px 0 0 0", fontSize: "0.8rem", color: "#0284c7" }}>
            The selected voice will read technical interview questions aloud with natural pacing.
          </p>
        </div>
      )}

      {selectedProvider === "gnani" && (
        <div className="voice-selection-card" style={{
          background: "#faf5ff",
          border: "1px solid #d8b4fe",
          borderRadius: "var(--radius)",
          padding: "16px",
          marginBottom: "20px"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", flexWrap: "wrap", gap: "8px" }}>
            <label htmlFor="gnani-voice-select" style={{ fontWeight: 600, fontSize: "0.95rem", color: "#581c87" }}>
              Interviewer Voice (Gnani TTS)
            </label>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setShowClonePanel(!showClonePanel);
                setEnrollError("");
                setEnrollSuccess("");
              }}
              style={{
                fontSize: "0.85rem",
                padding: "7px 14px",
                fontWeight: 600,
                borderColor: "#a855f7",
                color: "#581c87",
                background: "#f3e8ff",
                borderRadius: "6px",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                cursor: "pointer",
                boxShadow: "0 1px 3px rgba(124, 58, 237, 0.12)"
              }}
            >
              {showClonePanel ? "✕ Close Voice Cloning" : "🎙️ Clone My Voice"}
            </button>
          </div>

          <select
            id="gnani-voice-select"
            className="select-dropdown"
            value={selectedVoice}
            onChange={(e) => setSelectedVoice(e.target.value)}
            style={{ width: "100%", padding: "8px 12px", fontSize: "0.9rem", borderColor: "#c084fc", borderRadius: "6px" }}
            disabled={isSubmitting}
          >
            {supportedVoices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name || v.id} — {v.gender} ({v.description || v.persona || v.language})
              </option>
            ))}
          </select>
          <p style={{ margin: "6px 0 0 0", fontSize: "0.8rem", color: "#7e22ce" }}>
            The selected voice will read questions aloud with interactive replay controls.
          </p>

          {enrollSuccess && (
            <div className="voice-clone-success" role="status">
              <span>✓</span> {enrollSuccess}
            </div>
          )}

          {/* Voice Cloning Panel */}
          {showClonePanel && (
            <div className="voice-clone-panel">
              <div className="voice-clone-header">
                <span className="voice-clone-title">
                  <span>🎙️</span> Enroll Your Voice Profile
                </span>
                {isRecordingSample && (
                  <span className="voice-clone-recording-badge">
                    <span className="voice-clone-recording-pulse" />
                    Recording: {sampleRecordTime}s
                  </span>
                )}
              </div>

              <p style={{ fontSize: "0.8rem", color: "#6b21a8", margin: "0 0 10px 0" }}>
                Record 5–30 seconds of your voice reading the sample passage below (or upload a WAV/MP3). Gnani AI will generate a secure speaker embedding to read your assessment questions in your own voice.
              </p>

              {/* Sample Passage to Read */}
              <div className="voice-clone-prompt-card" style={{
                background: "#ffffff",
                border: "1px solid #d8b4fe",
                borderRadius: "8px",
                padding: "12px 14px",
                marginBottom: "12px",
                boxShadow: "0 1px 4px rgba(124, 58, 237, 0.06)"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                  <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "#6b21a8", textTransform: "uppercase", letterSpacing: "0.03em" }}>
                    📖 Sample Passage to Read Aloud (10–15 Seconds)
                  </span>
                  <span style={{ fontSize: "0.72rem", color: "#7c3aed", background: "#f3e8ff", padding: "2px 6px", borderRadius: "4px", fontWeight: 600 }}>
                    Recommended Text
                  </span>
                </div>
                <p style={{
                  fontSize: "0.88rem",
                  lineHeight: "1.55",
                  color: "#1e1b4b",
                  margin: 0,
                  fontStyle: "italic",
                  background: "#faf5ff",
                  padding: "10px 12px",
                  borderRadius: "6px",
                  borderLeft: "3px solid #7c3aed"
                }}>
                  &ldquo;Hello, I am ready to begin today&rsquo;s technical interview assessment. I will be demonstrating my problem-solving skills, explaining core data structures, and discussing scalable system design with clarity and confidence.&rdquo;
                </p>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "6px", fontSize: "0.74rem", color: "#7e22ce" }}>
                  <span>💡 Tip: Click &ldquo;Record from Mic&rdquo; and read at your natural speaking pace.</span>
                  <span>~12 seconds of speech</span>
                </div>
              </div>

              <div style={{ marginBottom: "10px" }}>
                <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "#581c87", marginBottom: "4px" }}>
                  Voice Label
                </label>
                <input
                  type="text"
                  className="input-field"
                  value={cloneVoiceName}
                  onChange={(e) => setCloneVoiceName(e.target.value)}
                  placeholder="e.g. My Voice"
                  style={{ width: "100%", padding: "6px 10px", fontSize: "0.85rem", borderColor: "#c084fc", borderRadius: "4px" }}
                  disabled={isEnrollingVoice || isRecordingSample}
                />
              </div>

              <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap", marginBottom: "10px" }}>
                {!isRecordingSample ? (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleStartSampleRecording}
                    disabled={isEnrollingVoice}
                    style={{ background: "#7c3aed", fontSize: "0.8rem", padding: "6px 12px" }}
                  >
                    🔴 Record from Mic
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={handleStopSampleRecording}
                    style={{ fontSize: "0.8rem", padding: "6px 12px", background: "#ef4444", color: "#fff", borderColor: "#dc2626" }}
                  >
                    ⏹ Stop Recording ({sampleRecordTime}s)
                  </button>
                )}

                <span style={{ fontSize: "0.75rem", color: "#7e22ce" }}>or</span>

                <label
                  className="btn btn-secondary"
                  style={{ fontSize: "0.8rem", padding: "6px 12px", cursor: isEnrollingVoice ? "not-allowed" : "pointer", marginBottom: 0 }}
                >
                  📁 Upload Audio File
                  <input
                    type="file"
                    accept="audio/*,.wav,.mp3,.ogg,.m4a"
                    onChange={handleFileUpload}
                    disabled={isEnrollingVoice || isRecordingSample}
                    style={{ display: "none" }}
                  />
                </label>

                {sampleAudioBlob && (
                  <span style={{ fontSize: "0.75rem", color: "#166534", fontWeight: 600 }}>
                    ✓ WAV Audio ready ({Math.round(sampleAudioBlob.size / 1024)} KB)
                  </span>
                )}
              </div>

              {sampleAudioBlob && (
                <div style={{ marginBottom: "12px", background: "#f3e8ff", padding: "8px 12px", borderRadius: "6px" }}>
                  <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#6b21a8", marginBottom: "4px" }}>
                    🔊 Voice Sample Preview:
                  </div>
                  <audio
                    controls
                    src={URL.createObjectURL(sampleAudioBlob)}
                    style={{ width: "100%", height: "32px" }}
                  />
                  {sampleRecordTime > 0 && sampleRecordTime < 5 && (
                    <div style={{ fontSize: "0.72rem", color: "#b45309", marginTop: "4px" }}>
                      💡 Tip: Recorded sample is {sampleRecordTime}s. Gnani AI recommends 5–30s of speech for best quality.
                    </div>
                  )}
                </div>
              )}

              {/* Consent verification */}
              <label className="voice-clone-consent">
                <input
                  type="checkbox"
                  checked={cloneConsent}
                  onChange={(e) => setCloneConsent(e.target.checked)}
                  disabled={isEnrollingVoice}
                />
                <span>
                  I confirm that this audio recording is my own voice and provide consent to generate a custom voice embedding to read assessment questions.
                </span>
              </label>

              {enrollError && (
                <div style={{ background: "#fef2f2", color: "#991b1b", border: "1px solid #fecaca", padding: "6px 10px", borderRadius: "4px", fontSize: "0.8rem", marginBottom: "10px" }}>
                  {enrollError}
                </div>
              )}

              <button
                type="button"
                className="btn btn-primary"
                onClick={handleEnrollVoice}
                disabled={isEnrollingVoice || !sampleAudioBlob || !cloneConsent}
                style={{ width: "100%", background: "#6b21a8", fontSize: "0.85rem", padding: "8px" }}
              >
                {isEnrollingVoice ? "⏳ Generating Voice Clone with Gnani AI..." : "✨ Enroll & Use My Voice for Interview"}
              </button>
            </div>
          )}
        </div>
      )}

      {validationError && (
        <div className="alert-error" role="alert">
          {validationError}
        </div>
      )}

      {errorMessage && (
        <div className="alert-error" role="alert">
          {errorMessage}
        </div>
      )}

      <div className="skills-grid" role="radiogroup" aria-label="Available technical skills">
        {availableSkills.map((skill) => {
          const isSelected = selectedSkills.includes(skill);
          const inputId = `skill-${skill.toLowerCase().replace(/\s+/g, "-")}`;

          return (
            <label
              key={skill}
              htmlFor={inputId}
              className={`skill-card ${isSelected ? "selected" : ""}`}
            >
              <input
                type="radio"
                name="skill-selection"
                id={inputId}
                checked={isSelected}
                onChange={() => handleToggleSkill(skill)}
                disabled={isSubmitting}
              />
              <span className="skill-card-label">{skill}</span>
            </label>
          );
        })}
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "16px" }}>
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleStart}
          disabled={isSubmitting}
          style={selectedProvider === "gnani" ? { background: "#7c3aed" } : {}}
        >
          {isSubmitting
            ? "Generating Assessment..."
            : selectedProvider === "gnani"
            ? "Start Assessment (Gnani TTS)"
            : "Start Assessment (Sarvam TTS)"}
        </button>
      </div>
    </section>
  );
}
