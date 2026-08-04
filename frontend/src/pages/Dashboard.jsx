import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { TrendingUp, FileText, Loader2, CheckCircle, X, Download, Plus, ChevronDown } from "lucide-react";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import Header from "../components/Header";
import { StateDropdown } from "../components/StateDropdown";
import { EnergyTypeDropdown } from "../components/EnergyTypeDropdown";
import { matchesEnergyTypeFilter } from "../constants/energyTypeOptions";
import { TypeOfDocumentDropdown } from "../components/TypeOfDocumentDropdown";
import AIAssistant from "./AIAssistant";
import { getToken } from "../services/auth";
import {
  fetchScrapeQueue,
  fetchScrapeQueueCount,
  clearScrapeQueue,
  runScraper,
  acceptScrapedDocument,
  rejectScrapedDocument,
} from "../services/scraper";

const DOC_TYPE_KEY_TO_CATEGORY = {
  policy: "Policy",
  regulation: "Regulation",
  order: "Order",
  roadmap: "Road Map",
  notification: "Notification",
  circular: "Circular",
  act: "Act",
  gazette: "Gazette",
  electricity_plan: "Electricity Plan",
};

// ─────────────────────────────────────────────────────────────────────────────
// Reusable dropdown-with-checkboxes component (same UX as TypeOfDocumentDropdown)
// ───────────────────────────────────────────────────────────────────────────
// ─────────────────────────────────────────────────────────────────────────────

export default function Dashboard({ user, onLogout }) {
  const API_URL = process.env.REACT_APP_API_URL;

  // ── Filter state ──────────────────────────────────────────────────────────
  const [selectedStates, setSelectedStates] = useState([]);
  const [selectedEnergyTypes, setSelectedEnergyTypes] = useState([]);
  const [year, setYear] = useState("");
  const [documentTypes, setDocumentTypes] = useState({
    policy: false,
    regulation: false,
    electricity_plan: false,
    act: false,
    gazette: false,
    order: false,
    roadmap: false,
    circular: false,
    notification: false,
  });

  // ── UI state ──────────────────────────────────────────────────────────────
  const [uploadMessage, setUploadMessage] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPolicy, setSelectedPolicy] = useState(null);
  const [showPdfModal, setShowPdfModal] = useState(false);
  const [allPolicies, setAllPolicies] = useState([]);
  const [activeSection] = useState("dashboard");
  const [language, setLanguage] = useState("english");
  const [showLanguageDropdown, setShowLanguageDropdown] = useState(false);
  const [selectedPolicies, setSelectedPolicies] = useState([]);

  const fileInputRef = useRef(null);

  // ── Scraper state ─────────────────────────────────────────────────────────
  const [scrapeQueue, setScrapeQueue] = useState([]);
  const [scrapeQueueCount, setScrapeQueueCount] = useState(0);
  const [scrapeActionLoading, setScrapeActionLoading] = useState({});
  const [scrapeRunning, setScrapeRunning] = useState(false);
  const [lastScrapeSession, setLastScrapeSession] = useState(null);

  // ── Translations ──────────────────────────────────────────────────────────
  const translations = {
    english: {
      dashboard: "Dashboard", uploadPdf: "Upload PDF", policyDocuments: "Policy",
      aiAssistant: "AI Assistant", regulations: "Regulations", order: "Order",
      roadmaps: "Roadmaps", notification: "Notifications", logout: "Logout",
      settings: "Settings", language: "Language", welcome: "Welcome",
      policyAIDashboard: "RE Policy Analyser", policyFilters: "Policy Filters",
      selectParameters: "Select parameters to filter policies", state: "State",
      energyType: "Energy Type", year: "Year", documentType: "Document Type",
      currentSelection: "Current Selection",
    },
    hindi: {
      dashboard: "डैशबोर्ड", uploadPdf: "पीडीएफ अपलोड करें", policyDocuments: "पॉलिसी",
      aiAssistant: "एआई सहायक", regulations: "विनियम", order: "आदेश",
      roadmaps: "रोडमैप", notification: "सूचनाएं", logout: "लॉगआउट",
      settings: "सेटिंग्स", language: "भाषा", welcome: "स्वागत है",
      policyAIDashboard: "पॉलिसी एआई डैशबोर्ड", policyFilters: "पॉलिसी फिल्टर",
      selectParameters: "पॉलिसी फ़िल्टर करने के लिए पैरामीटर चुनें", state: "राज्य",
      energyType: "ऊर्जा प्रकार", year: "वर्ष", documentType: "दस्तावेज़ प्रकार",
      currentSelection: "वर्तमान चयन",
    },
    marathi: {
      dashboard: "डॅशबोर्ड", uploadPdf: "पीडीएफ अपलोड करा", policyDocuments: "धोरण",
      aiAssistant: "एआय सहाय्यक", regulations: "नियमन", order: "आदेश",
      roadmaps: "रोडमॅप", notification: "सूचना", logout: "लॉगआउट",
      settings: "सेटिंग्ज", language: "भाषा", welcome: "स्वागत",
      policyAIDashboard: "धोरण एआय डॅशबोर्ड", policyFilters: "धोरण फिल्टर",
      selectParameters: "धोरण फिल्टर करण्यासाठी पॅरामीटर निवडा", state: "राज्य",
      energyType: "ऊर्जा प्रकार", year: "वर्ष", documentType: "दस्तऐवज प्रकार",
      currentSelection: "वर्तमान निवड",
    },
  };

  // Options for the two new dropdowns
