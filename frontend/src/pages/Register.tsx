import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const { data } = await api.post("/auth/register", {
        full_name: fullName,
        email,
        password,
      });
      await login(data.access_token);
      navigate("/family");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Registration failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page card">
      <h2>Create your account</h2>
      <form onSubmit={onSubmit}>
        <label>Full name</label>
        <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        <div style={{ height: "0.75rem" }} />
        <label>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <div style={{ height: "0.75rem" }} />
        <label>Password</label>
        <input
          type="password"
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <div className="error-text">{error}</div>}
        <div style={{ height: "1rem" }} />
        <button type="submit" disabled={submitting}>
          {submitting ? "Creating account..." : "Create account"}
        </button>
      </form>
      <p className="muted" style={{ marginTop: "1rem" }}>
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </div>
  );
}
