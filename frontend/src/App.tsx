import { Navigate, Route, Routes } from "react-router-dom";
import Nav from "./components/Nav";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Family from "./pages/Family";
import Expenses from "./pages/Expenses";
import Results from "./pages/Results";

function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="app-shell">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const { loading } = useAuth();

  if (loading) {
    return <div className="app-shell">Loading...</div>;
  }

  return (
    <>
      <Nav />
      <div className="app-shell">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/family"
            element={
              <RequireAuth>
                <Family />
              </RequireAuth>
            }
          />
          <Route
            path="/expenses"
            element={
              <RequireAuth>
                <Expenses />
              </RequireAuth>
            }
          />
          <Route
            path="/results"
            element={
              <RequireAuth>
                <Results />
              </RequireAuth>
            }
          />
          <Route path="/" element={<Navigate to="/family" replace />} />
        </Routes>
      </div>
    </>
  );
}
