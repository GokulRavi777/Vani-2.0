/**
 * Lightweight frontend contract and sanity check.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function assert(condition, message) {
  if (!condition) {
    console.error(`❌ Check failed: ${message}`);
    process.exit(1);
  }
}

console.log("Running frontend checks...");

// 1. Verify required source files exist
const requiredFiles = [
  "src/main.jsx",
  "src/App.jsx",
  "src/index.css",
  "src/api/client.js",
  "src/components/SkillSelector.jsx",
  "src/components/AssessmentView.jsx",
  "src/components/SessionStatusBadge.jsx"
];

for (const file of requiredFiles) {
  const fullPath = path.join(__dirname, file);
  assert(fs.existsSync(fullPath), `File ${file} must exist`);
}
console.log("✅ All required frontend component files exist.");

// 2. Check SkillSelector defines the 4 predefined skills
const skillSelectorContent = fs.readFileSync(path.join(__dirname, "src/components/SkillSelector.jsx"), "utf-8");
const expectedSkills = ["Python", "SQL", "Java", "Machine Learning"];
for (const skill of expectedSkills) {
  assert(skillSelectorContent.includes(skill), `SkillSelector must support ${skill}`);
}
assert(skillSelectorContent.includes("Start Assessment"), "SkillSelector must include 'Start Assessment' button");
assert(skillSelectorContent.includes("select at least one"), "SkillSelector must have validation message for empty selection");
console.log("✅ SkillSelector contract verified.");

// 3. Check AssessmentView supports 2-question navigation without re-generation
const assessmentViewContent = fs.readFileSync(path.join(__dirname, "src/components/AssessmentView.jsx"), "utf-8");
assert(assessmentViewContent.includes("Question 1") || assessmentViewContent.includes("Question"), "AssessmentView must navigate questions");
assert(assessmentViewContent.includes("Previous Question"), "AssessmentView must have Previous button");
assert(assessmentViewContent.includes("Next Question"), "AssessmentView must have Next button");
assert(assessmentViewContent.includes("SessionStatusBadge"), "AssessmentView must render SessionStatusBadge");
console.log("✅ AssessmentView contract verified.");

// 4. Check SessionStatusBadge shows assessment ID and fallback vs AI provenance
const statusBadgeContent = fs.readFileSync(path.join(__dirname, "src/components/SessionStatusBadge.jsx"), "utf-8");
assert(statusBadgeContent.includes("assessment_id"), "SessionStatusBadge must show assessment_id");
assert(statusBadgeContent.includes("Deterministic Fallback Bank"), "SessionStatusBadge must show Fallback badge");
assert(statusBadgeContent.includes("Configured AI Generator"), "SessionStatusBadge must show AI generator badge");
console.log("✅ SessionStatusBadge contract verified.");

// 5. Check dist output from build
assert(fs.existsSync(path.join(__dirname, "dist/index.html")), "Build output dist/index.html must exist");
console.log("✅ Production build artifacts verified.");

console.log("\nAll frontend checks passed successfully!");
