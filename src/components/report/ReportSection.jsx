import { useRef, useState, useMemo } from "react";
import "./ReportSection.css";

// ── ICONS ─────────────────────────────────────────────────────────────────
const ICONS = {
  summary: (
    <svg viewBox="0 0 16 16" fill="none">
      <rect x="2" y="2" width="12" height="12" rx="3" stroke="currentColor" strokeWidth="1.3" />
      <path d="M5 6h6M5 9h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  ),
  findings: (
    <svg viewBox="0 0 16 16" fill="none">
      <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.3" />
      <path d="M10.5 10.5l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M5.5 7h3M7 5.5v3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  ),
  recommendations: (
    <svg viewBox="0 0 16 16" fill="none">
      <path d="M8 2L9.5 6H14l-3.5 2.5 1.3 4L8 10l-3.8 2.5 1.3-4L2 6h4.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  ),
  risks: (
    <svg viewBox="0 0 16 16" fill="none">
      <path d="M8 2l6 12H2L8 2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M8 7v3M8 11.5h.01" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  ),
  glossary: (
    <svg viewBox="0 0 16 16" fill="none">
      <path d="M3 2.5h7.5L13 5v8.5H3V2.5z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M5.5 6.5h5M5.5 9h5M5.5 11.5h3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
    </svg>
  ),
};

// ── GLOSSÁRIO DE MÉTRICAS ───────────────────────────────────────────────
// Definições e fórmulas alinhadas com models/entities.py (GroupStats).
// Atenção: ROI aqui é net_revenue / cashback (diferente de outras versões
// do sistema que usam commission / cashback).
const METRIC_GLOSSARY = [
  {
    name: "GMV",
    formula: "Soma do volume de vendas geradas pelos usuários do grupo no período.",
    usage:
      "Mostra o volume de negócios movimentado por cada grupo. Sozinho não diz se o cashback " +
      "está sendo eficiente — precisa ser olhado junto com Comissão e Cashback.",
  },
  {
    name: "Comissão",
    formula: "Soma do valor de comissão recebido sobre as vendas do grupo.",
    usage:
      "É a receita bruta gerada pelas vendas, antes de descontar o custo do cashback pago. " +
      "Quanto maior, mais a operação do grupo está gerando de receita de origem.",
  },
  {
    name: "Cashback",
    formula: "Soma do valor de cashback pago aos usuários do grupo no período.",
    usage:
      "Representa o custo do incentivo dado ao usuário. Aqui, menor costuma ser melhor — " +
      "mede o quanto o programa está \"gastando\" para gerar a Comissão daquele grupo.",
  },
  {
    name: "Receita líquida",
    formula: "Comissão menos Cashback (commission − cashback).",
    usage:
      "É o resultado financeiro real do grupo depois de pagar o cashback. É a métrica mais " +
      "direta para saber se o grupo deu lucro ou prejuízo em termos absolutos (R$).",
  },
  {
    name: "ROI (Retorno sobre o Investimento)",
    formula: "Receita líquida dividida pelo Cashback pago (net_revenue ÷ cashback).",
    usage:
      "Mostra quanto de lucro líquido é gerado para cada R$ 1,00 investido em cashback. Um ROI " +
      "de 0,40, por exemplo, significa que cada real pago em cashback gerou R$ 0,40 de receita " +
      "líquida. É a métrica chave para comparar a eficiência do investimento entre os grupos.",
  },
  {
    name: "Margem",
    formula: "Receita líquida dividida pelo GMV (net_revenue ÷ gmv).",
    usage:
      "Indica que fração do volume de vendas do grupo sobrou como lucro líquido depois do " +
      "cashback. Ajuda a comparar a rentabilidade do grupo independente do seu tamanho.",
  },
  {
    name: "Ticket médio",
    formula: "GMV dividido pelo número de compradores do grupo (gmv ÷ buyers).",
    usage:
      "Mostra quanto, em média, cada comprador gastou. Útil para entender se o cashback está " +
      "incentivando compras maiores ou só mais compradores de ticket baixo.",
  },
  {
    name: "Cashback médio",
    formula: "Cashback total dividido pelo número de compradores do grupo (cashback ÷ buyers).",
    usage:
      "Indica quanto, em média, cada comprador recebeu de volta. Ajuda a entender se o custo " +
      "por comprador está dentro do esperado para o grupo.",
  },
  {
    name: "Comissão/comprador",
    formula: "Comissão total dividida pelo número de compradores do grupo (commission ÷ buyers).",
    usage:
      "Indica quanto de comissão, em média, cada comprador do grupo gerou. Ajuda a comparar a " +
      "qualidade das vendas entre grupos de tamanhos diferentes, sem que o grupo maior pareça " +
      "automaticamente \"melhor\" só por ter mais gente.",
  },
];

// ── REPORT CARD ───────────────────────────────────────────────────────────
function ReportCard({ section }) {
  const colorMap = {
    accent:  { bg: "var(--accent-dim)",  text: "var(--accent)",  border: "rgba(56,189,248,0.2)"  },
    success: { bg: "var(--success-dim)", text: "var(--success)", border: "rgba(16,185,129,0.2)"  },
    warning: { bg: "var(--warning-dim)", text: "var(--warning)", border: "rgba(245,158,11,0.2)"  },
    danger:  { bg: "var(--danger-dim)",  text: "var(--danger)",  border: "rgba(239,68,68,0.2)"   },
  };
  const colors = colorMap[section.color] || colorMap.accent;

  return (
    <div
      className="report-card"
      style={{
        "--card-accent": colors.text,
        "--card-accent-bg": colors.bg,
        "--card-accent-border": colors.border,
      }}
    >
      <div className="report-card-header">
        <div
          className="report-card-icon"
          style={{ background: colors.bg, color: colors.text, borderColor: colors.border }}
        >
          {ICONS[section.icon]}
        </div>
        <h3 className="report-card-title">{section.title}</h3>
      </div>

      {section.content && <p className="report-content">{section.content}</p>}

      {section.items && (
        <ul className="report-list">
          {section.items.map((item, i) => (
            <li key={i} className="report-list-item">
              <span className="list-marker" style={{ background: colors.text }} />
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── CARD: GLOSSÁRIO DE MÉTRICAS ────────────────────────────────────────
function MetricsGlossaryCard() {
  return (
    <div
      className="report-card"
      style={{
        "--card-accent":        "var(--accent)",
        "--card-accent-bg":     "var(--accent-dim)",
        "--card-accent-border": "rgba(56,189,248,0.2)",
        marginTop: 12,
      }}
    >
      <div className="report-card-header">
        <div
          className="report-card-icon"
          style={{ background: "var(--accent-dim)", color: "var(--accent)", borderColor: "rgba(56,189,248,0.2)" }}
        >
          {ICONS.glossary}
        </div>
        <h3 className="report-card-title">Glossário de Métricas</h3>
      </div>

      <ul className="report-list" style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {METRIC_GLOSSARY.map((m, i) => (
          <li
            key={i}
            style={{
              paddingBottom: 12,
              marginBottom: 12,
              borderBottom: i < METRIC_GLOSSARY.length - 1 ? "1px solid var(--border)" : "none",
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{m.name}</div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.55 }}>
              <strong>O que é:</strong> {m.formula}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.55, marginTop: 2 }}>
              <strong>Para que serve:</strong> {m.usage}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── EXPORTA PDF (jsPDF + html2canvas) ────────────────────────────────────
const PDF_LIGHT_THEME = {
  "--bg-base":        "#FFFFFF",
  "--bg-surface":     "#F8FAFC",
  "--bg-card":        "#FFFFFF",
  "--bg-card-hover":  "#F1F5F9",
  "--bg-input":       "#F8FAFC",
  "--border":         "#E2E8F0",
  "--border-light":   "#CBD5E1",
  "--accent":         "#0369A1",
  "--accent-dim":     "rgba(3, 105, 161, 0.08)",
  "--accent-glow":    "rgba(3, 105, 161, 0.15)",
  "--success":        "#047857",
  "--success-dim":    "rgba(4, 120, 87, 0.08)",
  "--warning":        "#B45309",
  "--warning-dim":    "rgba(180, 83, 9, 0.08)",
  "--danger":         "#B91C1C",
  "--danger-dim":     "rgba(185, 28, 28, 0.08)",
  "--text-primary":   "#000000",
  "--text-secondary": "#1E293B",
  "--text-muted":     "#52606D",
};

async function exportToPDF(targetRef) {
  const [{ default: jsPDF }, { default: html2canvas }] = await Promise.all([
    import("jspdf"),
    import("html2canvas"),
  ]);

  const element = targetRef.current;
  if (!element) return;

  const canvas = await html2canvas(element, {
    scale: 2,
    useCORS: true,
    backgroundColor: "#ffffff",
    logging: false,
    onclone: (clonedDoc) => {
      const root = clonedDoc.documentElement;
      Object.entries(PDF_LIGHT_THEME).forEach(([key, value]) => {
        root.style.setProperty(key, value);
      });
      clonedDoc.body.style.background = "#FFFFFF";
      clonedDoc.body.style.color = "#000000";
    },
  });

  const imgData = canvas.toDataURL("image/png");
  const pdf     = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const pageW   = pdf.internal.pageSize.getWidth();
  const pageH   = pdf.internal.pageSize.getHeight();
  const margin  = 10;
  const printW  = pageW - margin * 2;
  const printH  = (canvas.height * printW) / canvas.width;

  const genAt = new Date().toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
  pdf.setFontSize(9);
  pdf.setTextColor(120, 120, 140);
  pdf.text(`Relatório Executivo — ${genAt}`, margin, 7);
  pdf.setDrawColor(50, 50, 70);
  pdf.line(margin, 9, pageW - margin, 9);

  const contentTop = 12;

  if (printH + contentTop <= pageH - margin) {
    pdf.addImage(imgData, "PNG", margin, contentTop, printW, printH);
  } else {
    const pxPerMm   = canvas.width / printW;
    const sliceH_mm = pageH - contentTop - margin;
    const sliceH_px = sliceH_mm * pxPerMm;
    let   offsetY   = 0;
    let   page      = 0;

    while (offsetY < canvas.height) {
      if (page > 0) {
        pdf.addPage();
        pdf.setFontSize(9);
        pdf.setTextColor(120, 120, 140);
        pdf.text(`Relatório Executivo — ${genAt}`, margin, 7);
        pdf.line(margin, 9, pageW - margin, 9);
      }

      const sliceCanvas  = document.createElement("canvas");
      const actualSliceH = Math.min(sliceH_px, canvas.height - offsetY);
      sliceCanvas.width  = canvas.width;
      sliceCanvas.height = actualSliceH;
      sliceCanvas.getContext("2d").drawImage(canvas, 0, -offsetY);

      const slicePrintH = actualSliceH / pxPerMm;
      pdf.addImage(sliceCanvas.toDataURL("image/png"), "PNG", margin, contentTop, printW, slicePrintH);

      offsetY += sliceH_px;
      page++;
    }
  }

  const totalPages = pdf.internal.getNumberOfPages();
  for (let p = 1; p <= totalPages; p++) {
    pdf.setPage(p);
    pdf.setFontSize(8);
    pdf.setTextColor(100, 100, 120);
    pdf.text(`Página ${p} de ${totalPages}`, pageW / 2, pageH - 4, { align: "center" });
  }

  pdf.save(`relatorio-ab-${new Date().toISOString().slice(0, 10)}.pdf`);
}

// ── FORMATTERS ────────────────────────────────────────────────────────────
function formatMoney(n) {
  if (n == null || !Number.isFinite(n)) return "R$ 0,00";
  return `R$ ${Number(n).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatRatio(n) {
  if (n == null || !Number.isFinite(n)) return "0,00";
  return Number(n).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatPercent(n) {
  if (n == null || !Number.isFinite(n)) return "0%";
  return `${(n * 100).toFixed(1)}%`;
}

function fmtLift(fraction) {
  if (fraction == null || !Number.isFinite(fraction)) return "sem variação calculada";
  const pct  = fraction * 100;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

// ── RESUMO LOCAL ──────────────────────────────────────────────────────────
function buildLocalSummary(result) {
  const groups = result?.groups;
  if (!groups) return null;

  const groupNames = Object.keys(groups);
  if (groupNames.length < 2) return null;

  const controlName = result.control_group ?? groupNames[0];
  const control      = groups[controlName];
  if (!control) return null;

  const others = groupNames.filter((n) => n !== controlName);
  const lifts  = result.lifts ?? {};

  let text =
    `O grupo ${controlName} foi usado como controle, com ${control.buyers ?? 0} compradores ao longo de ${control.days ?? "?"} dias, ` +
    `GMV de ${formatMoney(control.gmv)}, receita líquida de ${formatMoney(control.net_revenue)}, ROI de ${formatRatio(control.roi)} e margem de ${formatPercent(control.margin)}. `;

  others.forEach((name) => {
    const g = groups[name] ?? {};
    const l = lifts[name]  ?? {};
    text +=
      `O grupo ${name} teve ${g.buyers ?? 0} compradores, GMV de ${formatMoney(g.gmv)} (${fmtLift(l.gmv)} vs. controle), ` +
      `receita líquida de ${formatMoney(g.net_revenue)} (${fmtLift(l.net_revenue)}) e ROI de ${formatRatio(g.roi)} (${fmtLift(l.roi)}). `;
  });

  if (result.recommended_group) {
    text += `O grupo recomendado é o ${result.recommended_group}`;
    text += result.recommendation_reason ? `: ${result.recommendation_reason}` : ".";
  }

  return text.trim();
}

function detectAnomalies(result) {
  const warnings = [];
  if (!result) return warnings;

  // 1. Avisos vindos do backend (validation.issues)
  const backendWarnings = result._backendWarnings ?? [];
  const SUPPRESS = new Set(["NO_USER_ID_VALIDATION"]);
  const BACKEND_LABELS = {
    MISSING_CASHBACK_COLUMN: "Coluna de cashback ausente no CSV; valores podem estar zerados ou estimados.",
  };
  backendWarnings.forEach((item) => {
    const code    = typeof item === "string" ? item : (item?.code ?? item?.type ?? item?.key ?? "");
    if (SUPPRESS.has(code)) return;
    const message = typeof item === "string" ? null : (item?.message ?? item?.description ?? item?.detail ?? null);
    const label   = BACKEND_LABELS[code] ?? message ?? (code ? `Aviso do backend: ${code}` : "Aviso do backend sem descrição.");
    warnings.push({ severity: "warning", label });
  });

  const groups = result?.groups ?? {};

  Object.entries(groups).forEach(([name, g]) => {
    const comm = g.commission ?? 0;
    const cash = g.cashback   ?? 0;

    // 2. Cashback idêntico à comissão — sinal de dado copiado/corrompido
    if (comm > 0 && Math.abs(comm - cash) < 0.01) {
      warnings.push({
        severity: "danger",
        label:
          `Grupo ${name}: cashback (${formatMoney(cash)}) é idêntico à comissão — ` +
          `possível erro de origem (coluna de cashback copiando comissão). ` +
          `Isso zera a receita líquida e o ROI desse grupo.`,
      });
    }

    // 3. Receita líquida negativa (cashback > comissão)
    if ((g.net_revenue ?? 0) < 0) {
      warnings.push({
        severity: "danger",
        label:
          `Grupo ${name}: receita líquida negativa (${formatMoney(g.net_revenue)}) — ` +
          `o cashback supera a comissão gerada.`,
      });
    }

    // 4. ROI zero com comissão positiva mas cashback ≠ comissão
    if (comm > 0 && (g.roi ?? 0) === 0 && Math.abs(comm - cash) >= 0.01) {
      warnings.push({
        severity: "warning",
        label:
          `Grupo ${name}: ROI igual a zero mesmo com comissão de ${formatMoney(comm)} — ` +
          `verifique o denominador do cálculo de ROI no backend.`,
      });
    }

    // 5. Conversão zerada com usuários cadastrados
    if ((g.total_users ?? 0) > 0 && (g.buyers ?? 0) === 0) {
      warnings.push({
        severity: "warning",
        label:
          `Grupo ${name}: nenhum comprador registrado (${g.total_users?.toLocaleString("pt-BR")} usuários) — ` +
          `taxa de conversão zerada.`,
      });
    }
  });

  // 6. Lifts extremos (> 200%)
  const lifts = result?.lifts ?? {};
  Object.entries(lifts).forEach(([groupName, l]) => {
    Object.entries(l).forEach(([metric, value]) => {
      if (value == null || !Number.isFinite(value)) return;
      if (Math.abs(value) > 2.0) {
        warnings.push({
          severity: "warning",
          label:
            `Lift de "${metric}" no grupo ${groupName} é ${fmtLift(value)} — ` +
            `valor extremo; confirme se os tamanhos de amostra são comparáveis.`,
        });
      }
    });
  });

  return warnings;
}

// ── MAIN COMPONENT ────────────────────────────────────────────────────────
export default function ReportSection({ result, loading, onAppend, sheetStatus, pdfTargetRef }) {
  const [pdfLoading, setPdfLoading] = useState(false);
  const sectionsRef                 = useRef(null);

  const localSummary = useMemo(() => buildLocalSummary(result), [result]);
  const anomalies    = useMemo(() => detectAnomalies(result),   [result]);
  const generatedAt  = useMemo(
    () => new Date().toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }),
    [result]
  );

  const handleExportPDF = async () => {
    if (pdfLoading) return;
    setPdfLoading(true);
    try {
      await exportToPDF(pdfTargetRef ?? sectionsRef);
    } catch (err) {
      console.error("Erro ao exportar PDF:", err);
      alert("Não foi possível gerar o PDF. Verifique o console para detalhes.");
    } finally {
      setPdfLoading(false);
    }
  };

  const isLoading = loading;

  const sheetBtnLabel =
    sheetStatus === "saving" ? "Salvando…"                :
    sheetStatus === "saved"  ? "✓ Salvo!"                 :
    sheetStatus === "error"  ? "✗ Erro — tentar novamente" :
    "Inserir na Planilha";

  return (
    <div className="report-wrap">

      {/* ── HEADER ──────────────────────────────────────────────────────── */}
      <div className="report-top">
        <div className="section-eyebrow">
          <div className="eyebrow-line-s" />
          <span>Relatório Executivo</span>
          <div className="eyebrow-line-s" />
        </div>

        {result && (
          <div className="report-meta">
            <span className="report-model">
              <svg viewBox="0 0 12 12" fill="none" width="10" height="10">
                <circle cx="6" cy="6" r="5" stroke="var(--accent)" strokeWidth="1.2" />
                <path d="M4 6l1.5 1.5L8 4" stroke="var(--accent)" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Resumo automático
            </span>
            <span className="report-time">{generatedAt}</span>

            {/* Badge de avisos no header — aparece quando há anomalias */}
            {anomalies.length > 0 && (
              <span
                title={`${anomalies.length} aviso(s) detectado(s) — veja o card abaixo`}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  fontSize: 11,
                  fontWeight: 600,
                  padding: "2px 8px",
                  borderRadius: 10,
                  background: anomalies.some(w => w.severity === "danger")
                    ? "var(--danger-dim)"
                    : "var(--warning-dim)",
                  color: anomalies.some(w => w.severity === "danger")
                    ? "var(--danger)"
                    : "var(--warning)",
                  border: `1px solid ${anomalies.some(w => w.severity === "danger")
                    ? "rgba(239,68,68,0.3)"
                    : "rgba(245,158,11,0.3)"}`,
                  cursor: "default",
                }}
              >
                {ICONS.risks}
                {anomalies.length} aviso{anomalies.length > 1 ? "s" : ""}
              </span>
            )}

            {/* Botão PDF */}
            <button
              className="btn btn-ghost export-btn"
              onClick={handleExportPDF}
              disabled={pdfLoading || isLoading}
              title="Exportar relatório como PDF"
            >
              {pdfLoading ? (
                <>
                  <svg viewBox="0 0 14 14" fill="none" width="12" height="12"
                    style={{ animation: "spin 0.8s linear infinite" }}>
                    <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.4" strokeDasharray="20 15" />
                  </svg>
                  Gerando…
                </>
              ) : (
                <>
                  <svg viewBox="0 0 14 14" fill="none" width="12" height="12">
                    <path d="M2 9v3h10V9M7 2v7M4 6l3 3 3-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Exportar PDF
                </>
              )}
            </button>

            <button
              className="btn btn-primary"
              style={{ marginLeft: 8 }}
              onClick={() => onAppend && onAppend()}
              disabled={isLoading || sheetStatus === "saving"}
            >
              <svg viewBox="0 0 14 14" fill="none" width="12" height="12" style={{ marginRight: 6 }}>
                <path d="M3 10h8M3 7h8M7 3v8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {sheetBtnLabel}
            </button>
          </div>
        )}
      </div>

      {/* ── CONTEÚDO ────────────────────────────────────────────────────── */}
      {isLoading && (
        <div className="report-skeleton">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton-section-block">
              <div className="skeleton" style={{ height: 20, width: "40%", borderRadius: 6 }} />
              <div className="skeleton" style={{ height: 14, borderRadius: 4, marginTop: 10 }} />
              <div className="skeleton" style={{ height: 14, borderRadius: 4, width: "85%", marginTop: 6 }} />
              <div className="skeleton" style={{ height: 14, borderRadius: 4, width: "70%", marginTop: 6 }} />
            </div>
          ))}
        </div>
      )}

      {!isLoading && localSummary && (
        <div className="report-sections" ref={sectionsRef}>

          {/* ── CARD: RESUMO DOS RESULTADOS ─────────────────────────────── */}
          <div
            className="report-card"
            style={{
              "--card-accent":        "var(--accent)",
              "--card-accent-bg":     "var(--accent-dim)",
              "--card-accent-border": "rgba(56,189,248,0.2)",
            }}
          >
            <div className="report-card-header">
              <div
                className="report-card-icon"
                style={{ background: "var(--accent-dim)", color: "var(--accent)", borderColor: "rgba(56,189,248,0.2)" }}
              >
                {ICONS.summary}
              </div>
              <h3 className="report-card-title">Resumo dos Resultados</h3>
            </div>
            <p className="report-content">{localSummary}</p>
          </div>

          {/* ── CARD: AVISOS DA ANÁLISE (só renderiza se houver anomalias) ── */}
          {anomalies.length > 0 && (
            <div
              className="report-card"
              style={{
                "--card-accent":        anomalies.some(w => w.severity === "danger") ? "var(--danger)"      : "var(--warning)",
                "--card-accent-bg":     anomalies.some(w => w.severity === "danger") ? "var(--danger-dim)"  : "var(--warning-dim)",
                "--card-accent-border": anomalies.some(w => w.severity === "danger") ? "rgba(239,68,68,0.2)" : "rgba(245,158,11,0.2)",
                marginTop: 12,
              }}
            >
              <div className="report-card-header">
                <div
                  className="report-card-icon"
                  style={{
                    background:  anomalies.some(w => w.severity === "danger") ? "var(--danger-dim)"   : "var(--warning-dim)",
                    color:       anomalies.some(w => w.severity === "danger") ? "var(--danger)"       : "var(--warning)",
                    borderColor: anomalies.some(w => w.severity === "danger") ? "rgba(239,68,68,0.2)" : "rgba(245,158,11,0.2)",
                  }}
                >
                  {ICONS.risks}
                </div>
                <h3 className="report-card-title">
                  Avisos da Análise
                  <span style={{
                    marginLeft: 8,
                    fontSize: 11,
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: 10,
                    background: anomalies.some(w => w.severity === "danger") ? "var(--danger-dim)"   : "var(--warning-dim)",
                    color:      anomalies.some(w => w.severity === "danger") ? "var(--danger)"       : "var(--warning)",
                    border: `1px solid ${anomalies.some(w => w.severity === "danger") ? "rgba(239,68,68,0.3)" : "rgba(245,158,11,0.3)"}`,
                    verticalAlign: "middle",
                  }}>
                    {anomalies.length}
                  </span>
                </h3>
              </div>

              <ul className="report-list">
                {anomalies.map((w, i) => (
                  <li key={i} className="report-list-item">
                    <span
                      className="list-marker"
                      style={{
                        background: w.severity === "danger" ? "var(--danger)" : "var(--warning)",
                        minWidth: 6,
                        height: 6,
                        borderRadius: "50%",
                        flexShrink: 0,
                        marginTop: 6,
                      }}
                    />
                    <span style={{
                      color: w.severity === "danger" ? "var(--danger)" : "inherit",
                      lineHeight: 1.55,
                    }}>
                      {w.label}
                    </span>
                  </li>
                ))}
              </ul>

              <p style={{
                fontSize: 11,
                color: "var(--text-muted)",
                marginTop: 12,
                paddingTop: 10,
                borderTop: "1px solid var(--border)",
                lineHeight: 1.5,
              }}>
                Esses avisos não bloqueiam a análise — servem para orientar a investigação da
                origem dos dados antes de tomar qualquer decisão acionável.
              </p>
            </div>
          )}

          {/* ── CARD: GLOSSÁRIO DE MÉTRICAS ─────────────────────────────── */}
          <MetricsGlossaryCard />

        </div>
      )}

      {/* Fallback: result existe mas não foi possível montar o resumo */}
      {!isLoading && result && !localSummary && (
        <div ref={sectionsRef}>
          <p style={{ color: "var(--text-muted)", fontSize: 13, padding: "12px 0" }}>
            Análise concluída, mas não há dados suficientes (são necessários ao menos 2 grupos) para montar o resumo.
          </p>
        </div>
      )}

      {!isLoading && !result && (
        <p style={{ color: "var(--text-muted)", fontSize: 13, padding: "12px 0" }}>
          Faça upload e análise de um CSV para gerar o relatório.
        </p>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}