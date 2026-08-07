import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { FamilyMember } from "../types";

const emptyMember = {
  name: "",
  relation: "self",
  age: undefined as number | undefined,
  expected_primary_care_visits: 0,
  expected_specialist_visits: 0,
  expected_er_visits: 0,
  expected_generic_prescriptions: 0,
  expected_brand_prescriptions: 0,
  planned_procedure_cost: 0,
};

export default function Family() {
  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [newMember, setNewMember] = useState(emptyMember);
  const [showAddForm, setShowAddForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadMembers() {
    const { data } = await api.get<FamilyMember[]>("/family");
    setMembers(data);
    setLoading(false);
  }

  useEffect(() => {
    loadMembers();
  }, []);

  async function addMember(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/family", newMember);
      setNewMember(emptyMember);
      setShowAddForm(false);
      await loadMembers();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not add family member");
    }
  }

  async function deleteMember(id: number) {
    if (!confirm("Remove this family member and all their data?")) return;
    await api.delete(`/family/${id}`);
    await loadMembers();
  }

  async function updateUsage(member: FamilyMember, field: string, value: number) {
    const updated = { ...member, [field]: value };
    setMembers((prev) => prev.map((m) => (m.id === member.id ? updated : m)));
    await api.put(`/family/${member.id}`, {
      name: updated.name,
      relation: updated.relation,
      age: updated.age,
      expected_primary_care_visits: updated.expected_primary_care_visits,
      expected_specialist_visits: updated.expected_specialist_visits,
      expected_er_visits: updated.expected_er_visits,
      expected_generic_prescriptions: updated.expected_generic_prescriptions,
      expected_brand_prescriptions: updated.expected_brand_prescriptions,
      planned_procedure_cost: updated.planned_procedure_cost,
    });
  }

  async function addCondition(memberId: number, name: string) {
    if (!name.trim()) return;
    await api.post(`/family/${memberId}/conditions`, { name, ongoing: true });
    await loadMembers();
  }

  async function removeCondition(memberId: number, conditionId: number) {
    await api.delete(`/family/${memberId}/conditions/${conditionId}`);
    await loadMembers();
  }

  async function addMedication(memberId: number, name: string, isGeneric: boolean) {
    if (!name.trim()) return;
    await api.post(`/family/${memberId}/medications`, {
      name,
      is_generic: isGeneric,
      fills_per_year: 12,
    });
    await loadMembers();
  }

  async function removeMedication(memberId: number, medicationId: number) {
    await api.delete(`/family/${memberId}/medications/${medicationId}`);
    await loadMembers();
  }

  if (loading) return <p>Loading...</p>;

  return (
    <div>
      <h1>Your family</h1>
      <p className="muted">
        Add each person who needs coverage, their medical conditions, and roughly how much care
        they expect to use this year. This drives the cost estimate on the Recommendation page —
        the more accurate these numbers, the better the estimate. Nothing here is shared outside
        this app.
      </p>

      {members.map((member) => (
        <MemberCard
          key={member.id}
          member={member}
          onDelete={() => deleteMember(member.id)}
          onUsageChange={(field, value) => updateUsage(member, field, value)}
          onAddCondition={(name) => addCondition(member.id, name)}
          onRemoveCondition={(id) => removeCondition(member.id, id)}
          onAddMedication={(name, generic) => addMedication(member.id, name, generic)}
          onRemoveMedication={(id) => removeMedication(member.id, id)}
        />
      ))}

      {showAddForm ? (
        <div className="card">
          <h2>Add family member</h2>
          <form onSubmit={addMember}>
            <div className="form-grid">
              <div>
                <label>Name</label>
                <input
                  value={newMember.name}
                  onChange={(e) => setNewMember({ ...newMember, name: e.target.value })}
                  required
                />
              </div>
              <div>
                <label>Relation</label>
                <select
                  value={newMember.relation}
                  onChange={(e) => setNewMember({ ...newMember, relation: e.target.value })}
                >
                  <option value="self">Self (employee)</option>
                  <option value="spouse">Spouse / Partner</option>
                  <option value="child">Child</option>
                  <option value="other">Other dependent</option>
                </select>
              </div>
              <div>
                <label>Age</label>
                <input
                  type="number"
                  min={0}
                  value={newMember.age ?? ""}
                  onChange={(e) =>
                    setNewMember({ ...newMember, age: e.target.value ? Number(e.target.value) : undefined })
                  }
                />
              </div>
            </div>
            {error && <div className="error-text">{error}</div>}
            <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem" }}>
              <button type="submit">Save family member</button>
              <button type="button" className="secondary" onClick={() => setShowAddForm(false)}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      ) : (
        <button onClick={() => setShowAddForm(true)}>+ Add family member</button>
      )}
    </div>
  );
}

