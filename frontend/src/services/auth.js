// Base API URL
const API_URL = process.env.REACT_APP_API_URL;

// -------------------------
// 🔐 CHECK AUTH
// -------------------------
export const isAuthenticated = () => {
  const token = localStorage.getItem("token");
  return !!token;
};


// -------------------------
// 👤 GET CURRENT USER
// -------------------------
export const getCurrentUser = () => {
  try {
    const user = localStorage.getItem("user");
    return user ? JSON.parse(user) : null;
  } catch (error) {
    console.error("User parse error:", error);
    return null;
  }
};


// -------------------------
// 🚪 LOGOUT (BACKEND + FRONTEND)
// -------------------------
export const logout = async () => {
  try {
    const session_token = localStorage.getItem("session_token");

    if (session_token) {
      await fetch(`${API_URL}/logout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ session_token }),
      });
    }
  } catch (error) {
    console.error("Logout API error:", error);
  } finally {
    // 🔥 Always clear frontend session
    localStorage.removeItem("token");
    localStorage.removeItem("session_token");
    localStorage.removeItem("user");
  }
};


// -------------------------
// 🔑 GET TOKEN (FOR API CALLS)
// -------------------------
export const getToken = () => {
  return localStorage.getItem("token");
};


// -------------------------
// 📡 AUTHENTICATED FETCH (VERY IMPORTANT)
// -------------------------
export const authFetch = async (url, options = {}) => {
  const token = getToken();

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_URL}${url}`, {
      ...options,
      headers,
    });

    // 🔥 Auto logout if token expired
    if (response.status === 401) {
      logout();
      window.location.reload();
    }

    return response;
  } catch (error) {
    console.error("API error:", error);
    throw error;
  }
};
