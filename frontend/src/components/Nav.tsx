import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Logo from "./Logo";

export default function Nav() {
  const { user, logout } = useAuth();

  return (
    <nav className="nav">
      <Link to={user ? "/family" : "/"} className="brand">
        <Logo />
        <span>
          Plan<span className="brand-accent">Wise</span>
        </span>
      </Link>

      {user ? (
        <div className="nav-links">
          <NavLink to="/family">Family</NavLink>
          <NavLink to="/expenses">Medical Expenses</NavLink>
          <NavLink to="/results">Recommendation</NavLink>
          <NavLink to="/practice">Practice Simulator</NavLink>
          <span className="muted">{user.full_name}</span>
          <button className="secondary" onClick={logout}>
            Log out
          </button>
        </div>
      ) : (
        <div className="nav-links">
          <NavLink to="/login">Log in</NavLink>
          <Link to="/register" className="btn-primary btn-sm">
            Get started
          </Link>
        </div>
      )}
    </nav>
  );
}
