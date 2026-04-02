import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  timeout: 120000, // 2 minutes — pipeline can take time
});

export async function analyzeResume(resumeText, jobDescription) {
  const { data } = await api.post("/analyze", {
    resume_text: resumeText,
    job_description: jobDescription,
  });
  return data;
}

export async function parseResumeFile(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/parse-resume", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data; // { text: string }
}

export async function getResumes() {
  const { data } = await api.get("/resumes");
  return data;
}

export async function getResults() {
  const { data } = await api.get("/results");
  return data;
}

export async function getResultById(id) {
  const { data } = await api.get(`/results/${id}`);
  return data;
}
