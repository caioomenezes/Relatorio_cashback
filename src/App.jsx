import { useState, useRef } from "react";
import Header from "./components/shared/Header";
import UploadSection from "./components/upload/UploadSection";
import PipelineStatus from "./components/shared/PipelineStatus";
import MetricsDashboard from "./components/dashboard/MetricsDashboard";
import ReportSection from "./components/report/ReportSection";
import "./App.css";

// ── URL DO BACKEND ────────────────────────────────────────────────────────
const API_BASE_URL = "http://localhost:8000";

// ═════════════════════════════════════════════════════════════════════════
export default function App() {
  const [appState, setAppState]             = useState("idle");
  const [fileInfo, setFileInfo]             = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [pipelineStep, setPipelineStep]     = useState(0);
  const [sheetStatus, setSheetStatus]       = useState(null); // null | "saving" | "saved" | "error"

  // ── REF do bloco capturado no PDF (dashboard + relatório) ───────────────
  const pdfTargetRef = useRef(null);

  // ── FILE ───────────────────────────────────────────────────────────────
  const handleFileAccepted = (file) => {
    setFileInfo(file);
    setAppState("uploaded");
    setAnalysisResult(null);
    setPipelineStep(0);
  };

  // ── ANALYZE ────────────────────────────────────────────────────────────
  const handleAnalyze = async () => {
    if (!fileInfo) return;
    setAppState("analyzing");
    setPipelineStep(1);

    try {
      setPipelineStep(2);
      const form = new FormData();
      form.append("file", fileInfo.raw, fileInfo.name);
      const resp = await fetch(`${API_BASE_URL}/analyze`, { method: "POST", body: form });
      if (!resp.ok) throw new Error(`API error ${resp.status}`);
      setPipelineStep(3);
      const payload = await resp.json();
      console.log("validation.issues", JSON.stringify(payload?.validation?.issues, null, 2));
      if (payload?.metrics) {
        const metrics = payload.metrics;
        // Injeta avisos do backend dentro do resultado para não precisar de state extra
        metrics._backendWarnings = payload?.validation?.issues ?? [];
        setAnalysisResult(metrics);
      }
      setAppState("done");
      setPipelineStep(5);
    } catch (err) {
      console.error("Falha na análise:", err);
      setAnalysisResult(null);
      setAppState("error");
      setPipelineStep(0);
    }
  };

  // ── SALVAR VIA BACKEND ────────────────────────────────────────────────
  const handleAppendToSheet = async () => {
    if (!analysisResult) return;
    setSheetStatus("saving");

    try {
      // Determina o vencedor comparando o ROI de cada grupo
      const groups = analysisResult?.groups ?? {};
      const groupNames = Object.keys(groups);

      let winnerName = null;
      let winnerStats = null;
      for (const name of groupNames) {
        const g = groups[name] ?? {};
        const roi = g.roi ?? 0;
        if (winnerStats === null || roi > (winnerStats.roi ?? 0)) {
          winnerName = name;
          winnerStats = g;
        }
      }

      const winnerRoi = winnerStats?.roi ?? null;
      const roiFormatted = winnerRoi != null ? winnerRoi.toFixed(2) : "0.00";

      const row = {
        test_name:           fileInfo?.name ?? "experimento",
        decision:            winnerName,
        winner_roi:          winnerRoi,
        winner_net_revenue:  winnerStats?.net_revenue ?? null,
        description:         `Cada R$ 1,00 de cashback gera R$ ${roiFormatted} de receita líquida.`,
      };

      const resp = await fetch(`${API_BASE_URL}/append`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(row),
      });

      if (!resp.ok) {
        const err = await resp.text();
        throw new Error(`Backend /append error: ${err}`);
      }

      setSheetStatus("saved");
      setTimeout(() => setSheetStatus(null), 4000);
    } catch (err) {
      console.error("Erro ao salvar na planilha:", err);
      setSheetStatus("error");
      setTimeout(() => setSheetStatus(null), 5000);
    }
  };

  // ── RESET ──────────────────────────────────────────────────────────────
  const handleReset = () => {
    setAppState("idle"); setFileInfo(null);
    setAnalysisResult(null); setPipelineStep(0); setSheetStatus(null);
  };

  // ── CSV HELPERS ────────────────────────────────────────────────────────
  function normalizeHeader(h) {
    return h.toLowerCase().normalize("NFKD").replace(/\p{Diacritic}/gu, "").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  }
  function parseMonetary(s) {
    if (s == null) return 0;
    const v = String(s).replace(/R\$|\s/g, "").replace(/\./g, "").replace(/,/g, ".");
    const n = parseFloat(v);
    return Number.isFinite(n) ? n : 0;
  }
  function parseIntSafe(s) {
    const n = parseInt(String(s).replace(/\D/g, ""), 10);
    return Number.isFinite(n) ? n : 0;
  }

  function computeMetricsFromCSVText(text) {
    const lines = text.split(/\r?\n/).filter(Boolean);
    if (!lines.length) return null;
    const header = lines[0].split(/,|;|\t/).map((h) => normalizeHeader(h));
    const rows   = lines.slice(1).map((l) => l.split(/,|;|\t/).map((c) => c.trim()));
    const idx    = {};
    header.forEach((h, i) => { idx[h] = i; });

    const colGroup      = idx["group"]      ?? idx["grupos_de_usuarios"] ?? idx["grupos"];
    const colGmv        = idx["gmv"]        ?? idx["vendas_totais"]      ?? idx["vendas"];
    const colCommission = idx["commission"] ?? idx["comissao"]           ?? idx["commission_value"];
    const colCashback   = idx["cashback"]   ?? idx["valor_cashback"];
    const colConverted  = idx["converted"]  ?? idx["compradores"]        ?? idx["buyers"];

    if (colGroup == null || colGmv == null) return null;

    const groups = {};
    for (const r of rows) {
      const g = (r[colGroup] || "UNKNOWN").toString().trim().toUpperCase();
      if (!groups[g]) groups[g] = { total_users: 0, buyers: 0, gmv: 0, commission: 0, cashback: 0 };
      groups[g].total_users += 1;
      groups[g].buyers      += colConverted  != null ? parseIntSafe(r[colConverted])   : 0;
      groups[g].gmv         += parseMonetary(r[colGmv]);
      groups[g].commission  += colCommission != null ? parseMonetary(r[colCommission]) : 0;
      groups[g].cashback    += colCashback   != null ? parseMonetary(r[colCashback])   : 0;
    }

    const groupsOut  = {};
    const groupNames = Object.keys(groups).sort();
    for (const name of groupNames) {
      const s = groups[name];
      const buyers = s.buyers || 0;
      const net_revenue = s.commission - s.cashback;
      groupsOut[name] = {
        group_name: name, total_users: s.total_users,
        gmv:                  Number(s.gmv.toFixed(2)),
        commission:           Number(s.commission.toFixed(2)),
        cashback:             Number(s.cashback.toFixed(2)),
        net_revenue:          Number(net_revenue.toFixed(2)),
        avg_ticket:           Number((buyers ? s.gmv / buyers : 0).toFixed(2)),
        avg_cashback:         Number((buyers ? s.cashback / buyers : 0).toFixed(2)),
        commission_per_buyer: Number((buyers ? s.commission / buyers : 0).toFixed(2)),
        roi:                  Number((s.cashback ? net_revenue / s.cashback : 0).toFixed(4)),
        margin:               Number((s.gmv ? net_revenue / s.gmv : 0).toFixed(4)),
        conversion_rate:      Number((s.total_users ? buyers / s.total_users : 0).toFixed(6)),
      };
    }
    return { control_group: groupNames[0] ?? null, groups: groupsOut, lifts: {} };
  }

  // ── RENDER ─────────────────────────────────────────────────────────────
  return (
    <div className="app-root">
      <Header onReset={handleReset} hasData={appState !== "idle"} />

      {/* Toast */}
      {sheetStatus && (
        <div style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 999,
          padding: "10px 18px", borderRadius: 8, fontSize: 13, fontWeight: 500,
          background: sheetStatus === "saved" ? "rgba(29,158,117,0.15)" : sheetStatus === "error" ? "rgba(216,90,48,0.15)" : "rgba(55,138,221,0.15)",
          border: `0.5px solid ${sheetStatus === "saved" ? "rgba(29,158,117,0.4)" : sheetStatus === "error" ? "rgba(216,90,48,0.4)" : "rgba(55,138,221,0.4)"}`,
          color: sheetStatus === "saved" ? "#1D9E75" : sheetStatus === "error" ? "#D85A30" : "#378ADD",
        }}>
          {sheetStatus === "saving" && "⏳ Salvando na planilha…"}
          {sheetStatus === "saved"  && "✓ Linha adicionada com sucesso!"}
          {sheetStatus === "error"  && "✗ Erro ao salvar. Verifique o console."}
        </div>
      )}

      <main className="app-main">
        <div className="content-grid">
          <aside className="left-col">
            <UploadSection onFileAccepted={handleFileAccepted} fileInfo={fileInfo} appState={appState} onAnalyze={handleAnalyze} />
            {appState !== "idle" && <PipelineStatus currentStep={pipelineStep} appState={appState} />}
          </aside>

          <section className="right-col">
            {(appState === "idle" || appState === "uploaded") && <EmptyState appState={appState} />}
            {(appState === "analyzing" || appState === "done" || appState === "error") && (
              <div ref={pdfTargetRef}>
                <MetricsDashboard result={analysisResult} loading={appState === "analyzing"} />
                <ReportSection
                  result={analysisResult}
                  loading={appState === "analyzing"}
                  onAppend={handleAppendToSheet}
                  sheetStatus={sheetStatus}
                  pdfTargetRef={pdfTargetRef}
                />
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

function EmptyState({ appState }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        {appState === "idle" ? (
          <svg viewBox="0 0 80 80" fill="none">
            <circle cx="40" cy="40" r="38" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="4 4" />
            <path d="M40 22v36M22 40h36" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" opacity="0.4" />
            <circle cx="40" cy="40" r="6" fill="var(--accent)" opacity="0.2" />
          </svg>
        ) : (
          <svg viewBox="0 0 80 80" fill="none">
            <circle cx="40" cy="40" r="38" stroke="var(--accent)" strokeWidth="1.5" />
            <path d="M26 40l10 10 18-20" stroke="var(--success)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </div>
      <h2 className="empty-title">{appState === "idle" ? "Nenhum experimento carregado" : "Arquivo pronto para análise"}</h2>
      <p className="empty-desc">
        {appState === "idle"
          ? "Faça upload de um arquivo CSV com os dados do experimento A/B para começar."
          : 'Clique em "Analisar Experimento" para iniciar o pipeline de análise estatística.'}
      </p>
    </div>
  );
}