//   const STATE_OPTIONS = [
//   { value: "Central", label: "Central" },
//   { value: "Andhra Pradesh", label: "Andhra Pradesh" },
//   { value: "Gujarat", label: "Gujarat" },
//   { value: "Haryana", label: "Haryana" },
//   { value: "Karnataka", label: "Karnataka" },
//   { value: "Madhya Pradesh", label: "Madhya Pradesh" },
//   { value: "Maharashtra", label: "Maharashtra" },
//   { value: "Punjab", label: "Punjab" },
//   { value: "Rajasthan", label: "Rajasthan" },
//   { value: "Tamil Nadu", label: "Tamil Nadu" },
//   { value: "Uttar Pradesh", label: "Uttar Pradesh" },
// ];

  // const ENERGY_OPTIONS = ENERGY_TYPE_FILTER_OPTIONS.filter((o) => o.value);

  const t = translations[language];

  // ── Filter helpers ────────────────────────────────────────────────────────

  const matchesStateFilter = (policy, states) => {
    if (states.length === 0) return true;
    return states.some((s) =>
      s === "Central"
        ? (policy.state || "").startsWith("Central")
        : policy.state === s
    );
  };

  const matchesTypeFilter = (policy, energyTypes) => {
    if (energyTypes.length === 0) return true;
    return energyTypes.some((t) => matchesEnergyTypeFilter(policy, t));
  };

  const matchesYearFilter = (policy, yearFilter) => {
    if (!yearFilter || yearFilter.toString().trim() === "") return true;
    const yearStr = yearFilter.toString().trim();
    const policyYear = policy.year.toString();

    if (policyYear === yearStr) return true;
    if (yearStr.length <= 3 && policyYear.startsWith(yearStr)) return true;

    if (yearStr.includes("-")) {
      const [startYear, endYear] = yearStr.split("-").map((y) => y.trim());
      const start = parseInt(startYear);
      const end = parseInt(endYear);
      if (!isNaN(start) && !isNaN(end)) {
        return policy.year >= start && policy.year <= end;
      }
    }
    return false;
  };

  const matchesDocumentTypeFilter = (policy, docTypes) => {
    const selectedTypes = Object.keys(docTypes).filter((k) => docTypes[k]);
    if (selectedTypes.length === 0) return true;
    const category = (policy.category || "General").trim().toLowerCase();
    return selectedTypes.some((type) => {
      const mapped = DOC_TYPE_KEY_TO_CATEGORY[type];
      return mapped && category === mapped.toLowerCase();
    });
  };

  const handleDocumentTypeChange = (type, isChecked) => {
    setDocumentTypes((prev) => ({ ...prev, [type]: isChecked }));
  };

  // ── Derived data ──────────────────────────────────────────────────────────

  const hasActiveFilters =
    selectedStates.length > 0 ||
    selectedEnergyTypes.length > 0 ||
    (year && year.toString().trim() !== "") ||
    Object.values(documentTypes).some((v) => v);

  const filteredPolicies = allPolicies.filter((policy) => {
    const matchesSearch =
      searchQuery === "" ||
      policy.file.toLowerCase().includes(searchQuery.toLowerCase()) ||
      policy.state.toLowerCase().includes(searchQuery.toLowerCase()) ||
      policy.power_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      policy.year.toString().includes(searchQuery);

    return (
      matchesSearch &&
      matchesStateFilter(policy, selectedStates) &&
      matchesTypeFilter(policy, selectedEnergyTypes) &&
      matchesYearFilter(policy, year) &&
      matchesDocumentTypeFilter(policy, documentTypes)
    );
  });

  // ── Data fetching ─────────────────────────────────────────────────────────

  const fetchPolicies = async () => {
    try {
      const res = await fetch(`${API_URL}/drive-policies`);
      const data = await res.json();
      setAllPolicies(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Error fetching policies:", error);
      setAllPolicies([]);
    }
  };

  const refreshScrapeNotifications = async () => {
    if (!getToken()) return;
    try {
      const [queue, countData] = await Promise.all([
        fetchScrapeQueue(),
        fetchScrapeQueueCount(),
      ]);
      setScrapeQueue(Array.isArray(queue) ? queue : []);
      setScrapeQueueCount(countData?.count ?? 0);
    } catch (error) {
      console.error("Failed to load scrape queue:", error);
    }
  };

  const refreshScrapeNotificationCount = async () => {
    if (!getToken()) return;
    try {
      const data = await fetchScrapeQueueCount();
      setScrapeQueueCount(data?.count ?? 0);
    } catch { /* ignore */ }
  };

  const handleClearScrapeQueue = async () => {
    if (!getToken()) return;
    try {
      await clearScrapeQueue();
      setScrapeQueue([]);
      setScrapeQueueCount(0);
    } catch (error) {
      console.error("Failed to clear scrape queue:", error);
    }
  };

  const handleRunScraper = async (scrapeState = "", yr = null, month = null, day = null) => {
    setScrapeRunning(true);
    try {
      const result = await runScraper({ state: scrapeState, year: yr, month, day });
      const count = result.new_documents ?? result.scraped ?? 0;
      setLastScrapeSession(result.session || new Date().toISOString().slice(0, 10));
      setUploadMessage(
        count > 0
          ? `Scrape complete — ${count} new document${count !== 1 ? "s" : ""} found`
          : "Scrape complete — no new documents found"
      );
      await refreshScrapeNotifications();
      setTimeout(() => setUploadMessage(""), 5000);
    } catch (error) {
      setUploadMessage(`Scrape failed: ${error.message}`);
      setTimeout(() => setUploadMessage(""), 5000);
    } finally {
      setScrapeRunning(false);
    }
  };

  const handleAcceptScraped = async (id, options = {}) => {
    setScrapeActionLoading((prev) => ({ ...prev, [id]: true }));
    try {
      const result = await acceptScrapedDocument(id, options);
      const warningCount = Array.isArray(result.warnings) ? result.warnings.length : 0;
      setUploadMessage(
        warningCount
          ? `${result.message || "Document accepted"} (${warningCount} warning${warningCount !== 1 ? "s" : ""})`
          : result.message || "Document accepted"
      );
      await refreshScrapeNotifications();
      await fetchPolicies();
      setTimeout(() => setUploadMessage(""), 4000);
      return result;
    } catch (error) {
      if (error.status !== 409 || options.force) {
        setUploadMessage(`Accept failed: ${error.message}`);
        setTimeout(() => setUploadMessage(""), 5000);
      }
      throw error;
    } finally {
      setScrapeActionLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  const handleRejectScraped = async (id) => {
    setScrapeActionLoading((prev) => ({ ...prev, [id]: true }));
    try {
      await rejectScrapedDocument(id);
      setUploadMessage("Document rejected");
      await refreshScrapeNotifications();
      setTimeout(() => setUploadMessage(""), 3000);
    } catch (error) {
      setUploadMessage(`Reject failed: ${error.message}`);
      setTimeout(() => setUploadMessage(""), 5000);
    } finally {
      setScrapeActionLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  // ── Policy interactions ───────────────────────────────────────────────────

  const handlePolicyClick = (policy) => { setSelectedPolicy(policy); setShowPdfModal(true); };
  const closePdfModal = () => { setShowPdfModal(false); setSelectedPolicy(null); };

  const handlePolicyCheckboxChange = (policy, isChecked) => {
    setSelectedPolicies((prev) =>
      isChecked ? [...prev, policy] : prev.filter((p) => p.file !== policy.file)
    );
  };

  const isPolicySelected = (policy) => selectedPolicies.some((p) => p.file === policy.file);

  const downloadPolicy = (policy) => {
    const url = policy.webViewLink || `${API_URL}/download/${policy.file}`;
    const a = document.createElement("a");
    a.href = url;
    a.download = policy.file;
    a.click();
  };

  const handleFileUpload = async (file) => {
    if (!file.name.endsWith(".pdf")) {
      setUploadMessage("Only PDF files allowed");
      setTimeout(() => setUploadMessage(""), 3000);
      return;
    }
    const filenameWithoutExt = file.name.replace(".pdf", "");
    const parts = filenameWithoutExt.split("_");
    if (parts.length < 3) {
      setUploadMessage("Invalid filename format. Use: State_EnergyType_Year.pdf");
      setTimeout(() => setUploadMessage(""), 5000);
      return;
    }
    const extractedState = parts[0];
    const extractedYear = parts[parts.length - 1];
    const extractedType = parts.slice(1, parts.length - 1).join("_");

    setUploadMessage("Uploading...");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("state", extractedState);
    formData.append("year", extractedYear);
    formData.append("month", "January");
    formData.append("power_type", extractedType);
    formData.append("token", "dummy");

    try {
      const res = await fetch(`${API_URL}/upload`, { method: "POST", body: formData });
      const data = await res.json();
      if (res.ok) { setUploadMessage(data.message || "Upload successful!"); fetchPolicies(); }
      else { setUploadMessage(data.detail || data.error || "Upload failed"); }
      setTimeout(() => setUploadMessage(""), 5000);
    } catch (error) {
      setUploadMessage(`Upload failed: ${error.message}`);
      setTimeout(() => setUploadMessage(""), 5000);
    }
  };

  // ── Effects ───────────────────────────────────────────────────────────────

  useEffect(() => {
    fetchPolicies();
    fetchScrapeQueueCount().then((data) => setScrapeQueueCount(data?.count ?? 0)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!getToken()) return undefined;
    const interval = setInterval(refreshScrapeNotificationCount, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => { fetchPolicies(); }, [year, documentTypes]);

  useEffect(() => { if (activeSection === "policies") fetchPolicies(); }, [activeSection]);

  useEffect(() => {
    const handler = (e) => {
      if (showLanguageDropdown && !e.target.closest(".settings-dropdown"))
        setShowLanguageDropdown(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showLanguageDropdown]);

  // ── Animation variants ────────────────────────────────────────────────────

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } },
  };
  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: { y: 0, opacity: 1, transition: { duration: 0.5 } },
  };

  // ── Current selection summary text ────────────────────────────────────────

  const selectionSummary = [
    selectedStates.length > 0 ? selectedStates.join(", ") : null,
    selectedEnergyTypes.length > 0 ? selectedEnergyTypes.join(", ") : null,
    year || null,
    Object.keys(documentTypes)
      .filter((k) => documentTypes[k])
      .map((k) => DOC_TYPE_KEY_TO_CATEGORY[k])
      .join(", ") || null,
  ]
    .filter(Boolean)
    .join(" • ") || "None";

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100">
      <motion.main className="flex-1" variants={containerVariants} initial="hidden" animate="visible">
        {activeSection === "dashboard" && (
          <div className="min-h-full">

            {/* Header */}
            <Header
              user={user}
              onLogout={onLogout}
              language={language}
              translations={t}
              setLanguage={setLanguage}
              scrapeQueue={scrapeQueue}
              scrapeQueueCount={scrapeQueueCount}
              scrapeActionLoading={scrapeActionLoading}
              scrapeRunning={scrapeRunning}
              onAcceptScraped={handleAcceptScraped}
              onRejectScraped={handleRejectScraped}
              onRefreshScrapeQueue={refreshScrapeNotifications}
              onClearScrapeQueue={handleClearScrapeQueue}
              onRunScraper={handleRunScraper}
              lastScrapeSession={lastScrapeSession}
            />

            {/* Upload toast */}
            <AnimatePresence>
              {uploadMessage && (
                <motion.div
                  initial={{ opacity: 0, y: -20, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -20, scale: 0.95 }}
                  className="fixed top-20 left-1/2 transform -translate-x-1/2 z-50 min-w-[300px]"
                >
                  <div className={`px-6 py-4 rounded-xl shadow-xl text-sm font-semibold border-2 ${
                    uploadMessage.toLowerCase().includes("failed") ||
                    uploadMessage.toLowerCase().includes("error") ||
                    uploadMessage.toLowerCase().includes("exist") ||
                    uploadMessage.toLowerCase().includes("invalid")
                      ? "bg-red-100 text-red-800 border-red-200"
                      : uploadMessage === "Uploading..."
                      ? "bg-blue-100 text-blue-800 border-blue-200"
                      : "bg-green-100 text-green-800 border-green-200"
                  }`}>
                    <div className="flex items-center space-x-3">
                      {uploadMessage.toLowerCase().includes("failed") ||
                      uploadMessage.toLowerCase().includes("error") ||
                      uploadMessage.toLowerCase().includes("exist") ||
                      uploadMessage.toLowerCase().includes("invalid") ? (
                        <X className="w-5 h-5" />
                      ) : uploadMessage === "Uploading..." ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <CheckCircle className="w-5 h-5" />
                      )}
                      <span>{uploadMessage}</span>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Main content */}
            <div className="flex items-center justify-center min-h-full mt-8 px-4 lg:px-8">
              <div className="w-full max-w-screen-2xl px-8 mx-auto">

                {/* ── Filters Card ── */}
                <motion.div variants={itemVariants}>
                  <Card className="h-full backdrop-blur-sm bg-white/90 border-gray-200 shadow-xl hover:shadow-2xl transition-shadow duration-300 p-8">
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <TrendingUp className="w-8 h-8 text-blue-600" />
                          <span className="text-2xl font-bold text-gray-800">Policy Filters</span>
                        </div>
                        <Button
                          onClick={() => fileInputRef.current?.click()}
                          className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white"
                          size="sm"
                        >
                          <Plus className="w-4 h-4" />
                          <span>Upload Document</span>
                        </Button>
                      </div>
                      <CardDescription>Select parameters to filter policies</CardDescription>
                    </CardHeader>

                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

                        {/* ── State dropdown ── */}
                        <div className="space-y-2">
                          <label className="text-sm font-medium text-gray-700">State</label>
                          <StateDropdown
  selectedStates={selectedStates}
  onStateChange={setSelectedStates}
/>
                        
                        </div>

                        {/* ── Energy Type dropdown ── */}
                        <div className="space-y-2">
                          <label className="text-sm font-medium text-gray-700">Energy Type</label>
                          <EnergyTypeDropdown
  selectedEnergyTypes={selectedEnergyTypes}
  onEnergyTypeChange={setSelectedEnergyTypes}
/>
                        
                        </div>

                        {/* ── Year input ── */}
                        <div className="space-y-2">
                          <label className="text-sm font-medium text-gray-700">Year</label>
                          <Input
                            type="text"
                            value={year}
                            onChange={(e) => setYear(e.target.value)}
                            placeholder="Year or range (e.g., 202, 2023-2025)"
                            className="bg-white"
                          />
                        </div>

                        {/* ── Document Type dropdown (unchanged) ── */}
                        <div className="space-y-2">
                          <label className="text-sm font-medium text-gray-700">Document Type</label>
                          <TypeOfDocumentDropdown
                            documentTypes={documentTypes}
                            onDocumentTypeChange={handleDocumentTypeChange}
                          />
                        </div>

                      </div>

                      {/* Current selection summary */}
                      <div className="pt-4 border-t border-gray-100">
                        <div className="flex items-center justify-between text-sm mb-3">
                          <span className="text-gray-500">Current Selection:</span>
                          <span className="font-medium text-gray-800">{selectionSummary}</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>

                {/* ── Filtered Policies list ── */}
                {hasActiveFilters && (
                  <motion.div variants={itemVariants} className="mt-8">
                    <Card className="backdrop-blur-sm bg-white/90 border-gray-200 shadow-xl">
                      <div className="px-6 pt-6 pb-2">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="text-lg font-semibold text-gray-800">Filtered Documents</h3>
                            <p className="text-sm text-gray-500 mt-1">
                              {filteredPolicies.length} matching documents found
                            </p>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Button
                              onClick={() => setSelectedPolicies([])}
                              variant="outline"
                              size="sm"
                              disabled={selectedPolicies.length === 0}
                              className="flex items-center space-x-1 hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-all duration-200"
                            >
                              <X className="w-3 h-3" />
                              <span>Clear All</span>
                            </Button>
                            <Button
                              onClick={() => setSelectedPolicies(filteredPolicies)}
                              variant="outline"
                              size="sm"
                              disabled={filteredPolicies.length === 0}
                              className="flex items-center space-x-1 hover:bg-green-50 hover:border-green-200 hover:text-green-600 transition-all duration-200"
                            >
                              <CheckCircle className="w-3 h-3" />
                              <span>Select All</span>
                            </Button>
                          </div>
                        </div>
                      </div>

                      <CardContent className="pt-2 pb-6">
                        {filteredPolicies.length === 0 ? (
                          <div className="text-center py-8">
                            <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                            <p className="text-gray-500 font-medium">No matching documents found</p>
                            <p className="text-gray-400 text-sm mt-1">
                              Change filter values to see matching documents
                            </p>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            {filteredPolicies.map((policy, index) => (
                              <div
                                key={`${policy.file}-${index}`}
                                className="rounded-xl border border-gray-200 bg-white p-4 hover:border-blue-300 hover:shadow-md transition-all"
                              >
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center space-x-3 flex-1">
                                    <input
                                      type="checkbox"
                                      checked={isPolicySelected(policy)}
                                      onChange={(e) => {
                                        e.stopPropagation();
                                        handlePolicyCheckboxChange(policy, e.target.checked);
                                      }}
                                      className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 cursor-pointer"
                                    />
                                    <div className="flex-1 min-w-0">
                                      <h4
                                        className="font-semibold text-gray-800 cursor-pointer hover:text-blue-600 truncate"
                                        onClick={() => handlePolicyClick(policy)}
                                      >
                                        {policy.file}
                                      </h4>
                                      <div className="flex items-center space-x-3 mt-1 text-xs text-gray-500">
                                        <span>{policy.state}</span>
                                        <span>•</span>
                                        <span>{policy.power_type}</span>
                                        <span>•</span>
                                        <span>{policy.year}</span>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </motion.div>
                )}

                {/* ── AI Assistant ── */}
                <motion.div variants={itemVariants} className="mt-8">
                  <AIAssistant
                    user={user}
                    onNavigateBack={() => {}}
                    selectedPolicies={selectedPolicies}
                  />
                </motion.div>

              </div>
            </div>
          </div>
        )}
      </motion.main>

      {/* ── PDF Viewer Modal ── */}
      {showPdfModal && selectedPolicy && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
          onClick={closePdfModal}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="bg-white rounded-2xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
                  <FileText className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-gray-800">{selectedPolicy.file}</h2>
                  <p className="text-sm text-gray-500">
                    {selectedPolicy.state} — {selectedPolicy.power_type} — {selectedPolicy.year}
                  </p>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                <Button
                  onClick={() => downloadPolicy(selectedPolicy)}
                  variant="outline"
                  size="sm"
                  className="flex items-center space-x-2"
                >
                  <Download className="w-4 h-4" />
                  <span>Download</span>
                </Button>
                <Button
                  onClick={closePdfModal}
                  variant="ghost"
                  size="sm"
                  className="p-2 hover:bg-gray-100"
                >
                  <X className="w-5 h-5" />
                </Button>
              </div>
            </div>
            <div style={{ height: "calc(90vh - 120px)" }}>
              <iframe
                src={
                  selectedPolicy.webViewLink
                    ? selectedPolicy.webViewLink.replace("/view", "/preview")
                    : `${API_URL}/view/${selectedPolicy.file}`
                }
                width="100%"
                height="100%"
                style={{ border: "none", borderRadius: "0 0 16px 16px" }}
                title={selectedPolicy.file}
              />
            </div>
          </motion.div>
        </motion.div>
      )}

      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        accept=".pdf"
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) handleFileUpload(e.target.files[0]);
        }}
        className="hidden"
      />
    </div>
  );
}
