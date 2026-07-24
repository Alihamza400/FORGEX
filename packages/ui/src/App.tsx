import { Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import { ProtectedRoute } from "./components/shared/ProtectedRoute";
import { Dashboard } from "./pages/Dashboard";
import { Agents } from "./pages/Agents";
import { AgentDetail } from "./pages/AgentDetail";
import { Orchestrate } from "./pages/Orchestrate";
import { Logs } from "./pages/Logs";
import { Settings } from "./pages/Settings";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/*"
        element={
          <Layout>
            <Routes>
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <Dashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/agents"
                element={
                  <ProtectedRoute requiredPermission="agent:list">
                    <Agents />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/agents/:name"
                element={
                  <ProtectedRoute requiredPermission="agent:list">
                    <AgentDetail />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/orchestrate"
                element={
                  <ProtectedRoute requiredPermission="orchestrate:read">
                    <Orchestrate />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/logs"
                element={
                  <ProtectedRoute requiredPermission="log:read">
                    <Logs />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings"
                element={
                  <ProtectedRoute>
                    <Settings />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Layout>
        }
      />
    </Routes>
  );
}

export default App;
