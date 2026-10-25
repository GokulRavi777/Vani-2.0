import React, { useState } from "react";
import SessionStatusBadge from "./SessionStatusBadge";

export default function AssessmentView({ assessment, onReset }) {
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);

  if (!assessment || !assessment.questions || assessment.questions.length !== 2) {
    return (
      <div className="card">
        <p className="alert-error">Invalid assessment session data. Please restart.</p>
        <button type="button" className="btn btn-secondary" onClick={onReset}>
          Restart Assessment
        </button>
      </div>
    );
  }

  const questions = assessment.questions;
  const currentQuestion = questions[currentQuestionIndex];
  const questionNumber = currentQuestionIndex + 1;
  const totalQuestions = questions.length;

  return (
    <div>
      <SessionStatusBadge assessment={assessment} />

      <section className="card" aria-labelledby="assessment-view-title">
        <div className="question-nav-container">
          <h2 id="assessment-view-title" className="card-title" style={{ margin: 0 }}>
            Technical Assessment
          </h2>
          <div className="stepper-tabs" role="tablist" aria-label="Question navigation">
            {questions.map((q, idx) => (
              <button
                key={q.question_id}
                type="button"
                role="tab"
                aria-selected={idx === currentQuestionIndex}
                className={`step-tab ${idx === currentQuestionIndex ? "active" : ""}`}
                onClick={() => setCurrentQuestionIndex(idx)}
              >
                Question {idx + 1}
              </button>
            ))}
          </div>
        </div>

        <div className="question-card-inner">
          <div className="question-meta">
            <span className="question-tag">Question ID: {currentQuestion.question_id}</span>
            <span className="question-tag">
              Targeted Skills: {currentQuestion.skills.join(", ")}
            </span>
          </div>

          <p className="question-text" data-testid="question-content">
            {currentQuestion.text}
          </p>
        </div>

        <div className="nav-controls">
          <div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setCurrentQuestionIndex((prev) => Math.max(0, prev - 1))}
              disabled={currentQuestionIndex === 0}
            >
              Previous Question
            </button>
            <span style={{ margin: "0 12px", fontSize: "0.9rem", color: "var(--text-muted)" }}>
              {questionNumber} of {totalQuestions}
            </span>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setCurrentQuestionIndex((prev) => Math.min(totalQuestions - 1, prev + 1))}
              disabled={currentQuestionIndex === totalQuestions - 1}
            >
              Next Question
            </button>
          </div>

          <button type="button" className="btn btn-secondary" onClick={onReset}>
            Change Skills / New Assessment
          </button>
        </div>

        <aside className="stage-note">
          <strong>Stage 1 Status:</strong> Question navigation active. Audio capture, Google TTS playback, and
          STT transcription pipelines will be integrated in Stages 2 through 4.
        </aside>
      </section>
    </div>
  );
}
