import React from "react";

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
  comparisonResults,
  isComparing,
  micPermissionError,
  providerError,
  audioBlob,
  onStartRecording,
  onStopRecording,
  onRetryAnswer,
  onFinishAnswer,
  canFinish
}) {
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

      {micPermissionError && (
        <div className="alert-error" role="alert">
          <strong>Microphone Error: </strong> {micPermissionError}
        </div>
      )}

      {providerError && (
        <div className="alert-error" role="alert">
          <strong>Provider Notice: </strong> {providerError}
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

          {audioMetadata && audioMetadata.rawSampleRate && (
            <div className="audio-spec-badge">
              {audioMetadata.rawSampleRate}Hz → 16kHz PCM ({audioMetadata.channels}ch)
            </div>
          )}
        </div>

        <div className="action-buttons-row">
          {!isRecording ? (
            <button
              type="button"
              className="btn btn-primary"
              onClick={onStartRecording}
              disabled={isComparing}
            >
              🎤 {audioBlob ? "Record Again" : "Start Recording"}
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-danger"
              onClick={onStopRecording}
            >
              ⏹ Stop Recording
            </button>
          )}

          {audioBlob && !isRecording && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onRetryAnswer}
              disabled={isComparing}
            >
              🔄 Reset Answer
            </button>
          )}

          {audioBlob && !isRecording && (
            <button
              type="button"
              className="btn btn-success"
              onClick={onFinishAnswer}
              disabled={!canFinish || isComparing}
            >
              {isComparing ? "Processing Providers..." : "✓ Confirm & Save Answer"}
            </button>
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
        <div className="transcript-box">
          <h4 className="transcript-title">
            Live Partial Transcript {isRecording && <span className="listening-tag">Listening...</span>}
          </h4>
          <div className="transcript-content">
            {livePartial || <span className="placeholder-text">Speak into your microphone to view live transcriptions...</span>}
          </div>
        </div>

        <div className="transcript-box">
          <h4 className="transcript-title">Finalized Transcript</h4>
          <div className="transcript-content final-text">
            {finalTranscript || <span className="placeholder-text">Final transcript will appear here when speech concludes.</span>}
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
