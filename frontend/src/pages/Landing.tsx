import { Link } from "react-router-dom";

export default function Landing() {
  return (
    <div className="landing">
      <section className="hero">
        <span className="eyebrow">Benefits decision support</span>
        <h1>
          Stop guessing which health plan
          <br />
          is right for your family.
        </h1>
        <p className="hero-sub">
          PlanWise looks at what your family actually spends and the conditions you actually
          have, then models each plan against the care you'll really need — so open enrollment
          stops being a coin flip.
        </p>
        <div className="hero-actions">
          <Link to="/register" className="btn-primary">
            Get started
          </Link>
          <Link to="/login" className="btn-ghost">
            I already have an account
          </Link>
        </div>
      </section>

      <section className="differentiator">
        <h2>The cheapest plan is not always the cheapest plan</h2>
        <p>
          Most tools stop at premiums, deductibles and copays. That math misses the thing that
          actually drains a family with an ongoing condition: <strong>the care your plan won't
          cover.</strong>
        </p>
        <div className="compare-strip">
          <div className="compare-col">
            <div className="compare-label">What a typical calculator sees</div>
            <div className="compare-figure">$8,160</div>
            <div className="compare-note">Lowest premium plan. Looks like the obvious winner.</div>
          </div>
          <div className="compare-arrow">→</div>
          <div className="compare-col highlight">
            <div className="compare-label">What PlanWise sees</div>
            <div className="compare-figure">$15,960</div>
            <div className="compare-note">
              The migraine preventive isn't on that plan's formulary. That's $7,800 a year paid
              entirely out of pocket — and none of it counts toward the out-of-pocket maximum.
            </div>
          </div>
        </div>
        <p className="compare-caption">
          Same family, same plan. One number is a premium calculation; the other is what actually
          leaves your bank account.
        </p>
      </section>

      <section className="steps">
        <h2>How it works</h2>
        <div className="step-grid">
          <div className="step">
            <div className="step-num">1</div>
            <h3>Tell us about your family</h3>
            <p>
              Who needs coverage, their ongoing conditions and medications, and roughly how much
              care you expect this year.
            </p>
          </div>
          <div className="step">
            <div className="step-num">2</div>
            <h3>Add last year's costs</h3>
            <p>
              Upload a claims or expense export from your current insurer, or enter rough totals.
              Past spending grounds the projection.
            </p>
          </div>
          <div className="step">
            <div className="step-num">3</div>
            <h3>See what each plan really costs</h3>
            <p>
              Every plan is scored on total annual cost, downside risk in a bad year, and whether
              it can actually deliver the care your conditions require.
            </p>
          </div>
        </div>
      </section>

      <section className="clinical">
        <h2>Coverage barriers, not just price tags</h2>
        <p>
          When you report a condition, PlanWise maps it to a modeled care pathway — the services
          someone with that condition typically needs over a year — and checks every plan against
          it:
        </p>
        <ul className="barrier-list">
          <li>
            <strong>Visit caps.</strong> Your pathway calls for 24 physical therapy visits. The
            plan covers 20. Those last four are full price and don't count toward your
            out-of-pocket maximum.
          </li>
          <li>
            <strong>Formulary gaps.</strong> A drug that isn't covered is not a copay difference.
            It's the entire cost, all year.
          </li>
          <li>
            <strong>Step therapy catch-22s.</strong> A plan requires documented failure of
            physical therapy before approving the next step — while capping the physical therapy
            you'd need to document it.
          </li>
          <li>
            <strong>Thin specialist networks.</strong> A plan technically covers pain medicine.
            Whether anyone in-network is accepting patients within 50 miles is a different
            question.
          </li>
        </ul>
      </section>

      <section className="cta-band">
        <h2>Find out what your plan actually costs you</h2>
        <Link to="/register" className="btn-primary">
          Get started
        </Link>
      </section>

      <p className="disclaimer" style={{ textAlign: "center" }}>
        PlanWise produces planning estimates using national-average unit costs, not your
        insurer's contracted rates. Care pathways are illustrative models of typical utilization —
        they are not clinical guidance and not a substitute for your clinician's judgment. Confirm
        plan details with your benefits team before enrolling.
      </p>
    </div>
  );
}
