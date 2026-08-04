import { useState } from "react";

export default function Upload() {
  const API_URL = process.env.REACT_APP_API_URL;
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState("");

  const uploadFile = async () => {
    if (!file.name.endsWith(".pdf")) {
        setMessage("Only PDF files allowed ❌");
        return;
}

    const formData = new FormData();

    formData.append("file", file);
    formData.append("state", "Maharashtra");
    formData.append("year", "2005"); // 🔥 IMPORTANT: string
    formData.append("month", "March");
    formData.append("power_type", "Wind");
    formData.append("category", "General");

    // 🔥 TEMP TOKEN FIX
    formData.append("token", "dummy");

    try {
const res = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      console.log(data); // DEBUG

      // Handle HTTPException from backend - error message is in 'detail' field
      setMessage(data.message || data.detail || data.error);
    } catch (error) {
      console.error(error);
      setMessage("Upload failed ❌");
    }
  };

  return (
    <div className="bg-white p-5 rounded-2xl shadow mb-6">
      <h2 className="text-xl font-semibold mb-3">Upload Policy 📂</h2>

      <input
        type="file"
        onChange={(e) => setFile(e.target.files[0])}
        className="mb-3"
      />

      <button
        onClick={uploadFile}
        className="bg-green-600 text-white px-4 py-2 rounded"
      >
        Upload
      </button>

      <p className="mt-2">{message}</p>
    </div>
  );
}