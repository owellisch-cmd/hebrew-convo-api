import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { DocumentOut, Expense, ExpenseSummary } from "../types";

const CATEGORY_LABELS: Record<string, string> = {
  primary_care: "Primary care",
  specialist: "Specialist",
  er: "Emergency room",
  hospital: "Hospital / inpatient",
  prescription: "Prescriptions",
  other: "Other",
};

export default function Expenses() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [manualExpenses, setManualExpenses] = useState<Expense[]>([]);
  const [summary, setSummary] = useState<ExpenseSummary[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [manualForm, setManualForm] = useState({ category: "primary_care", amount: "", description: "" });
  const fileInput = useRef<HTMLInputElement>(null);

  async function loadAll() {
    const [docsRes, expensesRes, summaryRes] = await Promise.all([
      api.get<DocumentOut[]>("/expenses/documents"),
      api.get<Expense[]>("/expenses"),
      api.get<ExpenseSummary[]>("/expenses/summary"),
    ]);
    setDocuments(docsRes.data);
    setManualExpenses(expensesRes.data.filter((e) => !docsRes.data.some((d) => d.expenses.some((de) => de.id === e.id))));
    setSummary(summaryRes.data);
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function onUpload(e: FormEvent) {
    e.preventDefault();
    setUploadError(null);
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    setUploading(true);
    try {
      await api.post("/expenses/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      if (fileInput.current) fileInput.current.value = "";
      await loadAll();
    } catch (err: any) {
      setUploadError(err?.response?.data?.detail || "Could not process that file");
    } finally {
      setUploading(false);
    }
  }

  async function deleteDocument(id: number) {
    if (!confirm("Remove this uploaded file and the expenses extracted from it?")) return;
    await api.delete(`/expenses/documents/${id}`);
    await loadAll();
  }

  async function addManualExpense(e: FormEvent) {
    e.preventDefault();
    if (!manualForm.amount) return;
    await api.post("/expenses/manual", {
      category: manualForm.category,
      amount: Number(manualForm.amount),
      description: manualForm.description || null,
    });
    setManualForm({ category: "primary_care", amount: "", description: "" });
    await loadAll();
  }

  async function deleteManualExpense(id: number) {
    await api.delete(`/expenses/manual/${id}`);
    await loadAll();
  }

  const totalSpend = summary.reduce((sum, s) => sum + s.total, 0);

  return (
    <div>
      <h1>Past medical expenses</h1>
      <p className="muted">
        Upload a claims or expense export from your current insurer (CSV or PDF) so past spending
        can inform the cost estimate — or just add rough totals manually. This is parsed
        automatically with simple keyword matching, so double-check the categories it picked.
        <br />
        <strong>Note:</strong> this reads and stores what you upload in this app's own database —
        it does not connect to your insurer or provider's systems.
      </p>

      <div className="card">
        <h2>Upload a file</h2>
        <form onSubmit={onUpload}>
          <input type="file" accept=".csv,.pdf" ref={fileInput} />
          <div style={{ height: "0.75rem" }} />
          <button type="submit" disabled={uploading}>
            {uploading ? "Processing..." : "Upload and parse"}
          </button>
          {uploadError && <div className="error-text">{uploadError}</div>}
        </form>
      </div>

      {documents.length > 0 && (
        <div className="card">
          <h2>Uploaded files</h2>
          {documents.map((doc) => (
            <div key={doc.id} style={{ marginBottom: "1rem" }}>
              <div className="member-header">
                <strong>{doc.filename}</strong>
                <button className="danger" onClick={() => deleteDocument(doc.id)}>
                  Remove
                </button>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Category</th>
                    <th>Amount</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {doc.expenses.map((exp) => (
                    <tr key={exp.id}>
                      <td>{CATEGORY_LABELS[exp.category] || exp.category}</td>
                      <td>${exp.amount.toLocaleString()}</td>
                      <td className="muted">{exp.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h2>Add an expense manually</h2>
        <form onSubmit={addManualExpense} className="inline-form">
          <div>
            <label>Category</label>
            <select
              value={manualForm.category}
              onChange={(e) => setManualForm({ ...manualForm, category: e.target.value })}
            >
              {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Amount ($)</label>
            <input
              type="number"
              min={0}
              step="0.01"
              value={manualForm.amount}
              onChange={(e) => setManualForm({ ...manualForm, amount: e.target.value })}
              required
            />
          </div>
          <div style={{ flex: 1 }}>
            <label>Description (optional)</label>
            <input
              value={manualForm.description}
              onChange={(e) => setManualForm({ ...manualForm, description: e.target.value })}
            />
          </div>
          <button type="submit">Add</button>
        </form>

        {manualExpenses.length > 0 && (
          <table style={{ marginTop: "1rem" }}>
            <thead>
              <tr>
                <th>Category</th>
                <th>Amount</th>
                <th>Description</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {manualExpenses.map((exp) => (
                <tr key={exp.id}>
                  <td>{CATEGORY_LABELS[exp.category] || exp.category}</td>
                  <td>${exp.amount.toLocaleString()}</td>
                  <td className="muted">{exp.description}</td>
                  <td>
                    <button className="list-remove" onClick={() => deleteManualExpense(exp.id)}>
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {summary.length > 0 && (
        <div className="card">
          <h2>Total by category</h2>
          <table>
            <tbody>
              {summary.map((s) => (
                <tr key={s.category}>
                  <td>{CATEGORY_LABELS[s.category] || s.category}</td>
                  <td>${s.total.toLocaleString()}</td>
                </tr>
              ))}
              <tr>
                <td>
                  <strong>Total</strong>
                </td>
                <td>
                  <strong>${totalSpend.toLocaleString()}</strong>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
