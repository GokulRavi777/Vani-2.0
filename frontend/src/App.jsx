import React, { useState } from "react";
import SkillSelector from "./components/SkillSelector";
import AssessmentView from "./components/AssessmentView";
import { createAssessment } from "./api/client";

export default function App() {
  const [assessment, setAssessment] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleStartAssessment = async (selectedSkills) => {
    setIsSubmitting(true);
    setErrorMessage("");

    try {
      const response = await createAssessment({
        skills: selectedSkills,
        language: "en-IN",
        questionCount: 2,
        sttMode: "google"
      });
      setAssessment(response);
    } catch (err) {
      setErrorMessage(err.message || "Failed to generate assessment. Please check backend connection.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setAssessment(null);
    setErrorMessage("");
  };

  return (
    <main className="container">
      <header className="app-header">
        <h1>Vani 2.0 POC — Assessment Engine</h1>
        <p>Proof of concept for speech recognition benchmarking (Stage 1: Application Skeleton)</p>
      </header>

      {!assessment ? (
        <SkillSelector
          onStartAssessment={handleStartAssessment}
          isSubmitting={isSubmitting}
          errorMessage={errorMessage}
        />
      ) : (
        <AssessmentView assessment={assessment} onReset={handleReset} />
      )}
    </main>
  );
}
