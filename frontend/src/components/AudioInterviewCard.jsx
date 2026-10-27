import React, { useState } from "react";

const VAD_PRESETS = [
  {
    id: "interview_optimal",
    label: "🎯 Interview Optimal",
    tag: "Recommended",
    vadThreshold: 0.55,
    minSilenceMs: 700,
    minSpeechMs: 120,
    minSegmentMs: 120,
    maxSpeechS: 20.0,
    summary: "Balanced for tech interviews: tolerates 700ms pauses for candidate thinking without fragmentation; keeps 120ms floor for short keyword answers."
  },
  {
    id: "fast_turnaround",
    label: "⚡ Fast Turnaround",
    tag: "Rapid Q&A",
    vadThreshold: 0.60,
    minSilenceMs: 350,
    minSpeechMs: 80,
    minSegmentMs: 100,
    maxSpeechS: 10.0,
    summary: "Aggressive cutoff: finalizes after 350ms silence for near-instant latency. Best for quick rapid-fire questions."
  },
  {
    id: "noisy_room",
    label: "🎧 Noisy Room / Strict",
    tag: "Strict Noise Filter",
    vadThreshold: 0.75,
    minSilenceMs: 600,
    minSpeechMs: 180,
    minSegmentMs: 150,
    maxSpeechS: 15.0,
    summary: "Higher confidence (0.75) and 180ms onset filter to reject AC hum, mechanical keyboard clicks, and background office chatter."
  },
  {
    id: "monologue_heavy",
    label: "🎙️ Long Monologue",
    tag: "System Design",
    vadThreshold: 0.50,
    minSilenceMs: 1200,
    minSpeechMs: 150,
    minSegmentMs: 120,
    maxSpeechS: 30.0,
    summary: "High patience: accommodates deep 1.2s pauses while chunking answers every 30s to keep real-time transcription streaming."
  }
];

