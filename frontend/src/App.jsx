import React, { useState } from "react";
import ProviderSelector from "./components/ProviderSelector";
import SkillSelector from "./components/SkillSelector";
import AssessmentView from "./components/AssessmentView";
import ResultsView from "./components/ResultsView";
import { createAssessment } from "./api/client";

export default function App() {
  const [selectedProvider, setSelectedProvider] = useState("sarvam");
  const [selectedVoice, setSelectedVoice] = useState("shubh");
  const [selectedLanguage, setSelectedLanguage] = useState("unknown");
  const [assessment, setAssessment] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  // viewMode: "provider" | "select" | "interview" | "results"
  const [viewMode, setViewMode] = useState("provider");
  const [completedAnswers, setCompletedAnswers] = useState({});
  const [selectedSttMode, setSelectedSttMode] = useState("sarvam");

  const handleSelectProvider = (provider) => {
    setSelectedProvider(provider);
    setSelectedSttMode(provider);
    setSelectedVoice(provider === "sarvam" ? "shubh" : "Kaveri");
    setErrorMessage("");
    setViewMode("select");
  };

  const handleStartAssessment = async (selectedSkills, voice = null, language = "unknown") => {
    setErrorMessage("");
    setIsSubmitting(true);

    const activeVoice = voice || selectedVoice || (selectedProvider === "sarvam" ? "shubh" : "Kaveri");
    const activeLang = language || selectedLanguage || "unknown";
    if (voice) {
      setSelectedVoice(voice);
    }
    if (language) {
      setSelectedLanguage(language);
    }

    try {
      const response = await createAssessment({
        skills: selectedSkills,
        language: activeLang,
        questionCount: 2,
        sttMode: selectedSttMode,
        provider: selectedProvider,
        voice: activeVoice
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
    setViewMode("provider");
    setErrorMessage("");
  };

  return (
    <main className="container">
      <header className="app-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <h1>Vani 2.0 POC — Technical Assessment</h1>
            <p>
              {selectedProvider === "gnani"
                ? "Voice Assessment & Question Reading powered by Gnani AI"
                : "Real-Time Speech Recognition powered by Sarvam AI Saaras v4"}
            </p>
          </div>
          <div className="mode-selector-header" style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            {viewMode !== "provider" && (
              <>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setViewMode("provider")}
                  style={{ fontSize: "0.8rem", padding: "4px 10px" }}
                  title="Switch speech and assessment provider"
                >
                  ← Switch Provider
                </button>
                <span
                  className="badge"
                  style={{
                    background: selectedProvider === "gnani" ? "#7c3aed" : "#2563eb",
                    color: "#fff",
                    padding: "6px 12px",
                    borderRadius: "16px",
                    fontSize: "0.85rem",
                    fontWeight: 600
                  }}
                >
                  {selectedProvider === "gnani"
                    ? `Provider: Gnani AI (${assessment?.voice || selectedVoice})`
                    : `Provider: Sarvam AI (${assessment?.voice || selectedVoice})`}
                </span>
              </>
            )}
          </div>
        </div>
      </header>

      {viewMode === "provider" && (
        <ProviderSelector
          currentProvider={selectedProvider}
          onSelectProvider={handleSelectProvider}
        />
      )}

      {viewMode === "select" && (
        <SkillSelector
          onStartAssessment={handleStartAssessment}
          isSubmitting={isSubmitting}
          errorMessage={errorMessage}
          selectedProvider={selectedProvider}
          initialVoice={selectedVoice}
          onChangeProvider={() => setViewMode("provider")}
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
