/**
 * API Service Layer
 * Prepared to connect to the FastAPI backend described in the architecture doc.
 * Base URL is read from environment variable — set VITE_API_URL in .env
 */

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const headers = () => ({
  "Content-Type": "application/json",
});

async function handleResponse(res) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// POST /upload — multipart CSV upload, returns { upload_id, preview }
export async function uploadCSV(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}/upload`, {
    method: "POST",
    body: form,
  });
  return handleResponse(res);
}

// POST /analyze — kick off the analysis pipeline, returns { job_id }
export async function startAnalysis(uploadId) {
  const res = await fetch(`${BASE_URL}/analyze`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ upload_id: uploadId }),
  });
  return handleResponse(res);
}

// GET /status/{job_id} — poll for progress, returns { status, progress }
export async function getJobStatus(jobId) {
  const res = await fetch(`${BASE_URL}/status/${jobId}`);
  return handleResponse(res);
}

// GET /report/{id} — fetch the completed report, returns ReportResponse
export async function getReport(reportId) {
  const res = await fetch(`${BASE_URL}/report/${reportId}`);
  return handleResponse(res);
}

// GET /health — verify API reachability
export async function checkHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  return handleResponse(res);
}

/**
 * Convenience: full pipeline helper
 * Uploads → starts analysis → polls until done → returns report
 */
export async function runFullPipeline(file, onProgress) {
  // 1. Upload
  const { upload_id } = await uploadCSV(file);
  onProgress?.("uploaded", 20);

  // 2. Start analysis
  const { job_id } = await startAnalysis(upload_id);
  onProgress?.("analyzing", 40);

  // 3. Poll for completion
  let attempts = 0;
  const MAX_ATTEMPTS = 60; // 2 min at 2s intervals
  while (attempts < MAX_ATTEMPTS) {
    await new Promise((r) => setTimeout(r, 2000));
    const { status, progress } = await getJobStatus(job_id);
    onProgress?.(status, progress);
    if (status === "done") break;
    if (status === "error") throw new Error("Pipeline falhou no backend.");
    attempts++;
  }

  // 4. Fetch report
  const report = await getReport(job_id);
  onProgress?.("done", 100);
  return report;
}
