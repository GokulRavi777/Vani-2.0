import React, { useState, useEffect } from "react";
import { fetchSkills } from "../api/client";

const DEFAULT_SKILLS = ["Python", "SQL", "Java", "Machine Learning"];

export default function SkillSelector({ onStartAssessment, isSubmitting, errorMessage }) {
  const [availableSkills, setAvailableSkills] = useState(DEFAULT_SKILLS);
  const [selectedSkills, setSelectedSkills] = useState([]);
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    fetchSkills()
      .then((data) => {
        if (data && Array.isArray(data.skills) && data.skills.length > 0) {
          setAvailableSkills(data.skills);
        }
      })
      .catch(() => {
        // Fallback to DEFAULT_SKILLS if backend is initializing
      });
  }, []);

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
    onStartAssessment(selectedSkills);
  };

  return (
    <section className="card" aria-labelledby="skill-selection-title">
      <h2 id="skill-selection-title" className="card-title">
        Select Technical Skill
      </h2>
      <p className="card-subtitle">
        Select exactly one skill for your interview assessment. Exactly two questions will be generated.
      </p>

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
        >
          {isSubmitting ? "Generating Assessment..." : "Start Assessment"}
        </button>
      </div>
    </section>
  );
}
