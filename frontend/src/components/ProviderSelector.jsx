import React, { useState } from "react";

export default function ProviderSelector({ currentProvider = "sarvam", onSelectProvider }) {
  const [selected, setSelected] = useState(currentProvider || "sarvam");

  const providers = [
    {
      id: "sarvam",
      name: "Sarvam AI",
      subtitle: "Saaras v4 Real-Time Speech Recognition",
      description: "Full voice assessment powered by Sarvam AI Saaras v4 STT and Bulbul TTS. Real-time 16kHz audio streaming, Indian accent optimization, dual-stream benchmarking, and automated response scoring.",
      features: ["Saaras v4 STT", "WebSocket Streaming", "Bulbul TTS", "Benchmarking"],
      isReady: true
    },
    {
      id: "gnani",
      name: "Gnani AI",
      subtitle: "Indic Conversational Voice AI Platform",
      description: "Proprietary conversational speech recognition, question reading TTS, voice cloning, and VAD tuning engine for Indic languages.",
      features: ["Indic Voice AI", "VAD Tuning", "TTS & Voice Clone", "WebSocket Streaming"],
      isReady: true
    }
  ];

  const handleContinue = (e) => {
    e.preventDefault();
    if (onSelectProvider) {
      onSelectProvider(selected);
    }
  };

  return (
    <section className="card" aria-labelledby="provider-selection-title">
      <h2 id="provider-selection-title" className="card-title">
        Select Speech & Assessment Provider
      </h2>
      <p className="card-subtitle">
        Choose your AI voice recognition provider to power the interview assessment.
      </p>

      <div className="providers-grid" role="radiogroup" aria-label="Available AI providers">
        {providers.map((p) => {
          const isSelected = selected === p.id;
          const inputId = `provider-${p.id}`;

          return (
            <div
              key={p.id}
              role="radio"
              aria-checked={isSelected}
              tabIndex={0}
              id={inputId}
              className={`provider-card ${p.id === "gnani" ? "provider-gnani" : ""} ${isSelected ? "selected" : ""}`}
              onClick={() => setSelected(p.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setSelected(p.id);
                }
              }}
            >
              <div className="provider-card-header">
                <span className="provider-card-title">
                  <input
                    type="radio"
                    name="provider-selection"
                    checked={isSelected}
                    onChange={() => setSelected(p.id)}
                    style={{ marginRight: "6px", cursor: "pointer" }}
                    aria-label={p.name}
                  />
                  {p.name}
                </span>
              </div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                {p.subtitle}
              </div>
              <p className="provider-card-desc">{p.description}</p>
              <div className="provider-features">
                {p.features.map((feat) => (
                  <span key={feat} className="provider-feature-tag">
                    {feat}
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "16px" }}>
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleContinue}
          style={selected === "gnani" ? { background: "#7c3aed" } : {}}
        >
          {selected === "gnani" ? "Continue with Gnani AI →" : "Continue with Sarvam AI →"}
        </button>
      </div>
    </section>
  );
}
