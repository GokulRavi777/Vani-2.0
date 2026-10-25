import React, { useState } from "react";
import SkillSelector from "./components/SkillSelector";
import AssessmentView from "./components/AssessmentView";
import ResultsView from "./components/ResultsView";
import { createAssessment } from "./api/client";

export default function App() {
  const [assessment, setAssessment] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [viewMode, setViewMode] = useState("select"); // "select" | "interview" | "results"
  const [completedAnswers, setCompletedAnswers] = useState({});
  const [selectedSttMode, setSelectedSttMode] = useState("compare");

  const handleStartAssessment = async (selectedSkills) => {
    setIsSubmitting(true);
    setErrorMessage("");

    try {
      const response = await createAssessment({
        skills: selectedSkills,
        language: "en-IN",
        questionCount: 2,
        sttMode: selectedSttMode
      });
      setAssessment(response);
      setViewMode("interview");
    } catch (err) {
      setErrorMessage(err.message || "Failed to generate assessment. Please check backend connection.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAssessmentComplete = (answers) => {
    setCompletedAnswers(answers);
    setViewMode("results");
  };

  const handleReset = () => {
    setAssessment(null);
    setCompletedAnswers({});
    setViewMode("select");
    setErrorMessage("");
  };

  return (
    <main className="container">
      <header className="app-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h1>Vani 2.0 POC — Assessment & STT Benchmark</h1>
            <p>Google Cloud STT vs. Sarvam AI Saaras v4 Evaluation Platform</p>
          </div>
          {viewMode === "select" && (
            <div className="mode-selector-header">
              <label htmlFor="stt-mode-select" style={{ fontSize: "0.85rem", fontWeight: 600, marginRight: "8px" }}>
                Target Mode:
              </label>
              <select
                id="stt-mode-select"
                value={selectedSttMode}
                onChange={(e) => setSelectedSttMode(e.target.value)}
                className="select-dropdown"
              >
                <option value="compare">Compare Mode (Google vs Sarvam)</option>
                <option value="google">Google Cloud STT</option>
                <option value="sarvam">Sarvam AI Saaras v4</option>
              </select>
            </div>
          )}
        </div>
      </header>

      {viewMode === "select" && (
        <SkillSelector
          onStartAssessment={handleStartAssessment}
          isSubmitting={isSubmitting}
          errorMessage={errorMessage}
        />
      )}

      {viewMode === "interview" && assessment && (
        <AssessmentView
          assessment={assessment}
          onReset={handleReset}
          onComplete={handleAssessmentComplete}
        />
      )}

      {viewMode === "results" && assessment && (
        <ResultsView
          assessment={assessment}
          answers={completedAnswers}
          onRestart={handleReset}
        />
      )}
    </main>
  );
}
