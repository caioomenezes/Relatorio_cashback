import "./PipelineStatus.css";

const STEPS = [
  { id: 1, label: "Parse & Validação",     icon: "parse",   desc: "Leitura e limpeza do CSV" },
  { id: 2, label: "Métricas de Negócio",   icon: "metrics", desc: "Conversão, ARPU, ticket" },
  { id: 3, label: "Testes Estatísticos",   icon: "stats",   desc: "Teste Z/T, p-value, IC 95%" },
  { id: 4, label: "Interpretação LLM",     icon: "llm",     desc: "Claude analisa os resultados" },
  { id: 5, label: "Registro no Sheets",    icon: "sheets",  desc: "Persistência auditável" },
];

const ICONS = {
  parse: (
    <svg viewBox="0 0 14 14" fill="none">
      <rect x="2" y="1" width="10" height="12" rx="2" stroke="currentColor" strokeWidth="1.3" />
      <path d="M4 5h6M4 8h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  ),
  metrics: (
    <svg viewBox="0 0 14 14" fill="none">
      <path d="M2 11V7M6 11V3M10 11V6M13 11H1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  ),
  stats: (
    <svg viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.3" />
      <path d="M5 7h4M7 5v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  ),
  llm: (
    <svg viewBox="0 0 14 14" fill="none">
      <path d="M2 3h10a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H8l-2 2V10H2a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" stroke="currentColor" strokeWidth="1.3" />
      <path d="M4 7h6M4 5.5h4" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.5" />
    </svg>
  ),
  sheets: (
    <svg viewBox="0 0 14 14" fill="none">
      <rect x="2" y="1" width="10" height="12" rx="2" stroke="currentColor" strokeWidth="1.3" />
      <path d="M2 5h10M5 5v8" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.6" />
    </svg>
  ),
};

function getStepState(stepId, currentStep, appState) {
  if (appState === "done") return "done";
  if (stepId < currentStep) return "done";
  if (stepId === currentStep) return "active";
  return "pending";
}

export default function PipelineStatus({ currentStep, appState }) {
  return (
    <div className="card pipeline-card">
      <div className="card-header">
        <div className="card-icon">
          <svg viewBox="0 0 16 16" fill="none">
            <path d="M2 4h2v8H2zM7 4h2v8H7zM12 4h2v8h-2z" stroke="var(--accent)" strokeWidth="1.3" />
            <path d="M4 8h3M9 8h3" stroke="var(--accent)" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
        </div>
        <span className="card-title">Pipeline de Análise</span>
        {appState === "done" && (
          <div className="badge badge-success" style={{ marginLeft: "auto" }}>Concluído</div>
        )}
        {appState === "analyzing" && (
          <div className="badge badge-accent" style={{ marginLeft: "auto" }}>
            <div className="pulse-dot" />
            Processando
          </div>
        )}
      </div>

      <div className="card-body pipeline-body">
        {STEPS.map((step, idx) => {
          const state = getStepState(step.id, currentStep, appState);
          return (
            <div key={step.id} className="pipeline-step-wrap">
              <div className={`pipeline-step step-${state}`}>
                <div className="step-indicator">
                  {state === "done" ? (
                    <svg viewBox="0 0 14 14" fill="none" width="12" height="12">
                      <path d="M2 7l4 4 6-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  ) : state === "active" ? (
                    <div className="step-spinner" />
                  ) : (
                    <span className="step-num">{step.id}</span>
                  )}
                </div>

                <div className="step-icon">
                  {ICONS[step.icon]}
                </div>

                <div className="step-text">
                  <span className="step-label">{step.label}</span>
                  <span className="step-desc">{step.desc}</span>
                </div>
              </div>
              {idx < STEPS.length - 1 && (
                <div className={`pipeline-connector ${state === "done" ? "connector-done" : ""}`} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
