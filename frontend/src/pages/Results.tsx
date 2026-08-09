import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { AccessFinding, PlanCost, RecommendationResponse } from "../types";

function money(n: number) {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function accessClass(score: number) {
  if (score >= 75) return "access-good";
  if (score >= 50) return "access-fair";
  return "access-poor";
}

function AccessScore({ score }: { score: number }) {
  return <span className={`access-score ${accessClass(score)}`}>{score}/100</span>;
}

export default function Results() {
  const [data, setData] = useState<RecommendationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [findingsFor, setFindingsFor] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get<RecommendationResponse>("/recommend");
      setData(data);
      setFindingsFor(data.recommended_plan_id);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not compute a recommendation");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (loading) return <p>Crunching the numbers...</p>;

  if (error) {
    return (
      <div className="card">
        <p className="error-text">{error}</p>
        <button onClick={load}>Try again</button>
      </div>
    );
  }

  if (!data || data.plans.length === 0) return <p>No plans configured.</p>;

  const recommended = data.plans.find((p) => p.plan_id === data.recommended_plan_id);
  const cheapest = [...data.plans].sort(
    (a, b) => a.expected_total_cost - b.expected_total_cost,
  )[0];
  const hasPathways = data.matched_pathways.length > 0;

  // The headline insight: the plan that looks cheapest is not the one we recommend.
  const costWinnerDiffers =
    hasPathways && cheapest.plan_id !== data.recommended_plan_id;

  const selectedPlan =
    data.plans.find((p) => p.plan_id === findingsFor) || recommended || data.plans[0];

  return (
    <div>
      <h1>Your recommendation</h1>
      <p className="muted">
        Estimated from your family's expected care usage on the{" "}
        <Link to="/family">Family</Link> page, any expenses on the{" "}
        <Link to="/expenses">Medical Expenses</Link> page, and — where a reported condition
        matches a modeled care pathway — the clinical care that condition typically requires.
      </p>

      {costWinnerDiffers && (
        <div className="alert-banner">
          <strong>The cheapest plan on paper is not the best plan for you.</strong>
          <p style={{ margin: "0.5rem 0 0" }}>
            {cheapest.plan_name} has the lowest premium-plus-copay cost (
            {money(cheapest.expected_total_cost)}), but it scores{" "}
            <AccessScore score={cheapest.access_score} /> on delivering the care your
            condition actually requires.
            {cheapest.access_gap_cost > 0 && (
              <>
                {" "}
                Once care it does not cover is included ({money(cheapest.access_gap_cost)} paid
                entirely out of pocket, none of it counting toward your out-of-pocket maximum),
                its real cost is <strong>{money(cheapest.access_adjusted_total_cost)}</strong>.
              </>
            )}
          </p>
        </div>
      )}

      {recommended && (
        <div
          className="card"
          style={{ background: "var(--recommended-bg)", borderColor: "#bfe0d3" }}
        >
          <span className="badge">Recommended</span>
          <h2 style={{ marginBottom: "0.25rem" }}>{recommended.plan_name}</h2>
          <p className="muted" style={{ marginTop: 0 }}>{recommended.plan_type}</p>
          <p>
            Estimated total annual cost:{" "}
            <strong>{money(recommended.access_adjusted_total_cost)}</strong> (
            {money(recommended.annual_premium)} premiums +{" "}
            {money(recommended.expected_out_of_pocket)} expected out-of-pocket
            {recommended.access_gap_cost > 0 &&
              ` + ${money(recommended.access_gap_cost)} not covered`}
            )
          </p>
          {hasPathways && (
            <p style={{ marginBottom: 0 }}>
              Care access for your conditions: <AccessScore score={recommended.access_score} />
            </p>
          )}
        </div>
      )}

      {hasPathways && (
        <div className="card">
          <h2>Care pathway for your conditions</h2>
          <p className="muted">
            Each condition below maps to a modeled year of care. Plans are then checked against
            it — visit caps, prior authorization, step therapy, specialist availability and drug
            coverage — to find barriers a cost calculator alone would miss.
          </p>
          {data.matched_pathways.map((p) => (
            <div className="pathway-card" key={p.id}>
              <div className="member-header">
                <strong>{p.name}</strong>
                <span className="tag">{p.category}</span>
              </div>
              <p className="muted" style={{ margin: "0.35rem 0 0.6rem" }}>{p.summary}</p>
              <table>
                <thead>
                  <tr>
                    <th>Projected care</th>
                    <th style={{ width: "5rem" }}>Per year</th>
                    <th style={{ width: "7rem" }}>Est. full cost</th>
                  </tr>
                </thead>
                <tbody>
                  {p.services.map((s) => (
                    <tr key={s.name}>
                      <td>
                        {s.name}
                        {s.clinical_note && (
                          <div className="muted" style={{ fontSize: "0.78rem" }}>
                            {s.clinical_note}
                          </div>
                        )}
                      </td>
                      <td>{s.annual_quantity}</td>
                      <td>{money(s.annual_quantity * s.unit_cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          <p className="muted" style={{ fontSize: "0.82rem" }}>
            Pathway care is added on top of the usage you entered manually on the Family page. If
            you already counted these visits there, lower those numbers to avoid double-counting.
          </p>
        </div>
      )}

      <div className="card">
        <h2>Why this plan?</h2>
        <div className="explanation-box">{data.explanation}</div>
      </div>

      {hasPathways && (
        <div className="card">
          <h2>Coverage barriers</h2>
          <p className="muted">
            Select a plan to see what would stand between you and the care above.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginBottom: "1rem" }}>
            {data.plans.map((p) => (
              <button
                key={p.plan_id}
                className={p.plan_id === findingsFor ? "" : "secondary"}
                onClick={() => setFindingsFor(p.plan_id)}
              >
                {p.plan_name}
              </button>
            ))}
          </div>

          <div className="member-header" style={{ marginBottom: "0.75rem" }}>
            <strong>{selectedPlan.plan_name}</strong>
            <AccessScore score={selectedPlan.access_score} />
          </div>

          {selectedPlan.access_findings.length === 0 ? (
            <p className="muted">
              No coverage barriers found — this plan covers the full modeled pathway.
            </p>
          ) : (
            selectedPlan.access_findings.map((f: AccessFinding, i: number) => (
              <div className={`finding finding-${f.severity}`} key={i}>
                <div className="severity-label">
                  {f.severity === "blocking" ? "Blocks care" : f.severity}
                  {f.uncovered_cost > 0 && ` · ${money(f.uncovered_cost)} out of pocket`}
                </div>
                <div style={{ fontWeight: 600, margin: "0.15rem 0" }}>{f.service_name}</div>
                <div style={{ fontSize: "0.9rem" }}>{f.message}</div>
              </div>
            ))
          )}
        </div>
      )}

      <div className="card" style={{ overflowX: "auto" }}>
        <h2>Compare all plans</h2>
        <table className="plan-table">
          <thead>
            <tr>
              <th></th>
              {data.plans.map((p) => (
                <th
                  key={p.plan_id}
                  className={`plan-col ${p.plan_id === data.recommended_plan_id ? "recommended-col" : ""}`}
                >
                  {p.plan_name}
                  <div className="muted" style={{ fontWeight: 400 }}>{p.plan_type}</div>
                  {p.plan_id === data.recommended_plan_id && (
                    <div className="badge" style={{ marginTop: "0.25rem" }}>Recommended</div>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <Row label="Annual premium" plans={data.plans} recommendedId={data.recommended_plan_id} field="annual_premium" />
            <Row label="Expected out-of-pocket" plans={data.plans} recommendedId={data.recommended_plan_id} field="expected_out_of_pocket" />
            <Row label="Cost if all care were covered" plans={data.plans} recommendedId={data.recommended_plan_id} field="expected_total_cost" />
            {hasPathways && (
              <>
                <Row
                  label="Care this plan does not cover"
                  plans={data.plans}
                  recommendedId={data.recommended_plan_id}
                  field="access_gap_cost"
                />
                <Row
                  label="True total annual cost"
                  plans={data.plans}
                  recommendedId={data.recommended_plan_id}
                  field="access_adjusted_total_cost"
                  bold
                />
                <tr>
                  <td>Care access score</td>
                  {data.plans.map((p) => (
                    <td
                      key={p.plan_id}
                      className={`plan-col ${p.plan_id === data.recommended_plan_id ? "recommended-col" : ""}`}
                    >
                      <AccessScore score={p.access_score} />
                      {p.has_blocking_barrier && (
                        <div style={{ fontSize: "0.72rem", color: "#b3261e", fontWeight: 700 }}>
                          BLOCKS CARE
                        </div>
                      )}
                    </td>
                  ))}
                </tr>
              </>
            )}
            <Row label="Best case (light usage)" plans={data.plans} recommendedId={data.recommended_plan_id} field="best_case_total_cost" />
            <Row label="Worst case (major medical event)" plans={data.plans} recommendedId={data.recommended_plan_id} field="worst_case_total_cost" />
            <tr>
              <td>Referral required?</td>
              {data.plans.map((p) => (
                <td key={p.plan_id} className={`plan-col ${p.plan_id === data.recommended_plan_id ? "recommended-col" : ""}`}>
                  {p.requires_referral ? "Yes" : "No"}
                </td>
              ))}
            </tr>
            <tr>
              <td>Out-of-network coverage?</td>
              {data.plans.map((p) => (
                <td key={p.plan_id} className={`plan-col ${p.plan_id === data.recommended_plan_id ? "recommended-col" : ""}`}>
                  {p.out_of_network_coverage ? "Yes" : "No"}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Plan details</h2>
        {data.plans.map((p) => (
          <div key={p.plan_id} style={{ marginBottom: "1rem" }}>
            <strong>{p.plan_name}</strong> ({p.plan_type})
            <p className="muted" style={{ marginTop: "0.25rem" }}>{p.notes}</p>
          </div>
        ))}
      </div>

      <p className="disclaimer">
        Estimates only. Costs use national-average unit prices, not your insurer's contracted
        rates. Care pathways are illustrative models of typical utilization — they are not
        clinical guidance, not patient-specific, and not a substitute for your clinician's
        judgment. Confirm plan details with your benefits team before enrolling.
      </p>
    </div>
  );
}

function Row({
  label,
  plans,
  recommendedId,
  field,
  bold,
}: {
  label: string;
  plans: PlanCost[];
  recommendedId: string;
  field: keyof PlanCost;
  bold?: boolean;
}) {
  return (
    <tr>
      <td style={bold ? { fontWeight: 700 } : undefined}>{label}</td>
      {plans.map((p) => (
        <td
          key={p.plan_id}
          className={`plan-col ${p.plan_id === recommendedId ? "recommended-col" : ""}`}
          style={bold ? { fontWeight: 700 } : undefined}
        >
          {money(p[field] as number)}
        </td>
      ))}
    </tr>
  );
}
