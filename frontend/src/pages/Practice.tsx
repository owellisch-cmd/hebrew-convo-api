import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import LineChart from "../components/LineChart";
import type {
  PayerInput,
  PracticeConfig,
  PracticeTemplate,
  ProviderInput,
  SavedPractice,
  SensitivityRow,
  SimulationResult,
  StaffInput,
} from "../types";

// Validated (light surface, CVD-safe) pair for the two-series chart.
const COLOR_IN = "#008a6e";
const COLOR_OUT = "#c2600f";

function money(n: number) {
  const sign = n < 0 ? "-" : "";
  return `${sign}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function moneyShort(n: number) {
  const a = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (a >= 1_000_000) return `${sign}$${(a / 1_000_000).toFixed(a >= 10_000_000 ? 0 : 1)}M`;
  if (a >= 1_000) return `${sign}$${Math.round(a / 1_000)}k`;
  return `${sign}$${Math.round(a)}`;
}

function num(n: number, digits = 0) {
  return n.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function detailOf(err: any, fallback: string): string {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d[0]?.msg) {
    const where = (d[0].loc || []).slice(1).join(" › ");
    return `${String(d[0].msg).replace(/^Value error, /, "")}${where ? ` (${where})` : ""}`;
  }
  return fallback;
}

/** Controlled number input that tolerates an empty box while typing. */
function NumField({
  label,
  value,
  onChange,
  step = 1,
  hint,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
  hint?: string;
}) {
  return (
    <div>
      <label title={hint}>{label}</label>
      <input
        type="number"
        step={step}
        min={0}
        value={Number.isFinite(value) ? value : ""}
        onChange={(e) => onChange(e.target.value === "" ? NaN : Number(e.target.value))}
      />
    </div>
  );
}

function Section({
  title,
  children,
  open = false,
  aside,
}: {
  title: string;
  children: React.ReactNode;
  open?: boolean;
  aside?: React.ReactNode;
}) {
  return (
    <details className="builder-section" open={open}>
      <summary>
        <span>{title}</span>
        {aside}
      </summary>
      <div className="builder-body">{children}</div>
    </details>
  );
}

function hasBlank(value: unknown): boolean {
  if (typeof value === "number") return !Number.isFinite(value);
  if (Array.isArray(value)) return value.some(hasBlank);
  if (value && typeof value === "object") return Object.values(value).some(hasBlank);
  return false;
}

export default function Practice() {
  const [templates, setTemplates] = useState<PracticeTemplate[]>([]);
  const [saved, setSaved] = useState<SavedPractice[]>([]);
  const [config, setConfig] = useState<PracticeConfig | null>(null);
  const [savedId, setSavedId] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [simError, setSimError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const requestSeq = useRef(0);

  useEffect(() => {
    (async () => {
      try {
        const [t, s] = await Promise.all([
          api.get<PracticeTemplate[]>("/practice/templates"),
          api.get<SavedPractice[]>("/practice/saved"),
        ]);
        setTemplates(t.data);
        setSaved(s.data);
        if (s.data.length > 0) {
          setConfig(s.data[0].config);
          setSavedId(s.data[0].id);
        } else if (t.data.length > 0) {
          setConfig(t.data[0].config);
        }
      } catch (err) {
        setLoadError(detailOf(err, "Could not load the practice builder"));
      }
    })();
  }, []);

  const payerTotal = config ? config.payer_mix.reduce((a, p) => a + (p.share_pct || 0), 0) : 0;
  const payerOk = Math.abs(payerTotal - 100) <= 0.5;
  const blank = config ? hasBlank(config) : false;

  // Re-simulate shortly after each edit. Stale responses are dropped so a slow
  // request can never overwrite the result for a newer design.
  useEffect(() => {
    if (!config) return;
    if (!payerOk) {
      setSimError(`Payer mix must add up to 100% (currently ${num(payerTotal, 1)}%).`);
      return;
    }
    if (blank) {
      setSimError("Fill in every field to run the simulation.");
      return;
    }
    const seq = ++requestSeq.current;
    const timer = window.setTimeout(async () => {
      setRunning(true);
      try {
        const { data } = await api.post<SimulationResult>("/practice/simulate", config);
        if (seq === requestSeq.current) {
          setResult(data);
          setSimError(null);
        }
      } catch (err) {
        if (seq === requestSeq.current) setSimError(detailOf(err, "Simulation failed"));
      } finally {
        if (seq === requestSeq.current) setRunning(false);
      }
    }, 350);
    return () => window.clearTimeout(timer);
  }, [config, payerOk, payerTotal, blank]);

  function edit(next: PracticeConfig) {
    setConfig(next);
    setDirty(true);
    setSaveMsg(null);
  }

  function startFromTemplate(id: string) {
    const t = templates.find((x) => x.id === id);
    if (!t) return;
    if (dirty && !window.confirm("Discard unsaved changes and start from this template?")) return;
    setConfig(structuredClone(t.config));
    setSavedId(null);
    setDirty(false);
    setSaveMsg(null);
  }

  function openSaved(id: number) {
    const p = saved.find((x) => x.id === id);
    if (!p) return;
    if (dirty && !window.confirm("Discard unsaved changes and open this design?")) return;
    setConfig(p.config);
    setSavedId(p.id);
    setDirty(false);
    setSaveMsg(null);
  }

  async function save(asNew: boolean) {
    if (!config) return;
    try {
      const body = { name: config.name, config };
      const { data } =
        savedId != null && !asNew
          ? await api.put<SavedPractice>(`/practice/saved/${savedId}`, body)
          : await api.post<SavedPractice>("/practice/saved", body);
      setSaved((prev) => [data, ...prev.filter((p) => p.id !== data.id)]);
      setSavedId(data.id);
      setDirty(false);
      setSaveMsg("Saved");
    } catch (err) {
      setSaveMsg(detailOf(err, "Could not save"));
    }
  }

  async function remove() {
    if (savedId == null) return;
    if (!window.confirm("Delete this saved design?")) return;
    try {
      await api.delete(`/practice/saved/${savedId}`);
      setSaved((prev) => prev.filter((p) => p.id !== savedId));
      setSavedId(null);
      setDirty(true);
      setSaveMsg("Deleted — the design is still open here, unsaved.");
    } catch (err) {
      setSaveMsg(detailOf(err, "Could not delete"));
    }
  }

  if (loadError) {
    return (
      <div className="card">
        <p className="error-text">{loadError}</p>
      </div>
    );
  }
  if (!config) return <p>Loading practice builder...</p>;

  const c = config;
  const setGroup = <K extends "demand" | "revenue" | "overhead" | "startup">(
    group: K,
    field: keyof PracticeConfig[K],
    value: number | string,
  ) => edit({ ...c, [group]: { ...c[group], [field]: value } });

  const setRow = <K extends "providers" | "staff" | "payer_mix">(
    list: K,
    index: number,
    patch: Partial<PracticeConfig[K][number]>,
  ) =>
    edit({
      ...c,
      [list]: (c[list] as PracticeConfig[K][number][]).map((row, i) =>
        i === index ? { ...row, ...patch } : row,
      ),
    });

  const removeRow = (list: "providers" | "staff" | "payer_mix", index: number) =>
    edit({ ...c, [list]: (c[list] as unknown[]).filter((_, i) => i !== index) });

  const startingCash =
    c.startup.owner_equity +
    c.startup.loan_amount -
    c.startup.buildout_and_equipment -
    c.startup.pre_opening_expenses;

  return (
    <div className="practice-page">
      <h1 style={{ marginBottom: "0.25rem" }}>Practice builder &amp; simulator</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        Design an outpatient practice — providers, staff, rooms, payer mix, overhead and financing
        — and watch its first years play out month by month. Every change re-runs the simulation.
      </p>

      <div className="card toolbar">
        <div>
          <label>Start from a specialty template</label>
          <select value="" onChange={(e) => startFromTemplate(e.target.value)}>
            <option value="" disabled>
              Choose a template…
            </option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label>Your saved designs</label>
          <select
            value={savedId ?? ""}
            onChange={(e) => openSaved(Number(e.target.value))}
            disabled={saved.length === 0}
          >
            <option value="" disabled>
              {saved.length === 0 ? "None saved yet" : "Open a saved design…"}
            </option>
            {saved.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label>Design name</label>
          <input value={c.name} onChange={(e) => edit({ ...c, name: e.target.value })} />
        </div>
        <div className="toolbar-actions">
          <button onClick={() => save(false)} disabled={!c.name.trim()}>
            {savedId != null ? "Save" : "Save design"}
          </button>
          {savedId != null && (
            <>
              <button className="secondary" onClick={() => save(true)}>
                Save as copy
              </button>
              <button className="danger" onClick={remove}>
                Delete
              </button>
            </>
          )}
          <span className="muted toolbar-status">
            {saveMsg ?? (dirty ? "Unsaved changes" : savedId != null ? "Saved" : "")}
          </span>
        </div>
      </div>

      <div className="sim-layout">
        <div className="builder">
          <Section title="Space & schedule" open>
            <div className="form-grid tight">
              <NumField
                label="Months to simulate"
                value={c.months}
                onChange={(v) => edit({ ...c, months: v })}
              />
              <NumField
                label="Open days / week"
                value={c.open_days_per_week}
                step={0.5}
                onChange={(v) => edit({ ...c, open_days_per_week: v })}
              />
              <NumField
                label="Exam rooms"
                value={c.exam_rooms}
                onChange={(v) => edit({ ...c, exam_rooms: v })}
              />
              <NumField
                label="Visits / room / day"
                value={c.visits_per_room_per_day}
                hint="How many visits one room can turn over in a clinic day"
                onChange={(v) => edit({ ...c, visits_per_room_per_day: v })}
              />
            </div>
          </Section>

          <Section
            title="Providers"
            open
            aside={
              <span className="muted">
                {c.providers.reduce((a, p) => a + (p.count || 0), 0)} total
              </span>
            }
          >
            {c.providers.map((p, i) => (
              <RowCard key={i} onRemove={c.providers.length > 1 ? () => removeRow("providers", i) : undefined}>
                <div className="span-2">
                  <label>Role</label>
                  <input value={p.role} onChange={(e) => setRow("providers", i, { role: e.target.value })} />
                </div>
                <NumField label="Count" value={p.count} onChange={(v) => setRow("providers", i, { count: v })} />
                <NumField
                  label="Salary / yr"
                  value={p.annual_salary}
                  step={1000}
                  onChange={(v) => setRow("providers", i, { annual_salary: v })}
                />
                <NumField
                  label="Clinic days / wk"
                  value={p.clinic_days_per_week}
                  step={0.5}
                  onChange={(v) => setRow("providers", i, { clinic_days_per_week: v })}
                />
                <NumField
                  label="Visits / day"
                  value={p.visits_per_day}
                  onChange={(v) => setRow("providers", i, { visits_per_day: v })}
                />
                <NumField
                  label="Starts month"
                  value={p.start_month}
                  onChange={(v) => setRow("providers", i, { start_month: v })}
                />
              </RowCard>
            ))}
            <button
              className="secondary btn-sm"
              onClick={() =>
                edit({
                  ...c,
                  providers: [
                    ...c.providers,
                    {
                      role: "Nurse practitioner",
                      count: 1,
                      annual_salary: 125000,
                      clinic_days_per_week: 4.5,
                      visits_per_day: 16,
                      start_month: 1,
                    } satisfies ProviderInput,
                  ],
                })
              }
            >
              + Add provider
            </button>
          </Section>

          <Section title="Support staff">
            <p className="field-note">
              Roles containing “bill” or “coder” count as billing staff when billing is in-house.
            </p>
            {c.staff.map((s, i) => (
              <RowCard key={i} onRemove={() => removeRow("staff", i)}>
                <div className="span-2">
                  <label>Role</label>
                  <input value={s.role} onChange={(e) => setRow("staff", i, { role: e.target.value })} />
                </div>
                <NumField label="Count" value={s.count} onChange={(v) => setRow("staff", i, { count: v })} />
                <NumField
                  label="Salary / yr"
                  value={s.annual_salary}
                  step={1000}
                  onChange={(v) => setRow("staff", i, { annual_salary: v })}
                />
                <NumField
                  label="Starts month"
                  value={s.start_month}
                  onChange={(v) => setRow("staff", i, { start_month: v })}
                />
              </RowCard>
            ))}
            <button
              className="secondary btn-sm"
              onClick={() =>
                edit({
                  ...c,
                  staff: [
                    ...c.staff,
                    { role: "Medical assistant", count: 1, annual_salary: 42000, start_month: 1 } satisfies StaffInput,
                  ],
                })
              }
            >
              + Add staff
            </button>
            <div className="form-grid tight" style={{ marginTop: "0.75rem" }}>
              <NumField
                label="Benefits & payroll tax load %"
                value={c.benefits_load_pct}
                onChange={(v) => edit({ ...c, benefits_load_pct: v })}
              />
            </div>
          </Section>

          <Section title="Patient demand">
            <div className="form-grid tight">
              <NumField
                label="Patients on day one"
                value={c.demand.starting_panel}
                hint="Patients who follow providers from a previous practice"
                onChange={(v) => setGroup("demand", "starting_panel", v)}
              />
              <NumField
                label="New patients / month"
                value={c.demand.new_patients_per_month}
                hint="At full marketing reach, after the ramp"
                onChange={(v) => setGroup("demand", "new_patients_per_month", v)}
              />
              <NumField
                label="Ramp-up months"
                value={c.demand.ramp_months}
                onChange={(v) => setGroup("demand", "ramp_months", v)}
              />
              <NumField
                label="Visits / patient / yr"
                value={c.demand.visits_per_patient_per_year}
                step={0.1}
                onChange={(v) => setGroup("demand", "visits_per_patient_per_year", v)}
              />
              <NumField
                label="Patient attrition % / yr"
                value={c.demand.annual_attrition_pct}
                onChange={(v) => setGroup("demand", "annual_attrition_pct", v)}
              />
              <NumField
                label="No-show %"
                value={c.demand.no_show_pct}
                onChange={(v) => setGroup("demand", "no_show_pct", v)}
              />
            </div>
          </Section>

          <Section title="Revenue & billing">
            <div className="form-grid tight">
              <NumField
                label="Medicare allowed / visit"
                value={c.revenue.medicare_allowed_per_visit}
                hint="Blended E/M, procedures and ancillaries per visit, at Medicare rates"
                onChange={(v) => setGroup("revenue", "medicare_allowed_per_visit", v)}
              />
              <div>
                <label>Billing</label>
                <select
                  value={c.revenue.billing_mode}
                  onChange={(e) => setGroup("revenue", "billing_mode", e.target.value)}
                >
                  <option value="in_house">In-house staff</option>
                  <option value="outsourced">Outsourced (% of collections)</option>
                </select>
              </div>
              {c.revenue.billing_mode === "outsourced" ? (
                <NumField
                  label="Billing fee % of collections"
                  value={c.revenue.outsourced_fee_pct}
                  step={0.5}
                  onChange={(v) => setGroup("revenue", "outsourced_fee_pct", v)}
                />
              ) : (
                <NumField
                  label="Claims / biller / month"
                  value={c.revenue.claims_per_biller_per_month}
                  step={100}
                  onChange={(v) => setGroup("revenue", "claims_per_biller_per_month", v)}
                />
              )}
              <NumField
                label="Denials recovered %"
                value={c.revenue.denial_recovery_pct}
                onChange={(v) => setGroup("revenue", "denial_recovery_pct", v)}
              />
            </div>
          </Section>

          <Section
            title="Payer mix"
            aside={
              <span className={payerOk ? "muted" : "error-text"} style={{ margin: 0 }}>
                {num(payerTotal, 1)}%
              </span>
            }
          >
            {c.payer_mix.map((p, i) => (
              <RowCard key={i} onRemove={c.payer_mix.length > 1 ? () => removeRow("payer_mix", i) : undefined}>
                <div className="span-2">
                  <label>Payer</label>
                  <input value={p.payer} onChange={(e) => setRow("payer_mix", i, { payer: e.target.value })} />
                </div>
                <NumField label="Share %" value={p.share_pct} onChange={(v) => setRow("payer_mix", i, { share_pct: v })} />
                <NumField
                  label="Rate % of Medicare"
                  value={p.rate_pct_of_medicare}
                  onChange={(v) => setRow("payer_mix", i, { rate_pct_of_medicare: v })}
                />
                <NumField label="Denial %" value={p.denial_pct} onChange={(v) => setRow("payer_mix", i, { denial_pct: v })} />
                <NumField
                  label="Days to pay"
                  value={p.days_to_pay}
                  onChange={(v) => setRow("payer_mix", i, { days_to_pay: v })}
                />
              </RowCard>
            ))}
            <button
              className="secondary btn-sm"
              onClick={() =>
                edit({
                  ...c,
                  payer_mix: [
                    ...c.payer_mix,
                    {
                      payer: "New payer",
                      share_pct: 0,
                      rate_pct_of_medicare: 100,
                      denial_pct: 8,
                      days_to_pay: 35,
                    } satisfies PayerInput,
                  ],
                })
              }
            >
              + Add payer
            </button>
          </Section>

          <Section title="Overhead">
            <div className="form-grid tight">
              <NumField label="Rent / month" value={c.overhead.rent_per_month} step={500}
                onChange={(v) => setGroup("overhead", "rent_per_month", v)} />
              <NumField label="EHR & software / provider / mo" value={c.overhead.software_per_provider_per_month} step={50}
                onChange={(v) => setGroup("overhead", "software_per_provider_per_month", v)} />
              <NumField label="Malpractice / provider / yr" value={c.overhead.malpractice_per_provider_per_year} step={500}
                onChange={(v) => setGroup("overhead", "malpractice_per_provider_per_year", v)} />
              <NumField label="Supplies / visit" value={c.overhead.supplies_per_visit}
                onChange={(v) => setGroup("overhead", "supplies_per_visit", v)} />
              <NumField label="Marketing / month" value={c.overhead.marketing_per_month} step={500}
                onChange={(v) => setGroup("overhead", "marketing_per_month", v)} />
              <NumField label="Other fixed / month" value={c.overhead.other_fixed_per_month} step={500}
                hint="Utilities, insurance, IT, cleaning, accounting, legal…"
                onChange={(v) => setGroup("overhead", "other_fixed_per_month", v)} />
            </div>
          </Section>

          <Section
            title="Startup & financing"
            aside={
              <span className={startingCash < 0 ? "error-text" : "muted"} style={{ margin: 0 }}>
                {moneyShort(startingCash)} opening cash
              </span>
            }
          >
            <div className="form-grid tight">
              <NumField label="Build-out & equipment" value={c.startup.buildout_and_equipment} step={10000}
                onChange={(v) => setGroup("startup", "buildout_and_equipment", v)} />
              <NumField label="Pre-opening expenses" value={c.startup.pre_opening_expenses} step={5000}
                hint="Credentialing, recruiting, deposits, pre-opening payroll"
                onChange={(v) => setGroup("startup", "pre_opening_expenses", v)} />
              <NumField label="Owner equity" value={c.startup.owner_equity} step={10000}
                onChange={(v) => setGroup("startup", "owner_equity", v)} />
              <NumField label="Loan amount" value={c.startup.loan_amount} step={10000}
                onChange={(v) => setGroup("startup", "loan_amount", v)} />
              <NumField label="Loan rate %" value={c.startup.loan_annual_rate_pct} step={0.25}
                onChange={(v) => setGroup("startup", "loan_annual_rate_pct", v)} />
              <NumField label="Loan term (months)" value={c.startup.loan_term_months}
                onChange={(v) => setGroup("startup", "loan_term_months", v)} />
            </div>
          </Section>
        </div>

        <div className="results-pane">
          {simError && <div className="alert-banner">{simError}</div>}
          {!result && !simError && <p>Simulating…</p>}
          {result && (
            <div style={{ opacity: running || simError ? 0.55 : 1, transition: "opacity 0.15s" }}>
              <Results result={result} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function RowCard({ children, onRemove }: { children: React.ReactNode; onRemove?: () => void }) {
  return (
    <div className="row-card">
      <div className="row-grid">{children}</div>
      {onRemove && (
        <button className="list-remove row-remove" onClick={onRemove} aria-label="Remove row">
          ×
        </button>
      )}
    </div>
  );
}

const BOTTLENECK_LABEL = {
  demand: "Patient demand",
  providers: "Provider time",
  rooms: "Exam rooms",
};

function Results({ result }: { result: SimulationResult }) {
  const s = result.summary;
  const m = result.months;
  const cashSeries = useMemo(
    () => [{ name: "Cash balance", color: COLOR_IN, values: m.map((r) => r.cash_balance) }],
    [m],
  );
  const flowSeries = useMemo(
    () => [
      { name: "Collections", color: COLOR_IN, values: m.map((r) => r.collections) },
      { name: "Operating expenses", color: COLOR_OUT, values: m.map((r) => r.total_expenses) },
    ],
    [m],
  );

  return (
    <>
      <div className="kpi-grid">
        <Kpi
          label="Operating break-even"
          value={s.operating_breakeven_month ? `Month ${s.operating_breakeven_month}` : "Not reached"}
          sub="Collections cover costs from here on"
          status={s.operating_breakeven_month ? (s.operating_breakeven_month <= 18 ? "good" : "warn") : "bad"}
        />
        <Kpi
          label="Lowest cash"
          value={moneyShort(s.lowest_cash)}
          sub={s.lowest_cash_month ? `Month ${s.lowest_cash_month}` : "At opening"}
          status={s.lowest_cash < 0 ? "bad" : s.lowest_cash < s.starting_cash * 0.15 ? "warn" : "good"}
        />
        <Kpi
          label="Steady-state margin"
          value={`${num(s.steady_state_operating_margin_pct)}%`}
          sub={`${moneyShort(s.steady_state_collections_per_month)}/mo collections`}
          status={s.steady_state_operating_margin_pct >= 15 ? "good" : s.steady_state_operating_margin_pct >= 0 ? "warn" : "bad"}
        />
        <Kpi
          label="Final-year operating income"
          value={moneyShort(s.final_year_operating_income)}
          sub={`Ending cash ${moneyShort(s.ending_cash)}`}
        />
        <Kpi
          label="Visits / month"
          value={num(s.steady_state_visits_per_month)}
          sub={`${num(s.steady_state_utilization_pct)}% of slots booked`}
        />
        <Kpi
          label="Constraint"
          value={BOTTLENECK_LABEL[s.bottleneck]}
          sub={`${money(s.net_collection_per_visit)} net / visit`}
          status={s.bottleneck === "demand" ? undefined : "warn"}
        />
      </div>

      <div className="card">
        <h3 className="chart-title">Cash balance</h3>
        <p className="muted chart-sub">
          Opening cash {money(s.starting_cash)} after build-out. Payers pay weeks after the visit,
          so the trough usually comes after the schedule fills.
        </p>
        <LineChart series={cashSeries} format={moneyShort} label="Cash balance by month" />
      </div>

      <div className="card">
        <h3 className="chart-title">Collections vs. operating expenses</h3>
        <p className="muted chart-sub">Monthly, before loan payments.</p>
        <LineChart series={flowSeries} format={moneyShort} label="Monthly collections and operating expenses" />
      </div>

      <div className="card">
        <h3 className="chart-title">What the simulation found</h3>
        {result.insights.length === 0 && <p className="muted">No issues flagged.</p>}
        {result.insights.map((f, i) => (
          <div className={`finding finding-${f.severity}`} key={i}>
            <span className="severity-label">{f.severity === "good" ? "looks good" : f.severity}</span>
            <div>
              <strong>{f.title}</strong>
            </div>
            <div className="muted" style={{ fontSize: "0.9rem" }}>
              {f.detail}
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h3 className="chart-title">What moves final-year operating income</h3>
        <p className="muted chart-sub">
          Each input swung on its own, everything else held at your design. Base:{" "}
          {money(s.final_year_operating_income)}.
        </p>
        <Tornado rows={result.sensitivity} base={s.final_year_operating_income} />
      </div>

      <div className="card">
        <h3 className="chart-title">By year</h3>
        <div className="table-scroll">
          <table className="plan-table num-table">
            <thead>
              <tr>
                <th>Year</th>
                <th>Visits</th>
                <th>Collections</th>
                <th>Expenses</th>
                <th>Operating income</th>
                <th>Margin</th>
                <th>Net cash flow</th>
              </tr>
            </thead>
            <tbody>
              {result.years.map((y) => (
                <tr key={y.year}>
                  <td>{y.year}</td>
                  <td>{num(y.visits)}</td>
                  <td>{money(y.collections)}</td>
                  <td>{money(y.expenses)}</td>
                  <td>{money(y.operating_income)}</td>
                  <td>{num(y.operating_margin_pct)}%</td>
                  <td>{money(y.net_cash_flow)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3 className="chart-title">By payer (whole simulation)</h3>
        <div className="table-scroll">
          <table className="plan-table num-table">
            <thead>
              <tr>
                <th>Payer</th>
                <th>Share</th>
                <th>Net / visit</th>
                <th>Visits</th>
                <th>Net revenue</th>
                <th>Lost to denials</th>
              </tr>
            </thead>
            <tbody>
              {result.payers.map((p) => (
                <tr key={p.payer}>
                  <td>{p.payer}</td>
                  <td>{num(p.share_pct)}%</td>
                  <td>{money(p.net_per_visit)}</td>
                  <td>{num(p.visits)}</td>
                  <td>{money(p.collections)}</td>
                  <td>{money(p.lost_to_denials)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="field-note">Net revenue is what those visits eventually pay, including any that land after the last simulated month.</p>
      </div>

      <details className="card month-details">
        <summary>
          <strong>Month-by-month table</strong>
        </summary>
        <div className="table-scroll">
          <table className="plan-table num-table">
            <thead>
              <tr>
                <th>Mo</th>
                <th>Patients</th>
                <th>New</th>
                <th>Turned away</th>
                <th>Visits</th>
                <th>Booked</th>
                <th>Collections</th>
                <th>Expenses</th>
                <th>Loan</th>
                <th>Net cash</th>
                <th>Cash</th>
                <th>A/R days</th>
              </tr>
            </thead>
            <tbody>
              {m.map((r) => (
                <tr key={r.month}>
                  <td>{r.month}</td>
                  <td>{num(r.active_patients)}</td>
                  <td>{num(r.new_patients)}</td>
                  <td>{num(r.turned_away)}</td>
                  <td>{num(r.completed_visits)}</td>
                  <td>{num(r.utilization_pct)}%</td>
                  <td>{money(r.collections)}</td>
                  <td>{money(r.total_expenses)}</td>
                  <td>{money(r.debt_service)}</td>
                  <td>{money(r.net_cash_flow)}</td>
                  <td>{money(r.cash_balance)}</td>
                  <td>{num(r.days_in_ar)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <p className="disclaimer">
        A planning model, not a pro forma you can take to a lender as-is. Template numbers are
        illustrative — replace salaries, rent, reimbursement and demand with local quotes, your
        actual payer contracts and a market study. Seasonality, provider productivity ramp-up,
        taxes, owner draws and facility/ancillary revenue are not modeled.
      </p>
    </>
  );
}

function Kpi({
  label,
  value,
  sub,
  status,
}: {
  label: string;
  value: string;
  sub: string;
  status?: "good" | "warn" | "bad";
}) {
  const icon = status === "good" ? "✓" : status === "warn" ? "!" : status === "bad" ? "✕" : null;
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">
        {icon && (
          <span className={`kpi-status kpi-${status}`} aria-label={status}>
            {icon}
          </span>
        )}
        {value}
      </div>
      <div className="kpi-sub">{sub}</div>
    </div>
  );
}

/** Horizontal range bars around the base result: worse-than-base in orange, better in green. */
function Tornado({ rows, base }: { rows: SensitivityRow[]; base: number }) {
  const values = rows.flatMap((r) => [r.low_value, r.high_value]).concat(base);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  const pct = (v: number) => ((v - lo) / span) * 100;
  const basePct = pct(base);

  return (
    <div className="tornado">
      {rows.map((r) => {
        const worst = Math.min(r.low_value, r.high_value);
        const best = Math.max(r.low_value, r.high_value);
        const worstLabel = r.low_value <= r.high_value ? r.low_label : r.high_label;
        const bestLabel = r.low_value <= r.high_value ? r.high_label : r.low_label;
        return (
          <div className="tornado-row" key={r.driver}>
            <div className="tornado-name">{r.driver}</div>
            <div className="tornado-track">
              <div className="tornado-base" style={{ left: `${basePct}%` }} />
              {worst < base && (
                <div
                  className="tornado-bar"
                  title={`${r.driver} ${worstLabel}: ${money(worst)}`}
                  style={{ left: `${pct(worst)}%`, width: `${basePct - pct(worst)}%`, background: COLOR_OUT }}
                />
              )}
              {best > base && (
                <div
                  className="tornado-bar"
                  title={`${r.driver} ${bestLabel}: ${money(best)}`}
                  style={{ left: `${basePct}%`, width: `${pct(best) - basePct}%`, background: COLOR_IN }}
                />
              )}
            </div>
            <div className="tornado-values">
              <span>
                {worstLabel}: {moneyShort(worst)}
              </span>
              <span>
                {bestLabel}: {moneyShort(best)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
