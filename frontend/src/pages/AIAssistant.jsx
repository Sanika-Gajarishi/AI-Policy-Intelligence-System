import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { Brain, Sparkles, Loader2, FileText, ArrowLeft, TrendingUp, Calendar, AlertTriangle, Info, Copy, CheckCircle2, Download, Plus, MessageSquare, Edit } from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { Skeleton } from "../components/ui/Skeleton";
import { authFetch } from "../services/auth";
import PolicyInfographic from "../components/PolicyInfographic";
import { buildInfographicHTML } from "../utils/infographic_export";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";




// ── Markdown component overrides ────────────────────────────────────────────
const markdownComponents = {
  // Tables
  table: ({ children }) => (
    <div className="overflow-x-auto my-4 rounded border border-slate-200">
      <table className="min-w-full divide-y divide-slate-200 text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-slate-50">{children}</thead>,
  tbody: ({ children }) => <tbody className="divide-y divide-slate-200">{children}</tbody>,
  tr: ({ children }) => <tr className="hover:bg-slate-50">{children}</tr>,
  th: ({ children }) => (
    <th className="px-4 py-2 text-left font-semibold text-slate-800 whitespace-nowrap">{children}</th>
  ),
  td: ({ children }) => <td className="px-4 py-2 text-slate-700">{children}</td>,

  // Headings
  h1: ({ children }) => (
    <h1 className="text-2xl font-bold text-black mt-6 mb-3">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-xl font-bold text-black mt-5 mb-2.5">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-lg font-bold text-black mt-4 mb-2">{children}</h3>
  ),

  // Paragraphs — larger text, generous line height, good spacing, JUSTIFIED
  p: ({ children }) => (
    <p className="text-[16px] text-black leading-8 mb-4 text-justify">{children}</p>
  ),

  // Bold
  strong: ({ children }) => (
    <strong className="font-semibold text-black">{children}</strong>
  ),

  // Italic
  em: ({ children }) => <em className="italic text-slate-700">{children}</em>,

  // Bullet lists
  ul: ({ children }) => (
    <ul className="list-disc list-outside ml-5 mb-4 space-y-1.5">{children}</ul>
  ),

  // Numbered lists
  ol: ({ children }) => (
    <ol className="list-decimal list-outside ml-5 mb-4 space-y-1.5">{children}</ol>
  ),

  li: ({ children }) => (
    <li className="text-[16px] text-black leading-7 text-justify">{children}</li>
  ),

  // Horizontal rule (--- divider)
  hr: () => <hr className="my-5 border-t border-slate-200" />,

  // Blockquote (used for notes/warnings in prompts)
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-amber-400 pl-4 my-3 text-slate-700 italic bg-amber-50 py-2 rounded-r text-justify">
      {children}
    </blockquote>
  ),

  // Inline code
  code: ({ children }) => (
    <code className="bg-slate-100 rounded px-1 py-0.5 text-sm font-mono text-slate-800">{children}</code>
  ),
};

