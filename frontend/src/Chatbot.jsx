import { useState, useEffect, useRef } from "react";
import { Copy, Edit, RefreshCw } from "lucide-react";

function Chatbot() {
  const API_URL = process.env.REACT_APP_API_URL;
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [editingIndex, setEditingIndex] = useState(null);
  const [editedContent, setEditedContent] = useState("");
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const ask = async () => {
    if (!question.trim()) return;

    setIsLoading(true);
    
    // Add user message to UI immediately
    const userMessage = { role: "user", content: question };
    setMessages((prev) => [...prev, userMessage]);

    try {
const res = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: question,
          state: "Maharashtra",
          year: 2005,
          month: "March",
          power_type: "Wind",
          conversation_id: conversationId,
          user_id: user.uid
        }),
      });

      const data = await res.json();
      
      // Set conversation ID if this is the first message
      if (!conversationId && data.conversation_id) {
          setConversationId(data.conversation_id);
          loadUserConversations();
      }

      // Add assistant response to UI
      const assistantMessage = { role: "assistant", content: data.answer };
      setMessages((prev) => [...prev, assistantMessage]);
      
      // Clear input
      setQuestion("");
    } catch (error) {
      console.error("Error asking question:", error);
      const errorMessage = { role: "assistant", content: "Sorry, something went wrong. Please try again." };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      ask();
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setConversationId(null);
    setQuestion("");
  };

  const handleCopy = (content) => {
    navigator.clipboard.writeText(content);
  };

  const handleEdit = (index, content) => {
    setEditingIndex(index);
    setEditedContent(content);
  };

  const handleSaveEdit = (index) => {
    setMessages((prev) =>
      prev.map((msg, i) =>
        i === index ? { ...msg, content: editedContent } : msg
      )
    );
    setEditingIndex(null);
    setEditedContent("");
  };

  const handleCancelEdit = () => {
    setEditingIndex(null);
    setEditedContent("");
  };

  const handleRegenerate = async (index) => {
    if (index === 0 || messages[index - 1].role !== "user") return;

    setIsLoading(true);
    const userMessage = messages[index - 1];

    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: userMessage.content,
          state: "Maharashtra",
          year: 2005,
          month: "March",
          power_type: "Wind",
          conversation_id: conversationId,
          user_id: user.uid
        }),
      });

      const data = await res.json();

      setMessages((prev) =>
        prev.map((msg, i) =>
          i === index ? { role: "assistant", content: data.answer } : msg
        )
      );
    } catch (error) {
      console.error("Error regenerating response:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: "800px", margin: "0 auto", padding: "20px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <h2>Policy Chatbot 🤖</h2>
        {messages.length > 0 && (
          <button 
            onClick={startNewChat}
            style={{
              padding: "8px 16px",
              backgroundColor: "#f0f0f0",
              border: "1px solid #ccc",
              borderRadius: "4px",
              cursor: "pointer"
            }}
          >
            New Chat
          </button>
        )}
      </div>

      {/* Chat Messages */}
      <div 
        style={{
          border: "1px solid #ddd",
          borderRadius: "8px",
          padding: "20px",
          marginBottom: "20px",
          minHeight: "400px",
          maxHeight: "600px",
          overflowY: "auto",
          backgroundColor: "#fafafa"
        }}
      >
        {messages.length === 0 ? (
          <p style={{ color: "#666", textAlign: "center" }}>
            Start a conversation by asking a question about policy documents...
          </p>
        ) : (
          messages.map((msg, index) => (
            <div
              key={index}
              style={{
                marginBottom: "16px",
                display: "flex",
                flexDirection: "column",
                alignItems: msg.role === "user" ? "flex-end" : "flex-start"
              }}
            >
              <div
                style={{
                  maxWidth: "70%",
                  padding: "12px 16px",
                  borderRadius: "12px",
                  backgroundColor: msg.role === "user" ? "#007bff" : "#ffffff",
                  color: msg.role === "user" ? "#ffffff" : "#333333",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.1)"
                }}
              >
                <strong>{msg.role === "user" ? "You" : "Assistant"}:</strong>
                {editingIndex === index && msg.role === "assistant" ? (
                  <textarea
                    value={editedContent}
                    onChange={(e) => setEditedContent(e.target.value)}
                    style={{
                      width: "100%",
                      marginTop: "8px",
                      padding: "8px",
                      borderRadius: "4px",
                      border: "1px solid #ddd",
                      minHeight: "60px",
                      resize: "vertical"
                    }}
                  />
                ) : (
                  <p style={{ margin: "4px 0 0 0", whiteSpace: "pre-wrap" }}>
                    {msg.content}
                  </p>
                )}
              </div>
              {editingIndex !== index && (
                <div
                  style={{
                    display: "flex",
                    gap: "8px",
                    marginTop: "8px",
                    padding: "4px 8px",
                    backgroundColor: "#f5f5f5",
                    borderRadius: "4px"
                  }}
                >
                  <button
                    onClick={() => handleCopy(msg.content)}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: "4px",
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                      color: "#666",
                      fontSize: "12px"
                    }}
                    title="Copy"
                  >
                    <Copy size={14} />
                  </button>
                  {msg.role === "user" ? (
                    <button
                      onClick={() => {
                        setQuestion(msg.content);
                      }}
                      style={{
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        padding: "4px",
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                        color: "#666",
                        fontSize: "12px"
                      }}
                      title="Edit"
                    >
                      <Edit size={14} />
                    </button>
                  ) : (
                    <button
                      onClick={() => handleEdit(index, msg.content)}
                      style={{
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        padding: "4px",
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                        color: "#666",
                        fontSize: "12px"
                      }}
                      title="Edit"
                    >
                      <Edit size={14} />
                    </button>
                  )}
                  {msg.role === "assistant" && (
                    <button
                      onClick={() => handleRegenerate(index)}
                      disabled={isLoading}
                      style={{
                        background: "none",
                        border: "none",
                        cursor: isLoading ? "not-allowed" : "pointer",
                        padding: "4px",
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                        color: isLoading ? "#ccc" : "#666",
                        fontSize: "12px"
                      }}
                      title="Regenerate"
                    >
                      <RefreshCw size={14} />
                    </button>
                  )}
                </div>
              )}
              {editingIndex === index && msg.role === "assistant" && (
                <div
                  style={{
                    display: "flex",
                    gap: "8px",
                    marginTop: "8px"
                  }}
                >
                  <button
                    onClick={() => handleSaveEdit(index)}
                    style={{
                      padding: "6px 12px",
                      backgroundColor: "#007bff",
                      color: "white",
                      border: "none",
                      borderRadius: "4px",
                      cursor: "pointer",
                      fontSize: "12px"
                    }}
                  >
                    Save
                  </button>
                  <button
                    onClick={handleCancelEdit}
                    style={{
                      padding: "6px 12px",
                      backgroundColor: "#f0f0f0",
                      color: "#333",
                      border: "1px solid #ccc",
                      borderRadius: "4px",
                      cursor: "pointer",
                      fontSize: "12px"
                    }}
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          ))
        )}
        {isLoading && (
          <div style={{ textAlign: "center", color: "#666" }}>
            Thinking...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div style={{ display: "flex", gap: "10px" }}>
        <textarea
          placeholder="Ask something about policy documents..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={isLoading}
          style={{
            flex: 1,
            padding: "12px",
            border: "1px solid #ddd",
            borderRadius: "8px",
            resize: "vertical",
            minHeight: "50px",
            fontFamily: "inherit"
          }}
          rows={1}
        />
        <button
          onClick={ask}
          disabled={isLoading || !question.trim()}
          style={{
            padding: "12px 24px",
            backgroundColor: isLoading || !question.trim() ? "#ccc" : "#007bff",
            color: "white",
            border: "none",
            borderRadius: "8px",
            cursor: isLoading || !question.trim() ? "not-allowed" : "pointer",
            fontWeight: "bold"
          }}
        >
          {isLoading ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}

export default Chatbot;