export default function AudioInterviewCard({
  question,
  questionNumber,
  totalQuestions,
  sttMode,
  isRecording,
  recordingTime,
  audioMetadata,
  livePartial,
  finalTranscript,
  latencyMs,
  comparisonResults,
  isComparing,
  micPermissionError,
  providerError,
  audioBlob,
  onStartRecording,
  onStopRecording,
  onRetryAnswer,
  onFinishAnswer,
  canFinish,
  isGnaniProvider = false,
  isGnaniTtsActive = false,
  gnaniVoice = "Kaveri",
  provider = "sarvam",
  interviewerVoice = "",
  isTtsActive = true,
  ttsLoading = false,
  ttsPlaying = false,
  ttsError = "",
  onReplayAudio,
  onPauseAudio,
  vadSettings,
  onChangeVadSettings
}) {
  const [vadPanelOpen, setVadPanelOpen] = useState(true);
  const [activeTab, setActiveTab] = useState("sliders"); // "sliders" | "headers" | "guide"

  const activeProv = (provider || (isGnaniProvider ? "gnani" : "sarvam")).toLowerCase();
  const activeVoiceName = interviewerVoice || gnaniVoice || (activeProv === "sarvam" ? "shubh" : "Kaveri");
  const isSarvamTheme = activeProv === "sarvam";

  const currentVad = vadSettings || {
    preset: "interview_optimal",
    vadThreshold: 0.55,
    minSilenceMs: 700,
    minSpeechMs: 120,
    minSegmentMs: 120,
    maxSpeechS: 20.0
  };

  const handleApplyPreset = (preset) => {
    if (onChangeVadSettings) {
      onChangeVadSettings({
        preset: preset.id,
        vadThreshold: preset.vadThreshold,
        minSilenceMs: preset.minSilenceMs,
        minSpeechMs: preset.minSpeechMs,
        minSegmentMs: preset.minSegmentMs,
        maxSpeechS: preset.maxSpeechS
      });
    }
  };

  const handleUpdateParam = (key, value) => {
    if (onChangeVadSettings) {
      onChangeVadSettings((prev) => ({
        ...prev,
        preset: "custom",
        [key]: value
      }));
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="interview-container">
      <div className="question-header">
        <div className="question-meta-row">
          <span className="question-badge">Question {questionNumber} of {totalQuestions}</span>
          <span className="skill-pill">Skills: {question.skills.join(", ")}</span>
          <span className="mode-pill">Mode: {sttMode.toUpperCase()}</span>
        </div>
        <h3 className="interview-question-text">{question.text}</h3>
      </div>

      {(isTtsActive || isGnaniTtsActive) && (
        <div className="question-tts-card" style={{
          background: isSarvamTheme ? "#eff6ff" : "#faf5ff",
          border: isSarvamTheme ? "1px solid #bfdbfe" : "1px solid #d8b4fe",
          borderRadius: "var(--radius)",
          padding: "12px 16px",
          marginBottom: "16px"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "1.2rem" }}>🎙️</span>
              <span style={{ fontSize: "0.85rem", color: isSarvamTheme ? "#1e40af" : "#6b21a8" }}>
                Interviewer: <strong>{activeVoiceName}</strong> ({isSarvamTheme ? "Sarvam Bulbul TTS" : "Gnani TTS"})
              </span>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              {ttsLoading ? (
                <span style={{ fontSize: "0.85rem", color: isSarvamTheme ? "#2563eb" : "#7c3aed", display: "flex", alignItems: "center", gap: "6px" }}>
                  <span>⏳</span> Reading question...
                </span>
              ) : ttsPlaying ? (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={onPauseAudio}
                  style={{ fontSize: "0.8rem", padding: "4px 10px" }}
                >
                  ⏸ Pause
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={onReplayAudio}
                  disabled={isRecording}
                  style={{ fontSize: "0.8rem", padding: "4px 10px" }}
                >
                  🔊 Replay Question
                </button>
              )}
            </div>
          </div>

          {ttsPlaying && (
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "8px", fontSize: "0.8rem", color: isSarvamTheme ? "#1e40af" : "#7c3aed" }}>
              <span className="tts-pulse-dot" style={{ background: isSarvamTheme ? "#2563eb" : "#7c3aed" }} />
              <span>Speaking: &ldquo;{question.text.length > 60 ? question.text.slice(0, 60) + '...' : question.text}&rdquo;</span>
            </div>
          )}

          {ttsError && (
            <div style={{
              background: "var(--error-bg)",
              color: "var(--error-text)",
              border: "1px solid var(--error-border)",
              borderRadius: "4px",
              padding: "6px 10px",
              marginTop: "8px",
              fontSize: "0.8rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center"
            }}>
              <span>Audio notice: {ttsError}</span>
              {onReplayAudio && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={onReplayAudio}
                  style={{ fontSize: "0.75rem", padding: "2px 8px" }}
                >
                  Retry Audio
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {micPermissionError && (
        <div className="alert-error" role="alert">
          <strong>Microphone Error: </strong> {micPermissionError}
        </div>
      )}

      {/* Gnani VAD Tuning & Live Audio Engine Demo Panel */}
      {(isGnaniProvider || sttMode === "gnani" || isGnaniTtsActive) && (
        <div className="gnani-vad-card">
          <div className="gnani-vad-header" onClick={() => setVadPanelOpen((v) => !v)}>
            <div className="gnani-vad-title-group">
              <span className="vad-icon">🎛️</span>
              <div>
                <div className="vad-title-line">
                  <h4 className="gnani-vad-title">Gnani Voice Activity Detection (VAD) Tuning</h4>
                  <span className={`vad-preset-tag ${currentVad.preset}`}>
                    {currentVad.preset === "custom" ? "Custom Tuning" : VAD_PRESETS.find(p => p.id === currentVad.preset)?.label || currentVad.preset}
                  </span>
                </div>
                <p className="vad-subtitle">
                  Direct WebSocket header tuning for <code>wss://api.vachana.ai/stt/v3/stream</code>
                </p>
              </div>
            </div>
            <button
              type="button"
              className="btn-vad-toggle"
              aria-label="Toggle VAD controls"
            >
              {vadPanelOpen ? "Hide Controls ▲" : "Adjust Parameters ▼"}
            </button>
          </div>

          {vadPanelOpen && (
            <div className="gnani-vad-body">
              {/* Tabs */}
              <div className="vad-tabs">
                <button
                  type="button"
                  className={`vad-tab-btn ${activeTab === "sliders" ? "active" : ""}`}
                  onClick={() => setActiveTab("sliders")}
                >
                  Sliders & Presets
                </button>
                <button
                  type="button"
                  className={`vad-tab-btn ${activeTab === "headers" ? "active" : ""}`}
                  onClick={() => setActiveTab("headers")}
                >
                  Raw WebSocket Headers
                </button>
                <button
                  type="button"
                  className={`vad-tab-btn ${activeTab === "guide" ? "active" : ""}`}
                  onClick={() => setActiveTab("guide")}
                >
                  Optimal Settings Guide
                </button>
              </div>

              {/* Tab 1: Sliders & Presets */}
              {activeTab === "sliders" && (
                <div className="vad-sliders-view">
                  {/* Preset Pills */}
                  <div className="vad-presets-row">
                    <span className="vad-row-label">Demo Presets:</span>
                    <div className="vad-preset-buttons">
                      {VAD_PRESETS.map((preset) => (
                        <button
                          key={preset.id}
                          type="button"
                          className={`vad-preset-btn ${currentVad.preset === preset.id ? "active" : ""}`}
                          onClick={() => handleApplyPreset(preset)}
                          disabled={isRecording}
                          title={preset.summary}
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Preset Summary Box */}
                  <div className="vad-preset-description">
                    <strong>Current Profile: </strong>
                    {currentVad.preset === "custom"
                      ? "Custom parameter adjustments active. Test variations during speech to observe turnaround latency."
                      : VAD_PRESETS.find((p) => p.id === currentVad.preset)?.summary}
                  </div>

                  {/* 5 Interactive Range Sliders */}
                  <div className="vad-sliders-grid">
                    {/* 1. vad_threshold */}
                    <div className="vad-slider-item">
                      <div className="vad-slider-top">
                        <label className="vad-param-label">
                          <code>x-vad-threshold</code>
                          <span className="vad-friendly-name">Speech Confidence</span>
                        </label>
                        <span className="vad-value-badge">{Number(currentVad.vadThreshold).toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min="0.10"
                        max="1.00"
                        step="0.05"
                        disabled={isRecording}
                        value={currentVad.vadThreshold}
                        onChange={(e) => handleUpdateParam("vadThreshold", parseFloat(e.target.value))}
                        className="vad-range-input"
                      />
                      <div className="vad-range-scale">
                        <span>0.10 (Sensitive)</span>
                        <span className="vad-optimal-mark">★ 0.55 Optimal</span>
                        <span>1.00 (Strict)</span>
                      </div>
                      <p className="vad-param-desc">
                        Confidence floor required to treat a frame as human speech. Prevents picking up breathing while retaining soft candidate answers.
                      </p>
                    </div>

                    {/* 2. min_silence_ms */}
                    <div className="vad-slider-item">
                      <div className="vad-slider-top">
                        <label className="vad-param-label">
                          <code>x-min-silence-ms</code>
                          <span className="vad-friendly-name">Silence to Finalize</span>
                        </label>
                        <span className="vad-value-badge">{currentVad.minSilenceMs} ms</span>
                      </div>
                      <input
                        type="range"
                        min="100"
                        max="2000"
                        step="50"
                        disabled={isRecording}
                        value={currentVad.minSilenceMs}
                        onChange={(e) => handleUpdateParam("minSilenceMs", parseInt(e.target.value, 10))}
                        className="vad-range-input"
                      />
                      <div className="vad-range-scale">
                        <span>100 ms (Fast Cutoff)</span>
                        <span className="vad-optimal-mark">★ 700 ms Optimal</span>
                        <span>2000 ms (Patient)</span>
                      </div>
                      <p className="vad-param-desc">
                        Continuous silence before finalizing an utterance. 700ms prevents candidate thinking pauses from splitting answers mid-sentence.
                      </p>
                    </div>

                    {/* 3. min_speech_ms */}
                    <div className="vad-slider-item">
                      <div className="vad-slider-top">
                        <label className="vad-param-label">
                          <code>x-min-speech-ms</code>
                          <span className="vad-friendly-name">Speech Onset Filter</span>
                        </label>
                        <span className="vad-value-badge">{currentVad.minSpeechMs} ms</span>
                      </div>
                      <input
                        type="range"
                        min="50"
                        max="1000"
                        step="10"
                        disabled={isRecording}
                        value={currentVad.minSpeechMs}
                        onChange={(e) => handleUpdateParam("minSpeechMs", parseInt(e.target.value, 10))}
                        className="vad-range-input"
                      />
                      <div className="vad-range-scale">
                        <span>50 ms (Immediate)</span>
                        <span className="vad-optimal-mark">★ 120 ms Optimal</span>
                        <span>1000 ms (Heavy Gate)</span>
                      </div>
                      <p className="vad-param-desc">
                        Noise gate duration before confirming speech. Filters microphone bumps, coughs, and throat clears (&lt;100ms) without clipping words.
                      </p>
                    </div>

                    {/* 4. min_segment_ms */}
                    <div className="vad-slider-item">
                      <div className="vad-slider-top">
                        <label className="vad-param-label">
                          <code>x-min-segment-ms</code>
                          <span className="vad-friendly-name">Utterance Floor</span>
                        </label>
                        <span className="vad-value-badge">{currentVad.minSegmentMs} ms</span>
                      </div>
                      <input
                        type="range"
                        min="100"
                        max="1000"
                        step="20"
                        disabled={isRecording}
                        value={currentVad.minSegmentMs}
                        onChange={(e) => handleUpdateParam("minSegmentMs", parseInt(e.target.value, 10))}
                        className="vad-range-input"
                      />
                      <div className="vad-range-scale">
                        <span>100 ms</span>
                        <span className="vad-optimal-mark">★ 120 ms Optimal</span>
                        <span>1000 ms</span>
                      </div>
                      <p className="vad-param-desc">
                        Minimum length to register an utterance. Retains short 1-word technical replies like &ldquo;True&rdquo;, &ldquo;False&rdquo;, &ldquo;int&rdquo;, &ldquo;SQL&rdquo;.
                      </p>
                    </div>

                    {/* 5. max_speech_s */}
                    <div className="vad-slider-item">
                      <div className="vad-slider-top">
                        <label className="vad-param-label">
                          <code>x-max-speech-s</code>
                          <span className="vad-friendly-name">Max Speech Chunk</span>
                        </label>
                        <span className="vad-value-badge">{Number(currentVad.maxSpeechS).toFixed(1)} s</span>
                      </div>
                      <input
                        type="range"
                        min="5.0"
                        max="60.0"
                        step="1.0"
                        disabled={isRecording}
                        value={currentVad.maxSpeechS}
                        onChange={(e) => handleUpdateParam("maxSpeechS", parseFloat(e.target.value))}
                        className="vad-range-input"
                      />
                      <div className="vad-range-scale">
                        <span>5.0 s</span>
                        <span className="vad-optimal-mark">★ 20.0 s Optimal</span>
                        <span>60.0 s</span>
                      </div>
                      <p className="vad-param-desc">
                        Monologue chunking cap. Forces transcript emission every 20 seconds during continuous answers even without candidate pauses.
                      </p>
                    </div>
                  </div>

                  <div className="vad-actions-footer">
                    <button
                      type="button"
                      className="btn-vad-reset"
                      onClick={() => handleApplyPreset(VAD_PRESETS[0])}
                      disabled={isRecording}
                    >
                      ↺ Reset to Optimal Settings (Interview Preset)
                    </button>
                    {isRecording && (
                      <span className="vad-locked-notice">
                        🔒 Parameters locked while recording stream is active.
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 2: Raw WebSocket Headers */}
              {activeTab === "headers" && (
                <div className="vad-headers-view">
                  <p className="vad-tab-explainer">
                    These headers are injected into the WebSocket handshake with <code>wss://api.vachana.ai/stt/v3/stream</code>. The official Gnani documentation confirms that VAD tuning is supported exclusively via raw WebSocket connection headers (the Python SDK does not currently expose them).
                  </p>
                  <pre className="vad-code-block">
{`GET /stt/v3/stream HTTP/1.1
Host: api.vachana.ai
Upgrade: websocket
Connection: Upgrade
x-vad-threshold: ${Number(currentVad.vadThreshold).toFixed(2)}
x-min-silence-ms: ${currentVad.minSilenceMs}
x-min-speech-ms: ${currentVad.minSpeechMs}
x-min-segment-ms: ${currentVad.minSegmentMs}
x-max-speech-s: ${Number(currentVad.maxSpeechS).toFixed(1)}
x-audio-format: pcm16
x-audio-sample-rate: 16000
x-language-code: en-IN (or auto-detected)
x-bias-list: Python, JavaScript, React, FastAPI, SQL, Docker, Kubernetes, AWS, Git
x-bias-score: 1.5`}
                  </pre>
                  <div className="vad-audio-contract-notice">
                    <strong>Audio Framing Contract:</strong> Audio must be streamed in <strong>1,024-byte frames</strong> (512 samples × 2 bytes at 16kHz PCM) sent every 32ms. Our backend client buffers and paces the audio chunks precisely to fulfill this contract.
                  </div>
                </div>
              )}

              {/* Tab 3: Optimal Settings Guide */}
              {activeTab === "guide" && (
                <div className="vad-guide-view">
                  <table className="vad-guide-table">
                    <thead>
                      <tr>
                        <th>Parameter</th>
                        <th>Documented Range</th>
                        <th>Default</th>
                        <th>Recommended Setting</th>
                        <th>Interview Impact &amp; Trade-off</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td><code>x-vad-threshold</code></td>
                        <td>0.0 &ndash; 1.0</td>
                        <td>0.70</td>
                        <td><span className="badge-optimal">0.55</span></td>
                        <td>Captures gentle/thoughtful voices and whispered code explanations without triggering on ambient room hiss.</td>
                      </tr>
                      <tr>
                        <td><code>x-min-silence-ms</code></td>
                        <td>100 &ndash; 2000 ms</td>
                        <td>500 ms</td>
                        <td><span className="badge-optimal">700 ms</span></td>
                        <td>Prevents premature transcription splits when candidates pause briefly to organize thoughts mid-sentence.</td>
                      </tr>
                      <tr>
                        <td><code>x-min-speech-ms</code></td>
                        <td>50 &ndash; 2000 ms</td>
                        <td>100 ms</td>
                        <td><span className="badge-optimal">120 ms</span></td>
                        <td>Acts as a front-end noise gate. Eliminates microphone handling thumps and throat-clearing without swallowing the first syllable.</td>
                      </tr>
                      <tr>
                        <td><code>x-min-segment-ms</code></td>
                        <td>100 &ndash; 1000 ms</td>
                        <td>120 ms</td>
                        <td><span className="badge-optimal">120 ms</span></td>
                        <td>Preserves short one-word technical answers (e.g. &ldquo;True&rdquo;, &ldquo;Null&rdquo;, &ldquo;O(n)&rdquo;) that might otherwise be discarded as glitch noise.</td>
                      </tr>
                      <tr>
                        <td><code>x-max-speech-s</code></td>
                        <td>5.0 &ndash; 120.0 s</td>
                        <td>Disabled</td>
                        <td><span className="badge-optimal">20.0 s</span></td>
                        <td>Monologue cap: forces intermediate transcript flushes every 20s so live interviewers see text progressing during long explanations.</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="recording-control-panel">
        <div className="recording-status-row">
          <div className="status-indicator-group">
            <span className={`status-dot ${isRecording ? "pulsing" : ""}`} />
            <span className="status-text">
              {isRecording ? "Recording in progress..." : audioBlob ? "Answer captured" : "Ready to record"}
            </span>
          </div>

          <div className="timer-badge">
            ⏱ {formatTime(recordingTime)}
          </div>

          {(isGnaniProvider || sttMode === "gnani" || isGnaniTtsActive) && (
            <div className="vad-active-status-badge" title="Active Gnani VAD WebSocket Header Parameters">
              ⚙️ VAD: {currentVad.preset === "custom" ? "Custom" : currentVad.preset.replace("_", " ")} (Thr: {Number(currentVad.vadThreshold).toFixed(2)}, Sil: {currentVad.minSilenceMs}ms)
            </div>
          )}

          {latencyMs && (
            <div className="vad-latency-badge" title="Turnaround speed from candidate pause until transcription delivery">
              ⚡ Turnaround: <strong>{latencyMs} ms</strong>
            </div>
          )}

          {audioMetadata && audioMetadata.rawSampleRate && (
            <div className="audio-spec-badge">
              {audioMetadata.rawSampleRate}Hz → 16kHz PCM ({audioMetadata.channels}ch)
            </div>
          )}
        </div>

        {/* Centered Microphone Action Button */}
        <div className="mic-center-container">
          <button
            type="button"
            className={`mic-button ${isRecording ? "recording" : audioBlob ? "captured" : ""}`}
            onClick={isRecording ? onStopRecording : onStartRecording}
            disabled={isComparing}
            aria-label={isRecording ? "Stop Recording" : "Start Recording"}
            title={isRecording ? "Click to stop recording" : "Click to start recording"}
          >
            {isRecording ? (
              <svg className="mic-svg-icon stop-icon" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="2.5" />
              </svg>
            ) : (
              <svg
                className="mic-svg-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="22" />
              </svg>
            )}
          </button>

          <span className="mic-button-label">
            {isRecording ? "Stop Recording" : "Start Recording"}
          </span>

          <span className="mic-button-subtext">
            {isRecording
              ? "Recording in progress • Click to stop"
              : audioBlob
              ? "Answer captured • Click to re-record"
              : "Click the microphone to begin your answer"}
          </span>

          {audioBlob && !isRecording && (
            <div className="mic-secondary-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onRetryAnswer}
                disabled={isComparing}
              >
                🔄 Reset Answer
              </button>

              <button
                type="button"
                className="btn btn-success"
                onClick={onFinishAnswer}
                disabled={!canFinish || isComparing}
              >
                {isComparing ? "Processing Providers..." : "✓ Confirm & Save Answer"}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Audio Playback of Recorded Answer */}
      {audioBlob && (
        <div className="audio-playback-section">
          <label className="audio-label">Captured Answer Playback:</label>
          <audio
            controls
            src={URL.createObjectURL(audioBlob)}
            className="audio-player"
          />
        </div>
      )}

      {/* Real-time Transcription Views */}
      <div className="transcripts-grid">
        <div className={`transcript-box ${isRecording ? "streaming-active" : ""}`}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <h4 className="transcript-title" style={{ margin: 0 }}>
              Live Parallel Transcription {isRecording && <span className="listening-tag">● Streaming Now</span>}
            </h4>
            {isRecording && livePartial && (
              <span className="parallel-live-tag" style={{ fontSize: "0.74rem", color: "#15803d", fontWeight: 700 }}>
                ⚡ Parallel Live
              </span>
            )}
          </div>
          <div className="transcript-content">
            {isRecording ? (
              livePartial ? (
                <span className="live-partial-text" style={{ color: "#1e40af", fontWeight: 500 }}>
                  {livePartial} <span className="streaming-cursor">▌</span>
                </span>
              ) : (
                <span className="placeholder-text" style={{ color: "#2563eb" }}>
                  🎙️ Listening... speak now to see words transcribe parallelly in real time.
                </span>
              )
            ) : livePartial || finalTranscript ? (
              <span>{finalTranscript || livePartial}</span>
            ) : (
              <span className="placeholder-text">Click &ldquo;Start Answering&rdquo; and speak into your microphone to view live transcriptions...</span>
            )}
          </div>
        </div>

        <div className="transcript-box">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <h4 className="transcript-title" style={{ margin: 0 }}>Finalized Transcript</h4>
            {latencyMs && (
              <span className="transcript-latency-pill" title="Turnaround speed from silence gate to transcription">
                ⚡ Turnaround: <strong>{latencyMs} ms</strong> (Silence Gate: {currentVad.minSilenceMs}ms)
              </span>
            )}
          </div>
          <div className="transcript-content final-text">
            {finalTranscript ? (
              <span>{finalTranscript}</span>
            ) : isRecording ? (
              <span className="placeholder-text">
                Utterance will finalize and commit here after silence ({currentVad.minSilenceMs}ms)...
              </span>
            ) : (
              <span className="placeholder-text">Final transcript will appear here when speech concludes.</span>
            )}
          </div>
        </div>
      </div>

      {/* Comparison View (when mode is compare and evaluation complete) */}
      {sttMode === "compare" && comparisonResults && (
        <div className="comparison-side-by-side">
          <h4 className="comparison-header-title">Side-by-Side Provider Benchmark</h4>
          <div className="comparison-grid">
            <div className="provider-col google-col">
              <div className="provider-name-bar">
                <h5>Google Cloud STT</h5>
                <span className={`provider-status ${comparisonResults.google?.status}`}>
                  {comparisonResults.google?.status || "Unavailable"}
                </span>
              </div>
              <p className="provider-transcript">
                {comparisonResults.google?.transcript || "No transcript returned"}
              </p>
              <div className="metric-row">
                <span>Latency:</span>
                <strong>{comparisonResults.google?.latencyMs ? `${comparisonResults.google.latencyMs} ms` : "N/A"}</strong>
              </div>
              {comparisonResults.google?.error && (
                <div className="provider-error-msg">{comparisonResults.google.error}</div>
              )}
            </div>

            <div className="provider-col sarvam-col">
              <div className="provider-name-bar">
                <h5>Sarvam AI Saaras v4</h5>
                <span className={`provider-status ${comparisonResults.sarvam?.status}`}>
                  {comparisonResults.sarvam?.status || "Unavailable"}
                </span>
              </div>
              <p className="provider-transcript">
                {comparisonResults.sarvam?.transcript || "No transcript returned"}
              </p>
              <div className="metric-row">
                <span>Latency:</span>
                <strong>{comparisonResults.sarvam?.latencyMs ? `${comparisonResults.sarvam.latencyMs} ms` : "N/A"}</strong>
              </div>
              {comparisonResults.sarvam?.error && (
                <div className="provider-error-msg">{comparisonResults.sarvam.error}</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
