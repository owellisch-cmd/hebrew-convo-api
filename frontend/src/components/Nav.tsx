import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Nav() {
  const { user, logout } = useAuth();

  if (!user) return null;

  return (
    <nav className="nav">
      <NavLink to="/" className="brand">
        Health Insurance Advisor
      </NavLink>
      <div className="nav-links">
        <NavLink to="/family">Family</NavLink>
        <NavLink to="/expenses">Medical Expenses</NavLink>
        <NavLink to="/results">Recommendation</NavLink>
        <span className="muted">{user.full_name}</span>
        <button className="secondary" onClick={logout}>
          Log out
        </button>
      </div>
    </nav>
  );
}
