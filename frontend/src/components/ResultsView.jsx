import React from "react";

export default function ResultsView({ assessment, answers, onRestart }) {
  const questions = assessment.questions || [];

  return (
    <div className="card results-container" aria-labelledby="results-title">
      <div className="results-header">
        <h2 id="results-title" className="card-title">Assessment Benchmark Results</h2>
        <p className="card-subtitle">
          Session ID: <code>{assessment.assessment_id}</code> | Configured Mode: <strong>{(assessment.stt_mode || "google").toUpperCase()}</strong>
        </p>
      </div>

      <div className="results-list">
        {questions.map((q, idx) => {
          const answer = answers[q.question_id] || {};
          const comp = answer.comparisonResults;

          return (
            <div key={q.question_id} className="result-card">
              <div className="result-card-header">
                <h3>Question {idx + 1}: {q.text}</h3>
                <div className="result-meta">
                  <span className="skill-pill">Skills: {q.skills.join(", ")}</span>
                  <span className="question-tag">ID: {q.question_id}</span>
                </div>
              </div>

              {answer.audioBlob && (
                <div className="result-audio">
                  <label>Retained Audio Sample:</label>
                  <audio controls src={URL.createObjectURL(answer.audioBlob)} className="audio-player" />
                </div>
              )}

              {/* Benchmark Transcripts and Provider Breakdown */}
              <div className="result-breakdown">
                <h4>Transcripts & Provider Metrics</h4>
                <div className="provider-grid">
                  <div className="provider-box">
                    <div className="provider-title">
                      <h5>Google Cloud STT</h5>
                      <span className={`badge ${comp?.google?.status === "completed" ? "badge-ai" : "badge-fallback"}`}>
                        {comp?.google?.status || "Live Streamed"}
                      </span>
                    </div>
                    <div className="provider-body">
                      <p className="transcript-quote">
                        "{comp?.google?.transcript || answer.finalTranscript || "No speech recognized"}"
                      </p>
                      <div className="metrics-list">
                        <div>
                          <span>Latency / Time-to-final:</span>
                          <strong>{comp?.google?.latencyMs ? `${comp.google.latencyMs} ms` : answer.latencyMs ? `${answer.latencyMs} ms` : "N/A"}</strong>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="provider-box">
                    <div className="provider-title">
                      <h5>Sarvam AI Saaras v4</h5>
                      <span className={`badge ${comp?.sarvam?.status === "completed" ? "badge-ai" : "badge-fallback"}`}>
                        {comp?.sarvam?.status || (assessment.stt_mode === "compare" ? "Completed" : "Not Selected")}
                      </span>
                    </div>
                    <div className="provider-body">
                      <p className="transcript-quote">
                        "{comp?.sarvam?.transcript || (assessment.stt_mode === "sarvam" ? answer.finalTranscript : "Evaluation unavailable in non-Sarvam mode")}"
                      </p>
                      <div className="metrics-list">
                        <div>
                          <span>Latency / Time-to-final:</span>
                          <strong>{comp?.sarvam?.latencyMs ? `${comp.sarvam.latencyMs} ms` : "N/A"}</strong>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="results-actions">
        <button type="button" className="btn btn-primary" onClick={onRestart}>
          Start New Assessment
        </button>
      </div>
    </div>
  );
}