function MemberCard({
  member,
  onDelete,
  onUsageChange,
  onAddCondition,
  onRemoveCondition,
  onAddMedication,
  onRemoveMedication,
}: {
  member: FamilyMember;
  onDelete: () => void;
  onUsageChange: (field: string, value: number) => void;
  onAddCondition: (name: string) => void;
  onRemoveCondition: (id: number) => void;
  onAddMedication: (name: string, generic: boolean) => void;
  onRemoveMedication: (id: number) => void;
}) {
  const [conditionInput, setConditionInput] = useState("");
  const [medicationInput, setMedicationInput] = useState("");
  const [medicationGeneric, setMedicationGeneric] = useState(true);

  return (
    <div className="member-card">
      <div className="member-header">
        <div>
          <strong>{member.name}</strong>{" "}
          <span className="muted">
            ({member.relation}
            {member.age != null ? `, age ${member.age}` : ""})
          </span>
        </div>
        <button className="danger" onClick={onDelete}>
          Remove
        </button>
      </div>

      <div style={{ marginTop: "0.75rem" }}>
        <div className="section-title">Medical conditions</div>
        {member.conditions.map((c) => (
          <span className="tag" key={c.id}>
            {c.name}{" "}
            <button className="list-remove" onClick={() => onRemoveCondition(c.id)}>
              ×
            </button>
          </span>
        ))}
        <div className="inline-form" style={{ marginTop: "0.5rem" }}>
          <input
            placeholder="e.g. Type 2 diabetes"
            value={conditionInput}
            onChange={(e) => setConditionInput(e.target.value)}
          />
          <button
            type="button"
            className="secondary"
            onClick={() => {
              onAddCondition(conditionInput);
              setConditionInput("");
            }}
          >
            Add
          </button>
        </div>
      </div>

      <div style={{ marginTop: "0.75rem" }}>
        <div className="section-title">Ongoing medications</div>
        {member.medications.map((m) => (
          <span className="tag" key={m.id}>
            {m.name} ({m.is_generic ? "generic" : "brand"}){" "}
            <button className="list-remove" onClick={() => onRemoveMedication(m.id)}>
              ×
            </button>
          </span>
        ))}
        <div className="inline-form" style={{ marginTop: "0.5rem" }}>
          <input
            placeholder="e.g. Metformin"
            value={medicationInput}
            onChange={(e) => setMedicationInput(e.target.value)}
          />
          <label style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
            <input
              type="checkbox"
              checked={medicationGeneric}
              onChange={(e) => setMedicationGeneric(e.target.checked)}
            />
            Generic
          </label>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              onAddMedication(medicationInput, medicationGeneric);
              setMedicationInput("");
            }}
          >
            Add
          </button>
        </div>
      </div>

      <div style={{ marginTop: "1rem" }}>
        <div className="section-title">Expected care this year</div>
        <div className="form-grid">
          <UsageField
            label="Primary care visits"
            value={member.expected_primary_care_visits}
            onChange={(v) => onUsageChange("expected_primary_care_visits", v)}
          />
          <UsageField
            label="Specialist visits"
            value={member.expected_specialist_visits}
            onChange={(v) => onUsageChange("expected_specialist_visits", v)}
          />
          <UsageField
            label="ER visits"
            value={member.expected_er_visits}
            onChange={(v) => onUsageChange("expected_er_visits", v)}
          />
          <UsageField
            label="Generic prescriptions / yr"
            value={member.expected_generic_prescriptions}
            onChange={(v) => onUsageChange("expected_generic_prescriptions", v)}
          />
          <UsageField
            label="Brand prescriptions / yr"
            value={member.expected_brand_prescriptions}
            onChange={(v) => onUsageChange("expected_brand_prescriptions", v)}
          />
          <UsageField
            label="Planned procedure cost ($)"
            value={member.planned_procedure_cost}
            onChange={(v) => onUsageChange("planned_procedure_cost", v)}
            step={100}
          />
        </div>
      </div>
    </div>
  );
}

function UsageField({
  label,
  value,
  onChange,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  step?: number;
}) {
  return (
    <div>
      <label>{label}</label>
      <input
        type="number"
        min={0}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}
