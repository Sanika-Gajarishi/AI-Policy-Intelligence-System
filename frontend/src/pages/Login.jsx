import { useState } from "react";
import axios from "axios";
import climatehubLogo from "../assets/CHIAL_LOGO.png";
import { auth, googleProvider } from "../firebase";
import { signInWithPopup } from "firebase/auth";

const API_URL = process.env.REACT_APP_API_URL;

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const handleGoogleSignIn = async () => {
    setLoading(true);
    setError("");

    try {
      const result = await signInWithPopup(auth, googleProvider);
      const user = result.user;

      if (!user.email.toLowerCase().endsWith("@climatehub.in")) {
        setError("Only users with @climatehub.in email addresses are allowed to login.");
        await auth.signOut();
        setLoading(false);
        return;
      }

      const response = await axios.post(`${API_URL}/auth/google`, {
        email: user.email,
        displayName: user.displayName,
        uid: user.uid,
        emailVerified: user.emailVerified
      });

      const loggedInUser = {
        ...response.data.user,
        uid: user.uid,
        displayName: user.displayName
      };

      localStorage.setItem("user", JSON.stringify(loggedInUser));

      onLogin(loggedInUser);

      if (response.data.token) {
        localStorage.setItem("token", response.data.token);
        localStorage.setItem("session_token", response.data.session_token);
      } else {
        setError("Google sign-in failed. Please try again.");
      }
    } catch (err) {
      console.error("Google sign-in error:", err);
      if (err.code === 'auth/popup-closed-by-user') {
        setError("Sign-in popup was closed. Please try again.");
      } else if (err.code === 'auth/popup-blocked') {
        setError("Pop-up was blocked. Please allow pop-ups and try again.");
      } else {
        setError("Failed to sign in with Google. Please try again.");
      }
    }

    setLoading(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    if (!email.toLowerCase().includes("climatehub")) {
      setError("Only users with climatehub email addresses are allowed to login.");
      setLoading(false);
      return;
    }

    try {
      const endpoint = isRegistering ? "/register" : "/login";
      const payload = isRegistering
        ? { email, password, full_name: fullName }
        : { email, password };

      const response = await axios.post(`${API_URL}${endpoint}`, payload);

      if (response.data.token) {
        localStorage.setItem("token", response.data.token);
        localStorage.setItem("session_token", response.data.session_token);
        localStorage.setItem("user", JSON.stringify(response.data.user));

        onLogin(response.data.user);
      } else {
        setError(response.data.message || "Registration successful, please login");
        if (isRegistering) {
          setIsRegistering(false);
          setFullName("");
        }
      }
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message || "Something went wrong";
      if (errorMessage.includes("Invalid email or password")) {
        setError("Invalid credentials. Please check your email and password, or create a new account.");
      } else if (errorMessage.includes("Email already registered")) {
        setError("This email is already registered. Please try logging in instead.");
      } else {
        setError(errorMessage);
      }
    }

    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex flex-col items-center justify-center p-4">
      <div className="mb-8">
        <img src={climatehubLogo} alt="ClimateHub" className="w-64 h-auto transform scale-200" />
      </div>

      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">
            {isRegistering ? "Create Account" : "Welcome Back"}
          </h1>
          <p className="text-gray-600">
            {isRegistering ? "Sign up to access the RE Policy Analyser " : "Login to access your RE Policy Analyser"}
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        <div className="mb-6">
          <button
            type="button"
            onClick={handleGoogleSignIn}
            disabled={loading}
            className="w-full flex items-center justify-center gap-3 bg-white border-2 border-gray-300 text-gray-700 py-3 rounded-lg font-semibold hover:bg-gray-50 transition duration-200 disabled:opacity-50"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Sign in with Google
          </button>
        </div>

        <div className="relative mb-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-white text-gray-500">Or continue with email</span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {isRegistering && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Full Name</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="Enter your full name"
                required
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Email Address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="Enter your email"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Password
            </label>

            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2 pr-12 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="Enter your password"
                required
              />

              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-500 hover:text-gray-700 text-lg"
              >
                👁
              </button>
            </div>
            {!isRegistering && (
              <div className="text-right mt-2">
                <button
                  type="button"
                  onClick={() => alert("Forgot password feature coming soon")}
                  className="text-sm text-blue-600 hover:text-blue-700"
                >
                  Forgot Password?
                </button>
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 transition duration-200 disabled:opacity-50"
          >
            {loading ? (isRegistering ? "Creating Account..." : "Signing In...") : (isRegistering ? "Create Account" : "Sign In")}
          </button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-gray-600">
            {isRegistering ? "Already have an account?" : "Don't have an account?"}
            <button
              type="button"
              onClick={() => { setIsRegistering(!isRegistering); setError(""); setFullName(""); }}
              className="ml-1 text-blue-600 hover:text-blue-700 font-medium"
            >
              {isRegistering ? "Sign In" : "Sign Up"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}