export default function AIAssistant({ user, onNavigateBack, selectedPolicies }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [tableData, setTableData] = useState(null);
  const [infographicData, setInfographicData] = useState(null);
  const [viewMode, setViewMode] = useState("text");
  const [loading, setLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [openMenuId, setOpenMenuId] = useState(null);
  useEffect(() => {
    loadUserConversations();
}, []);
  const [sources, setSources] = useState([]);
  const [contextPolicies, setContextPolicies] = useState([]);
  const [warning, setWarning] = useState("");
  const [exporting, setExporting] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const messagesEndRef = useRef(null);
  const didMountRef = useRef(false);
  const [activePolicies, setActivePolicies] = useState([]);

  const hasActivePolicies = activePolicies.length > 0;
  const canAsk = !loading && (question.trim().length > 0 || hasActivePolicies);
  const canExport = !loading && !exporting && (question.trim().length > 0 || hasActivePolicies);

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };

  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: { y: 0, opacity: 1, transition: { duration: 0.5 } }
  };

  useEffect(() => {
    const next = selectedPolicies || [];
    setContextPolicies(next);
    setActivePolicies(next);
  }, [selectedPolicies]);

  useEffect(() => {
    if (!didMountRef.current) {
      didMountRef.current = true;
      return;
    }
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Close the open chat-history dropdown menu when clicking anywhere else
  useEffect(() => {
    const closeMenu = () => setOpenMenuId(null);
    document.addEventListener("click", closeMenu);
    return () => document.removeEventListener("click", closeMenu);
  }, []);

 
 
  const fetchData = async () => {
    const prompt = question.trim() || (hasActivePolicies ? "Summarize the selected policies" : "");
    if (!prompt) return;

    setLoading(true);
    setStatusMessage("Generating AI response from selected policy documents...");

    const userMessage = { role: "user", content: prompt };
    setMessages((prev) => [...prev, userMessage]);

    const currentQuestion = prompt;
    setQuestion("");

    try {
      const res = await authFetch("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: prompt,
          selected_policies: activePolicies.map(p => ({
            file: p.file,
            state: p.state,
            power_type: p.power_type,
            year: p.year
          })),
          conversation_id: conversationId,
          user_id: user.email
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP error! status: ${res.status}`);

      const answer = data.answer || data.error;

      if (!conversationId && data.conversation_id) {
        setConversationId(data.conversation_id);
        loadUserConversations();
      }
      if (data.infographic_data) { setInfographicData(data.infographic_data); setViewMode("infographic"); }
      if (data.table) setTableData(data.table);

      const now = new Date().toISOString();
      setSources(Array.isArray(data.sources) ? data.sources : []);
      setWarning(data.warning || "");

      const assistantMessage = {
        role: "assistant",
        content: answer,
        table: data.table || null,
        infographic_data: data.infographic_data || null,
        sources: Array.isArray(data.sources) ? data.sources : [],
        warning: data.warning || ""
      };
      setMessages((prev) => [...prev, assistantMessage]);


    } catch (error) {
      console.error("AI Assistant Error:", error);
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${error.message || "Backend error. Please try again."}` }]);
    } finally {
      setLoading(false);
      setStatusMessage("");
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !loading) fetchData();
  };

  const copyToClipboard = (text) => {
    if (!text) return;
    navigator.clipboard.writeText(text).catch((error) => console.error("Copy failed", error));
  };

  const startNewChat = () => {
    setMessages([]);
    setConversationId(null);
    setQuestion("");
    setTableData(null);
    setInfographicData(null);
    setViewMode("text");
    setSources([]);
    setWarning("");
  };

  const loadFromHistory = (chat) => {
    setMessages(chat.messages || []);
    setConversationId(chat.id);

    setTableData(null);
    setInfographicData(null);
    setViewMode("text");
    setSources([]);
    setWarning("");
};
  
  const deleteChat = async (id) => {
    await authFetch(`/conversations/${id}`, {
        method: "DELETE"
    });

    loadUserConversations();
};

  const renameChat = async (id, title) => {
    await authFetch(
        `/conversations/${id}/rename`,
        {
            method: "PUT",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                title
            })
        }
    );

    loadUserConversations();
};

  const pinChat = async (id, pinned) => {
    await authFetch(
        `/conversations/${id}/pin?pinned=${pinned}`,
        {
            method: "PUT"
        }
    );

    loadUserConversations();
};

  const exportDocument = async (docType) => {
    const prompt = question.trim() || (hasActivePolicies ? "Create a document summarizing the selected policies" : "");
    if (!prompt) return;
    setExporting(true);
    setStatusMessage(
      `Generating ${docType === "report" ? "PDF" : docType === "word" ? "Word document" : "PowerPoint presentation"}...`
    );

    try {
      const res = await authFetch("/generate-doc", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: prompt,
          doc_type: docType,
          selected_policies: activePolicies.map((p) => ({
            file: p.file, state: p.state, power_type: p.power_type, year: p.year,
          })),
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.error || "Document generation failed.");
      }

      const blob = await res.blob();
      const ext = docType === "ppt" ? "pptx" : docType === "word" ? "docx" : "pdf";
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `policy_${docType}.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Export failed", error);
      setMessages(prev => [...prev, { role: "assistant", content: `Export error: ${error.message || "Unable to generate document."}` }]);
    } finally {
      setExporting(false);
      setStatusMessage("");
    }
  };

  const loadUserConversations = async () => {
    try {
        const response = await authFetch(
            `/conversations/user/${user.email}`
        );

        const data = await response.json();

        setChatHistory(
            data.conversations || []
        );
    } catch (error) {
        console.error(
            "Failed to load conversations",
            error
        );
    }
};

const generateAndExportInfographic = async () => {
  const prompt =
    question.trim() ||
    (hasActivePolicies
      ? "Create an infographic of the selected policies"
      : "");

  if (!prompt) return;

  setExporting(true);
  setStatusMessage("Generating infographic...");

  try {
    const infographicQuestion = "Create an infographic: " + prompt;

    const res = await authFetch("/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question: infographicQuestion,
        selected_policies: activePolicies.map((p) => ({
          file: p.file,
          state: p.state,
          power_type: p.power_type,
          year: p.year,
        })),
      }),
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));

      throw new Error(
        errorData.detail ||
        errorData.error ||
        "Infographic generation failed."
      );
    }

    const data = await res.json();

    const infData = data.infographic_data;

    if (!infData) {
      throw new Error(
        "No infographic data returned from server."
      );
    }

    // NEW EXPORT ENGINE
    const infographicHTML = buildInfographicHTML(infData);

    if (!infographicHTML) {
      throw new Error(
        "Failed to build infographic HTML."
      );
    }

    const blob = new Blob(
      [infographicHTML],
      { type: "text/html" }
    );

    const url = window.URL.createObjectURL(blob);

    const a = document.createElement("a");

    a.href = url;
    a.download = `policy_infographic_${Date.now()}.html`;

    document.body.appendChild(a);
    a.click();
    a.remove();

    window.URL.revokeObjectURL(url);

    setStatusMessage(
      "Infographic downloaded successfully!"
    );

    setTimeout(() => {
      setStatusMessage("");
    }, 3000);

  } catch (error) {
    console.error(
      "Infographic export failed",
      error
    );

    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content:
          `Infographic export error: ${
            error.message ||
            "Unable to generate infographic."
          }`
      }
    ]);
  } finally {
    setExporting(false);
    setStatusMessage("");
  }
};

  // ── Render assistant message content ──────────────────────────────────────
  const renderAssistantContent = (msg) => {
    // Structured table from backend JSON
    if (msg.table) {
      return (
        <div className="overflow-x-auto rounded border border-slate-200 bg-white p-3">
          <h4 className="font-semibold text-slate-900 mb-2">
            {msg.table.table_title || "Tabulated response"}
          </h4>
          {msg.table.notes && (
            <p className="text-sm text-slate-600 mb-2 text-justify">{msg.table.notes}</p>
          )}
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                {msg.table.headers.map((header, i) => (
                  <th key={i} className="px-3 py-2 text-left font-semibold">{header}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {msg.table.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-3 py-2">{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    // Infographic
    if (msg.infographic_data) {
      return (
        <div className="my-4 rounded-lg overflow-auto">
          <PolicyInfographic data={msg.infographic_data} />
        </div>
      );
    }

    // ── Markdown renderer (handles tables, ---, bold, bullets, headings) ──
    return (
      <div className="prose prose-base max-w-none text-justify">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={markdownComponents}
        >
          {msg.content}
        </ReactMarkdown>
      </div>
    );
  };

  return (
    <motion.div
      className="w-full"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      <Card className="backdrop-blur-sm bg-white/90 border-gray-200 shadow-xl">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Brain className="w-8 h-8 text-purple-600" />
              <span className="text-2xl font-bold text-gray-800">AI Assistant</span>
            </div>
            {messages.length > 0 && (
              <Button onClick={startNewChat} variant="outline" size="sm" className="flex items-center gap-2">
                <Plus className="w-4 h-4" />
                New Chat
              </Button>
            )}
          </div>
          <CardDescription>
            Get AI-powered insights about your selected policy documents
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Main Chat Interface */}
            <div className="lg:col-span-3 space-y-6">
              {/* Chat Input */}
              <motion.div variants={itemVariants}>
                <Card className="backdrop-blur-sm bg-white/90 border-gray-200 shadow-lg">
                  <CardContent className="space-y-4 pt-6">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-700">Your Question</label>
                      <Input
                        type="text"
                        placeholder="e.g., Compare 2005 and 2015 policies..."
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                        onKeyPress={handleKeyPress}
                        className="bg-white"
                      />
                    </div>

                    <Button
                      onClick={fetchData}
                      disabled={!canAsk}
                      className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-medium shadow-lg hover:shadow-xl transition-all duration-200"
                    >
                      {loading ? (
                        <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Thinking...</>
                      ) : (
                        <><Brain className="w-4 h-4 mr-2" />Ask AI</>
                      )}
                    </Button>

                    {statusMessage && (
                      <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
                        {statusMessage}
                      </div>
                    )}

                    <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-2">
                      <Button onClick={() => exportDocument("ppt")} disabled={!canExport} variant="outline" className="w-full">
                        <Download className="w-4 h-4 mr-2" /> Create PPT
                      </Button>
                      <Button onClick={() => exportDocument("word")} disabled={!canExport} variant="outline" className="w-full">
                        <Download className="w-4 h-4 mr-2" /> Export Word
                      </Button>
                      <Button onClick={() => generateAndExportInfographic()} disabled={!canExport} variant="outline" className="w-full">
                        <Download className="w-4 h-4 mr-2" /> Export Infographic
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Chat Messages */}
              <motion.div variants={itemVariants}>
                <Card className="backdrop-blur-sm bg-white/90 border-gray-200 shadow-lg">
                  <CardHeader>
                    <CardTitle className="flex items-center space-x-2">
                      <MessageSquare className="w-5 h-5 text-green-600" />
                      <span>Conversation</span>
                    </CardTitle>
                    <CardDescription>
                      Your conversation history with the AI assistant. Follow-up questions maintain context.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="min-h-[400px] max-h-[600px] overflow-y-auto space-y-4">
                      {messages.length === 0 ? (
                        <div className="text-center py-12 text-gray-400">
                          <Brain className="w-12 h-12 mx-auto mb-4 opacity-50" />
                          <p className="text-lg font-medium">Ready to help</p>
                          <p className="text-base">Ask a question about energy policies</p>
                        </div>
                      ) : (
                        messages.map((msg, index) => (
                          <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                          >
                            <div className="max-w-[95%] rounded-lg p-4">
                              <div className="flex items-center justify-between gap-2 mb-2">
                                <span className="font-semibold text-base">
                                  {msg.role === "user" ? "You" : "Assistant"}
                                </span>
                                {msg.role === "user" ? (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => setQuestion(msg.content)}
                                    className="inline-flex items-center gap-2"
                                  >
                                    <Edit className="w-4 h-4" />
                                    Edit
                                  </Button>
                                ) : (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => copyToClipboard(msg.content)}
                                    className="inline-flex items-center gap-2"
                                  >
                                    <Copy className="w-4 h-4" />
                                    Copy
                                  </Button>
                                )}
                              </div>

                              {msg.role === "user" ? (
                                <p className="whitespace-pre-wrap text-base text-justify">{msg.content}</p>
                              ) : (
                                <div>
                                  {msg.warning && (
                                    <div className="mb-3 p-3 bg-amber-100 border border-amber-300 rounded text-amber-800 text-sm">
                                      <AlertTriangle className="w-4 h-4 inline mr-1" />
                                      {msg.warning}
                                    </div>
                                  )}
                                  {renderAssistantContent(msg)}
                                </div>
                              )}
                            </div>
                          </motion.div>
                        ))
                      )}

                      {loading && (
                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
                          <div className="bg-gray-100 rounded-lg p-4">
                            <div className="flex items-center gap-2">
                              <Loader2 className="w-4 h-4 animate-spin" />
                              <span className="text-base">Thinking...</span>
                            </div>
                          </div>
                        </motion.div>
                      )}

                      <div ref={messagesEndRef} />
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Selected Policies */}
              {contextPolicies.length > 0 && (
                <motion.div variants={itemVariants}>
                  <Card className="backdrop-blur-sm bg-white/90 border-gray-200 shadow-lg">
                    <CardHeader>
                      <CardTitle className="flex items-center space-x-2">
                        <FileText className="w-5 h-5 text-green-600" />
                        <span>Selected Policies</span>
                      </CardTitle>
                      <CardDescription>
                        {activePolicies.length} policy{activePolicies.length === 1 ? "" : "ies"} enabled for context
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {contextPolicies.map((policy, index) => (
                        <label
                          key={index}
                          className="flex items-start gap-3 bg-blue-50 rounded-lg p-3 border border-blue-200 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            className="mt-1 h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                            checked={activePolicies.some(p => p.file === policy.file)}
                            onChange={(e) => {
                              const enabled = e.target.checked;
                              setActivePolicies((prev) => {
                                if (enabled) {
                                  if (prev.some(p => p.file === policy.file)) return prev;
                                  return [...prev, policy];
                                }
                                return prev.filter(p => p.file !== policy.file);
                              });
                            }}
                          />
                          <div className="min-w-0 flex-1">
                            <div className="text-sm font-medium text-gray-800 line-clamp-1">{policy.file}</div>
                            <div className="text-xs text-black mt-1">
                              {policy.state} • {policy.power_type} • {policy.year}
                            </div>
                          </div>
                        </label>
                      ))}
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {/* Quick Questions */}
              <motion.div variants={itemVariants}>
                <Card className="backdrop-blur-sm bg-white/90 border-gray-200 shadow-lg">
                  <CardHeader>
                    <CardTitle className="flex items-center space-x-2">
                      <TrendingUp className="w-5 h-5 text-blue-600" />
                      <span>Quick Questions</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {(activePolicies.length > 0 ? [
                      `Summarize the selected ${activePolicies.length > 1 ? activePolicies.length + " policies" : "policy"}`,
                      "What are the key changes in these policies?",
                      "Compare the renewable energy targets",
                      "What incentives are available?",
                      "Implementation timeline overview"
                    ] : [
                      "What are the key policy changes?",
                      "Compare renewable energy targets",
                      "Show policy effectiveness metrics",
                      "What incentives are available?",
                      "Policy implementation timeline"
                    ]).map((quickQuestion, index) => (
                      <Button
                        key={index}
                        variant="ghost"
                        size="sm"
                        onClick={() => setQuestion(quickQuestion)}
                        className="w-full justify-start text-left hover:bg-blue-50 hover:text-blue-700"
                      >
                        {quickQuestion}
                      </Button>
                    ))}
                  </CardContent>
                </Card>
              </motion.div>

              {/* Chat History */}
              {chatHistory.length > 0 && (
                <motion.div variants={itemVariants}>
                  <Card className="backdrop-blur-sm bg-white/90 border-gray-200 shadow-lg">
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <Calendar className="w-5 h-5 text-green-600" />
                          <span>Recent Conversations</span>
                        </div>
                        <span className="text-xs text-green-600">Synced</span>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-2 overflow-visible">
                      {[...chatHistory].reverse().map((chat, index) => (
                        <div
                          key={chat.id}
                          onClick={() => loadFromHistory(chat)}
                          className="w-full text-left rounded-lg border border-slate-200 px-3 py-3 transition hover:border-purple-300 hover:bg-purple-50 cursor-pointer"
                        >
                          <div className="relative flex items-center justify-between">
                            <p className="text-sm font-medium truncate flex-1 flex items-center gap-2">
                              {chat.pinned && "📌"}
                              {chat.title || "New Chat"}
                            </p>

                            <div className="relative">
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setOpenMenuId(openMenuId === chat.id ? null : chat.id);
                                }}
                                className="
                                  px-2
                                  text-slate-500
                                  hover:text-slate-700
                                  rounded
                                "
                              >
                                ⋮
                              </button>

                              {openMenuId === chat.id && (
                                <div
                                  onClick={(e) => e.stopPropagation()}
                                  className="
                                    absolute
                                    right-0
                                    top-7
                                    bg-white
                                    border
                                    border-slate-200
                                    rounded-lg
                                    shadow-lg
                                    z-50
                                    min-w-[140px]
                                    overflow-hidden
                                  "
                                >
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setOpenMenuId(null);

                                      const title = prompt(
                                        "Rename conversation",
                                        chat.title
                                      );

                                      if (title) {
                                        renameChat(chat.id, title);
                                      }
                                    }}
                                    className="
                                      w-full
                                      text-left
                                      px-4
                                      py-2
                                      hover:bg-slate-100
                                    "
                                  >
                                    Rename
                                  </button>

                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setOpenMenuId(null);
                                      pinChat(chat.id, !chat.pinned);
                                    }}
                                    className="
                                      w-full
                                      text-left
                                      px-4
                                      py-2
                                      hover:bg-slate-100
                                    "
                                  >
                                    {chat.pinned ? "Unpin" : "Pin"}
                                  </button>

                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setOpenMenuId(null);

                                      if (
                                        window.confirm(
                                          "Delete this conversation?"
                                        )
                                      ) {
                                        deleteChat(chat.id);
                                      }
                                    }}
                                    className="
                                      w-full
                                      text-left
                                      px-4
                                      py-2
                                      text-red-600
                                      hover:bg-red-50
                                    "
                                  >
                                    Delete
                                  </button>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
