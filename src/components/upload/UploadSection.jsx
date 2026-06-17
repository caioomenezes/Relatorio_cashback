import { useState, useRef } from "react";
import "./UploadSection.css";

export default function UploadSection({ onFileAccepted, fileInfo, appState, onAnalyze }) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef();

  const isAnalyzing = appState === "analyzing";
  const isDone = appState === "done";

  const handleFile = (file) => {
    setError(null);
    if (!file) return;
    if (!file.name.endsWith(".csv")) {
      setError("Apenas arquivos .csv são aceitos.");
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setError("Arquivo muito grande. Máximo: 50 MB.");
      return;
    }
    onFileAccepted({
      name: file.name,
      size: file.size,
      lastModified: file.lastModified,
      raw: file,
    });
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    handleFile(e.dataTransfer.files[0]);
  };

  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = () => setIsDragging(false);

  const formatBytes = (bytes) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const formatDate = (ts) =>
    new Date(ts).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });

  return (
    <div className="card upload-card">
      <div className="card-header">
        <div className="card-icon">
          <svg viewBox="0 0 16 16" fill="none">
            <path d="M2 11v2a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-2M8 9V2M5 5l3-3 3 3" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <span className="card-title">Dados do Experimento</span>
      </div>

      <div className="card-body">
        {/* DROP ZONE */}
        {!fileInfo ? (
          <div
            className={`drop-zone ${isDragging ? "dragging" : ""} ${error ? "drop-error" : ""}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".csv"
              className="file-input-hidden"
              onChange={(e) => handleFile(e.target.files[0])}
            />
            <div className="drop-icon">
              <svg viewBox="0 0 48 48" fill="none">
                <rect x="6" y="10" width="36" height="30" rx="4" stroke="var(--accent)" strokeWidth="1.5" />
                <path d="M6 18h36" stroke="var(--accent)" strokeWidth="1.5" />
                <path d="M16 26h16M16 32h10" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" opacity="0.4" />
                <path d="M31 7l3 3-3 3M31 10h-6" stroke="var(--success)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <p className="drop-main">Arraste seu arquivo CSV aqui</p>
            <p className="drop-sub">ou <span className="drop-link">clique para selecionar</span></p>
            <p className="drop-hint">Máx. 50 MB · UTF-8 ou Latin-1</p>

            {error && (
              <div className="drop-error-msg">
                <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                  <circle cx="8" cy="8" r="6" stroke="var(--danger)" strokeWidth="1.5" />
                  <path d="M8 5v3.5M8 11h.01" stroke="var(--danger)" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
                {error}
              </div>
            )}
          </div>
        ) : (
          /* FILE INFO CARD */
          <div className="file-info-block">
            <div className="file-info-header">
              <div className="file-icon">
                <svg viewBox="0 0 32 32" fill="none">
                  <rect x="4" y="2" width="18" height="26" rx="3" fill="var(--accent-dim)" stroke="var(--accent)" strokeWidth="1.2" />
                  <rect x="22" y="8" width="6" height="18" rx="2" fill="var(--success-dim)" stroke="var(--success)" strokeWidth="1" />
                  <path d="M8 10h10M8 14h10M8 18h6" stroke="var(--accent)" strokeWidth="1.2" strokeLinecap="round" opacity="0.6" />
                </svg>
              </div>
              <div className="file-details">
                <span className="file-name">{fileInfo.name}</span>
                <span className="file-meta">
                  {formatBytes(fileInfo.size)} · {formatDate(fileInfo.lastModified)}
                </span>
              </div>
              <div className="badge badge-success">
                <svg viewBox="0 0 10 10" fill="none" width="8" height="8">
                  <circle cx="5" cy="5" r="4" fill="var(--success)" />
                </svg>
                Pronto
              </div>
            </div>

            {/* Metadata rows */}
            <div className="file-meta-grid">
              <MetaRow label="Arquivo" value={fileInfo.name} mono />
              <MetaRow label="Tamanho" value={formatBytes(fileInfo.size)} mono />
              <MetaRow label="Última modificação" value={formatDate(fileInfo.lastModified)} />
              <MetaRow label="Status" value="Validado" success />
            </div>

            {/* Expected columns hint */}
            <div className="schema-hint">
              <p className="schema-title">Colunas esperadas</p>
              <div className="schema-cols">
                {["grupo_ab", "usuario_id", "valor_cashback", "conversao", "data"].map((col) => (
                  <span key={col} className="schema-col mono">{col}</span>
                ))}
              </div>
            </div>

            {!isAnalyzing && !isDone && (
              <button
                className="btn btn-ghost file-change-btn"
                onClick={() => { onFileAccepted(null); }}
                style={{ marginTop: "4px", fontSize: "0.8rem", height: "34px" }}
              >
                Trocar arquivo
              </button>
            )}
          </div>
        )}

        {/* ANALYZE BUTTON */}
        {fileInfo && (
          <button
            className="btn btn-primary btn-full btn-lg analyze-btn"
            onClick={onAnalyze}
            disabled={isAnalyzing || isDone}
          >
            {isAnalyzing ? (
              <>
                <div className="spinner" />
                Analisando...
              </>
            ) : isDone ? (
              <>
                <svg viewBox="0 0 16 16" fill="none" width="15" height="15">
                  <path d="M3 8l4 4 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Análise Concluída
              </>
            ) : (
              <>
                <svg viewBox="0 0 16 16" fill="none" width="15" height="15">
                  <path d="M3 14V8M8 14V4M13 14V10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  <path d="M13 4l2 2-2 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.7" />
                </svg>
                Analisar Experimento
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
}

function MetaRow({ label, value, mono, success }) {
  return (
    <div className="meta-row">
      <span className="meta-label">{label}</span>
      <span className={`meta-value ${mono ? "mono" : ""} ${success ? "meta-success" : ""}`}>
        {value}
      </span>
    </div>
  );
}
