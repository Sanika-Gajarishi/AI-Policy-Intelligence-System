import { useState, useEffect } from "react";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import { getCurrentUser, isAuthenticated, logout } from "./services/auth";

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // 🔥 Always clear session and show login first on app start
  useEffect(() => {
    const initAuth = async () => {
      try {
        // Clear any existing session to always show login first
        localStorage.clear();
        setUser(null);
      } catch (error) {
        console.error("Auth error:", error);
        localStorage.clear();
      } finally {
        setLoading(false);
      }
    };

    initAuth();
  }, []);

  // 🔥 After login
  const handleLogin = (userData) => {
    setUser(userData);
    // Ensure the dashboard starts at the top so filters are visible after login
    try {
      // Small timeout to let the new view render before scrolling
      setTimeout(() => {
        window.scrollTo({ top: 0, behavior: "auto" });
      }, 50);
    } catch (e) {
      console.warn("Scroll to top failed:", e);
    }
  };

  // 🔥 Logout (backend + frontend)
  const handleLogout = async () => {
    try {
      await logout(); // call backend logout
    } catch (err) {
      console.error("Logout error:", err);
    } finally {
      localStorage.clear();
      setUser(null);
    }
  };

  // 🔄 Loading screen
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-100 to-blue-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Checking authentication...</p>
        </div>
      </div>
    );
  }

  // 🔐 Not logged in → show Login
  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  // ✅ Logged in → show Dashboard
  return <Dashboard user={user} onLogout={handleLogout} />;
}

export default App;