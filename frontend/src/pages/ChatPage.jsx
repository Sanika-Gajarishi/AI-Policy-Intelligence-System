import { User } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

const API_URL = process.env.REACT_APP_API_URL;

export default function ChatPage() {
  const navigate = useNavigate();

  const [question, setQuestion] = useState("");
  const [result, setResult] = useState("");

  const ask = async () => {
    const res = await fetch(`${API_URL}/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        state: "Maharashtra",
        year: 2005,
        power_type: "Wind",
        conversation_id: conversationId,
        user_id: user.uid
      }),
    });

    const data = await res.json();
    setResult(data.answer);
  };

  return (
    <div className="p-6 bg-gray-100 min-h-screen">
      <button
        onClick={() => navigate("/dashboard")}
        className="mb-4 bg-gray-500 text-white px-3 py-1 rounded"
      >
        ⬅ Back
      </button>

      <h1 className="text-2xl font-bold mb-4">🤖 Policy Chat</h1>

      <input
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask about policy..."
        className="w-full p-3 border rounded mb-3"
      />

      <button
        onClick={ask}
        className="bg-blue-600 text-white px-4 py-2 rounded"
      >
        Ask
      </button>

      <div className="mt-4 bg-white p-4 rounded shadow">
        <h3 className="font-semibold">Answer:</h3>
        <p>{result}</p>
      </div>
    </div>
  );
}