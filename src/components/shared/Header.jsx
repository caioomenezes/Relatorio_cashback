import "./Header.css";

export default function Header({ onReset, hasData }) {
  return (
    <header className="header">
      <div className="header-inner">
        {/* Logo / Brand */}
        <div className="header-brand">
          <div className="brand-logo">
            <svg viewBox="0 0 28 28" fill="none">
              <rect width="28" height="28" rx="7" fill="var(--accent)" opacity="0.15" />
              <path d="M7 20L11 12L15 17L18 10L21 14" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="21" cy="9" r="2" fill="var(--success)" />
            </svg>
          </div>
          <div className="brand-text">
            <span className="brand-name">A/B Cashback</span>
            <span className="brand-suffix">Analyzer</span>
          </div>
          <div className="badge badge-accent header-badge">AI-Native</div>
        </div>

        {/* Center nav info */}
        <nav className="header-nav">
          <NavItem label="Análise" active />
          <NavItem label="Histórico" />
          <NavItem label="Configurações" />
        </nav>

        {/* Right actions */}
        <div className="header-actions">
          {hasData && (
            <button className="btn btn-ghost header-reset-btn" onClick={onReset}>
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <path d="M2 8a6 6 0 1 0 1.2-3.6M2 4v3.5H5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Novo Experimento
            </button>
          )}
          <div className="header-divider" />
          <div className="header-version">
            <span className="mono" style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>v1.0</span>
          </div>
        </div>
      </div>

      {/* Bottom accent line */}
      <div className="header-line" />
    </header>
  );
}

function NavItem({ label, active }) {
  return (
    <button className={`nav-item ${active ? "nav-item-active" : ""}`}>
      {label}
    </button>
  );
}
