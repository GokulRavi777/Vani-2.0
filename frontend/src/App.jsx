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
  const [selectedSttMode, setSelectedSttMode] = useState("sarvam");

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
            <h1>Vani 2.0 POC — Technical Assessment</h1>
            <p>Real-Time Speech Recognition powered by Sarvam AI Saaras v4</p>
          </div>
          <div className="mode-selector-header">
            <span className="badge" style={{ background: "#2563eb", color: "#fff", padding: "6px 12px", borderRadius: "16px", fontSize: "0.85rem", fontWeight: 600 }}>
              STT: Sarvam Saaras v4
            </span>
          </div>
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
