import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { RecommendationResponse } from "../types";

export default function Results() {
  const [data, setData] = useState<RecommendationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get<RecommendationResponse>("/recommend");
      setData(data);
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

  if (!data) return null;

  if (data.plans.length === 0) {
    return <p>No plans configured.</p>;
  }

  const recommended = data.plans.find((p) => p.plan_id === data.recommended_plan_id);

  return (
    <div>
      <h1>Your recommendation</h1>
      <p className="muted">
        Estimated using your family's expected care usage from the{" "}
        <Link to="/family">Family</Link> page and any expenses you uploaded on the{" "}
        <Link to="/expenses">Medical Expenses</Link> page. Update either and come back for a fresh
        estimate.
      </p>

      {recommended && (
        <div className="card" style={{ background: "var(--recommended-bg)", borderColor: "#bfe0d3" }}>
          <span className="badge">Recommended</span>
          <h2 style={{ marginBottom: "0.25rem" }}>{recommended.plan_name}</h2>
          <p className="muted" style={{ marginTop: 0 }}>{recommended.plan_type}</p>
          <p>
            Estimated total annual cost: <strong>${recommended.expected_total_cost.toLocaleString()}</strong>{" "}
            (${recommended.annual_premium.toLocaleString()} in premiums + $
            {recommended.expected_out_of_pocket.toLocaleString()} expected out-of-pocket)
          </p>
        </div>
      )}

      <div className="card">
        <h2>Why this plan?</h2>
        <div className="explanation-box">{data.explanation}</div>
      </div>

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
                  <div className="muted" style={{ fontWeight: 400 }}>
                    {p.plan_type}
                  </div>
                  {p.plan_id === data.recommended_plan_id && (
                    <div className="badge" style={{ marginTop: "0.25rem" }}>
                      Recommended
                    </div>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <Row label="Annual premium" plans={data.plans} recommendedId={data.recommended_plan_id} field="annual_premium" money />
            <Row
              label="Expected out-of-pocket"
              plans={data.plans}
              recommendedId={data.recommended_plan_id}
              field="expected_out_of_pocket"
              money
            />
            <Row
              label="Expected total annual cost"
              plans={data.plans}
              recommendedId={data.recommended_plan_id}
              field="expected_total_cost"
              money
              bold
            />
            <Row
              label="Best case (light usage)"
              plans={data.plans}
              recommendedId={data.recommended_plan_id}
              field="best_case_total_cost"
              money
            />
            <Row
              label="Worst case (a major medical event)"
              plans={data.plans}
              recommendedId={data.recommended_plan_id}
              field="worst_case_total_cost"
              money
            />
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
            <p className="muted" style={{ marginTop: "0.25rem" }}>
              {p.notes}
            </p>
          </div>
        ))}
      </div>

      <p className="muted">
        These figures use national-average costs per visit/prescription, not your actual insurer's
        contracted rates — treat this as a planning estimate, and confirm exact numbers with your
        benefits team before enrolling.
      </p>
    </div>
  );
}

function Row({
  label,
  plans,
  recommendedId,
  field,
  money,
  bold,
}: {
  label: string;
  plans: RecommendationResponse["plans"];
  recommendedId: string;
  field: keyof RecommendationResponse["plans"][number];
  money?: boolean;
  bold?: boolean;
}) {
  return (
    <tr>
      <td style={bold ? { fontWeight: 700 } : undefined}>{label}</td>
      {plans.map((p) => {
        const value = p[field] as number;
        return (
          <td
            key={p.plan_id}
            className={`plan-col ${p.plan_id === recommendedId ? "recommended-col" : ""}`}
            style={bold ? { fontWeight: 700 } : undefined}
          >
            {money ? `$${value.toLocaleString()}` : value}
          </td>
        );
      })}
    </tr>
  );
}
