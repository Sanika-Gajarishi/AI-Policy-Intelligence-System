import { useState, useEffect, useMemo, useRef } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Check,
  Eye,
  Download,
  Loader2,
  ChevronUp,
  ChevronDown,
  Pencil,
  ChevronDown as ChevronDownIcon,
} from "lucide-react";
import { Button } from "./ui/Button";
import { Select } from "./ui/Select";
import { Input } from "./ui/Input";
import {
  ENERGY_TYPE_FILTER_OPTIONS,
  matchesEnergyTypeFilter,
  normalizePowerTypeForFilter,
} from "../constants/energyTypeOptions";

// ── Constants ─────────────────────────────────────────────────────────────────

const MONTHS = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
];

const YEAR_OPTIONS_LIST = [
  "1990","1991","1992","1993","1994","1995","1996","1997","1998","1999",
  "2000","2001","2002","2003","2004","2005","2006","2007","2008","2009",
  "2010","2011","2012","2013","2014","2015","2016","2017","2018","2019",
  "2020","2021","2022","2023","2024","2025","2026","2027","2028","2029",
  "2030","2031","2032","2033","2034","2035","2036","2037","2038","2039",
  "2040","2041","2042","2043","2044","2045","2046","2047","2048","2049","2050",
];

const STATE_LIST = [
  "Andhra Pradesh","Central","Gujarat","Haryana","Karnataka",
  "Madhya Pradesh","Maharashtra","Punjab","Rajasthan","Tamil Nadu",
  "Uttar Pradesh",
];

const DOC_TYPE_LIST = [
  "Act","Circular","Corrigendum","Electricity Plan","Gazette",
  "General","Notification","Order","Policy","Regulation","Road Map",
];

// Energy type options — pull just the value strings (skip the "All" blank entry)
const ENERGY_TYPE_LIST = ENERGY_TYPE_FILTER_OPTIONS
  .filter((o) => o.value !== "")
  .map((o) => ({ label: o.label, value: o.value }));

const CATEGORY_BADGE = {
  Regulation: "bg-blue-100 text-blue-800 border-blue-200",
  Order: "bg-orange-100 text-orange-800 border-orange-200",
  Policy: "bg-green-100 text-green-800 border-green-200",
  Notification: "bg-purple-100 text-purple-800 border-purple-200",
  Circular: "bg-teal-100 text-teal-800 border-teal-200",
  Tender: "bg-rose-100 text-rose-800 border-rose-200",
  Gazette: "bg-amber-100 text-amber-800 border-amber-200",
  Roadmap: "bg-emerald-100 text-emerald-800 border-emerald-200",
  General: "bg-gray-100 text-gray-700 border-gray-200",
};

const POWER_TYPE_BADGES = {
  BESS: { label: "BESS", className: "bg-green-800 text-white border-green-900" },
  "Green Hydrogen": { label: "Green H₂", className: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  "Integrated Renewable": { label: "Integrated", className: "bg-teal-100 text-teal-800 border-teal-200" },
  "Renewable Energy": { label: "Renewable", className: "bg-green-100 text-green-800 border-green-200" },
  Biomass: { label: "Biomass", className: "bg-lime-100 text-lime-900 border-lime-200" },
  "Clean Energy": { label: "Clean", className: "bg-sky-100 text-sky-800 border-sky-200" },
  Solar: { label: "Solar", className: "bg-yellow-100 text-yellow-900 border-yellow-200" },
  Wind: { label: "Wind", className: "bg-blue-100 text-blue-800 border-blue-200" },
  General: { label: "General", className: "bg-gray-100 text-gray-700 border-gray-200" },
  Transmission: { label: "Transmission", className: "bg-indigo-50 text-indigo-700 border-indigo-200" },
  Grid: { label: "Grid", className: "bg-indigo-100 text-indigo-800 border-indigo-200" },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function getPowerTypeBadge(powerType) {
  const normalized = normalizePowerTypeForFilter(powerType);
  return POWER_TYPE_BADGES[normalized] || { label: normalized, className: POWER_TYPE_BADGES.General.className };
}

function parseDuplicateFilename(detail) {
  if (!detail) return "";
  if (typeof detail === "object") return detail.existing_filename || detail.drive_file_name || "";
  const text = String(detail);
  const match = text.match(/already exists in the system:\s*(.+?)\./i);
  return match ? match[1].trim() : "";
}

function getMonthFromScrapedAt(scrapedAt) {
  if (!scrapedAt) return null;
  const d = new Date(scrapedAt);
  if (Number.isNaN(d.getTime())) return null;
  return MONTHS[d.getMonth()];
}

function getMonthFromPublicationDate(publicationDate) {
  if (!publicationDate) return null;
  const parts = publicationDate.split("-");
  if (parts.length >= 2) {
    const monthNum = parseInt(parts[1], 10);
    if (!Number.isNaN(monthNum) && monthNum >= 1 && monthNum <= 12) return MONTHS[monthNum - 1];
  }
  return null;
}

function getDayFromPublicationDate(publicationDate) {
  if (!publicationDate) return null;
  const parts = publicationDate.split("-");
  if (parts.length >= 3) {
    const day = parseInt(parts[2], 10);
    return Number.isNaN(day) ? null : day;
  }
  return null;
}

function monthsMatch(a, b) {
  if (!a || !b) return false;
  return a.toLowerCase().slice(0, 3) === b.toLowerCase().slice(0, 3);
}

function matchesPublicationDateFilter(item, filters) {
  if (!filters) return true;
  const { year, month, day } = filters;
  const hasYear = year !== null && year !== undefined && year !== "";
  const hasMonth = Boolean(month);
  const hasDay = day !== null && day !== undefined && day !== "";
  if (!hasYear && !hasMonth && !hasDay) return true;
  if (hasYear) {
    const itemYear = Number(item.year);
    if (Number.isNaN(itemYear) || itemYear !== Number(year)) return false;
  }
  if (hasMonth) {
    const itemMonth =
      item.month ||
      getMonthFromPublicationDate(item.publication_date) ||
      getMonthFromScrapedAt(item.scraped_at);
    if (!monthsMatch(itemMonth, month)) return false;
  }
  if (hasDay) {
    const itemDay = item.day ?? getDayFromPublicationDate(item.publication_date);
    if (itemDay == null || Number(itemDay) !== Number(day)) return false;
  }
  return true;
}

const getDisplayDate = (item) => {
  const pub = item.publication_date;
  if (!pub) return item.scraped_at?.slice(0, 10) || "Unknown";
  const parts = pub.split("-");
  if (parts.length === 3) return `${parts[2]}-${parts[1]}-${parts[0]}`;
  if (parts.length === 2) return `${parts[1]}-${parts[0]}`;
  return pub;
};

function truncateTitle(title, max = 120) {
  if (!title) return "";
  if (title.length <= max) return title;
  return `${title.slice(0, max)}...`;
}

function badgeClass(map, key) {
  return map[key] || map.General;
}

function validateFilename(filename) {
  if (!filename || !filename.trim()) return "Filename cannot be empty.";
  if (!filename.toLowerCase().endsWith(".pdf")) return "Filename must end with .pdf";
  const parts = filename.replace(/\.pdf$/i, "").split("_");
  if (parts.length < 4) return "Filename must follow: State_EnergyType_DocumentType_Year.pdf";
  const year = parts[parts.length - 1];
  if (!/^\d{4}$/.test(year)) return "Last part before .pdf must be a 4-digit year (e.g. 2025).";
  return null;
}

// ── Multi-select checkbox dropdown ────────────────────────────────────────────
/**
 * A dropdown that shows a list of items with individual checkboxes.
 * When nothing is checked it shows "All <label>" as the trigger text.
 *
 * Props:
 *   label        – display name for the "All …" placeholder, e.g. "Years"
 *   options      – array of strings  OR  array of { label, value }
 *   selected     – Set of selected values
 *   onChange     – (newSet) => void
 *   width        – tailwind width class, default "w-44"
 *   maxHeight    – max-height of the list, default "max-h-56"
 *   searchable   – show a search box inside the dropdown (useful for long lists)
 */
function MultiCheckboxDropdown({
  label,
  options,
  selected,
  onChange,
  width = "w-44",
  maxHeight = "max-h-56",
  searchable = false,
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef(null);

  // normalise options to { label, value }
  const normalised = options.map((o) =>
    typeof o === "string" ? { label: o, value: o } : o
  );

  const filtered = searchable && search.trim()
    ? normalised.filter((o) => o.label.toLowerCase().includes(search.trim().toLowerCase()))
    : normalised;

  // close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (!containerRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const allSelected = selected.size === 0; // empty set = "All"
  const toggle = (value) => {
    const next = new Set(selected);
    if (next.has(value)) next.delete(value); else next.add(value);
    onChange(next);
  };
  const selectAll = () => onChange(new Set());

  // build trigger label
  let triggerText;
  if (allSelected) {
    triggerText = `All ${label}`;
  } else if (selected.size === 1) {
    const single = normalised.find((o) => selected.has(o.value));
    triggerText = single ? single.label : `1 selected`;
  } else {
    triggerText = `${selected.size} selected`;
  }

  return (
    <div ref={containerRef} className={`relative ${width}`}>
      {/* Trigger button — matches the height/style of the existing Select inputs */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`
          w-full h-9 flex items-center justify-between gap-1
          border border-gray-300 rounded-md bg-white
          px-3 text-sm text-gray-700
          hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-[#1a2744]
          ${open ? "ring-2 ring-[#1a2744] border-[#1a2744]" : ""}
        `}
      >
        <span className="truncate">{triggerText}</span>
        <ChevronDown className={`w-4 h-4 shrink-0 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {/* Dropdown panel */}
      {open && (
        <div
          className={`
            absolute top-10 left-0 z-50 bg-white border border-gray-200
            rounded-xl shadow-xl w-full min-w-max
          `}
          style={{ minWidth: "100%" }}
        >
          {searchable && (
            <div className="px-3 pt-3 pb-2">
              <input
                type="text"
                placeholder={`Search ${label.toLowerCase()}…`}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-2 py-1 text-xs
                           focus:outline-none focus:ring-2 focus:ring-[#1a2744]"
                autoFocus
              />
            </div>
          )}

          <div className={`overflow-y-auto ${maxHeight} py-1`}>
            {/* "All" row */}
            <label className="flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-gray-50">
              <input
                type="checkbox"
                className="accent-[#1a2744] w-3.5 h-3.5"
                checked={allSelected}
                onChange={selectAll}
                readOnly={false}
              />
              <span className="text-sm text-gray-700 font-medium">All {label}</span>
            </label>

            {/* Divider */}
            <div className="border-t border-gray-100 mx-2 my-0.5" />

            {filtered.map((opt) => (
              <label
                key={opt.value}
                className="flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-gray-50"
              >
                <input
                  type="checkbox"
                  className="accent-[#1a2744] w-3.5 h-3.5"
                  checked={selected.has(opt.value)}
                  onChange={() => toggle(opt.value)}
                />
                <span className="text-sm text-gray-700 truncate">{opt.label}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ScrapedDocumentsModal({
  open,
  onClose,
  scrapeQueue = [],
  scrapeRunning = false,
  scrapeActionLoading = {},
  onRunScraper,
  onAcceptScraped,
  onRejectScraped,
  lastScrapeSession,
}) {
  const [localQueue, setLocalQueue] = useState([]);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  // ── Multi-select filter state (Sets; empty Set = "All") ──
  const [yearFilter, setYearFilter] = useState(new Set());
  const [stateFilter, setStateFilter] = useState(new Set());
  const [monthFilter, setMonthFilter] = useState(new Set());
  const [typeFilter, setTypeFilter] = useState(new Set());
  const [energyTypeFilter, setEnergyTypeFilter] = useState(new Set());

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [dateSort, setDateSort] = useState("desc");
  const [duplicateDialog, setDuplicateDialog] = useState(null);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [activeScrapeFilters, setActiveScrapeFilters] = useState(null);
  const [reviewDialog, setReviewDialog] = useState(null);
  const [filenameError, setFilenameError] = useState("");
  const [isUploadingEditedFile, setIsUploadingEditedFile] = useState(false);

  // ── Scrape date picker state ──
  // Now supports multi-select checkboxes for year + month
  const [scrapeYears, setScrapeYears] = useState(new Set());   // Set of year strings
  const [scrapeMonths, setScrapeMonths] = useState(new Set()); // Set of month strings
  const [scrapeDay, setScrapeDay] = useState("");

  useEffect(() => {
    const pending = (scrapeQueue || []).filter((item) => item.status === "pending");
    setLocalQueue(pending);
    if (!scrapeRunning) setPage(1);
  }, [scrapeQueue, scrapeRunning]);

  useEffect(() => {
    setPage(1);
  }, [rowsPerPage, yearFilter, stateFilter, monthFilter, typeFilter, energyTypeFilter, search, dateSort]);

  useEffect(() => {
    if (!showDatePicker) return;
    const handler = (e) => {
      if (!e.target.closest("[data-datepicker]")) setShowDatePicker(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showDatePicker]);

  // ── Filtered list ──
  const filtered = useMemo(() => {
    let list = [...localQueue];

    if (activeScrapeFilters && lastScrapeSession) {
      list = list.filter((item) => item.scrape_session === lastScrapeSession);
      list = list.filter((item) => matchesPublicationDateFilter(item, activeScrapeFilters));
    }

    // State — multi-select
    if (stateFilter.size > 0) {
      list = list.filter((item) => stateFilter.has(item.state));
    }

    // Year — multi-select
    if (yearFilter.size > 0) {
      list = list.filter((item) => yearFilter.has(String(item.year)));
    }

    // Month — multi-select
    if (monthFilter.size > 0) {
      list = list.filter((item) => {
        const pubMonth =
          item.month ||
          getMonthFromPublicationDate(item.publication_date) ||
          getMonthFromScrapedAt(item.scraped_at);
        // check if any selected month matches
        return [...monthFilter].some((m) => monthsMatch(pubMonth, m));
      });
    }

    // Document type — multi-select
    if (typeFilter.size > 0) {
      list = list.filter((item) => typeFilter.has(item.category || "General"));
    }

    // Energy type — multi-select
    if (energyTypeFilter.size > 0) {
      list = list.filter((item) =>
        [...energyTypeFilter].some((val) => matchesEnergyTypeFilter(item, val))
      );
    }

    // Text search
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((item) => (item.title || "").toLowerCase().includes(q));
    }

    list.sort((a, b) => {
      const ta = new Date(a.scraped_at || 0).getTime();
      const tb = new Date(b.scraped_at || 0).getTime();
      return dateSort === "asc" ? ta - tb : tb - ta;
    });

    return list;
  }, [
    localQueue,
    activeScrapeFilters,
    lastScrapeSession,
    yearFilter,
    stateFilter,
    monthFilter,
    typeFilter,
    energyTypeFilter,
    search,
    dateSort,
  ]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / rowsPerPage));
  const safePage = Math.min(page, totalPages);
  const pageItems = filtered.slice((safePage - 1) * rowsPerPage, safePage * rowsPerPage);

  const clearFilters = () => {
    setRowsPerPage(10);
    setYearFilter(new Set());
    setStateFilter(new Set());
    setMonthFilter(new Set());
    setTypeFilter(new Set());
    setEnergyTypeFilter(new Set());
    setSearch("");
    setActiveScrapeFilters(null);
    setPage(1);
  };

  const toggleDateSort = () => setDateSort((s) => (s === "asc" ? "desc" : "asc"));

  const handleAccept = async (id, options = {}) => {
    try {
      await onAcceptScraped?.(id, options);
      setLocalQueue((prev) => prev.filter((item) => item.id !== id));
    } catch (error) {
      if (error?.status === 409) {
        const existingFilename =
          parseDuplicateFilename(error.detail) || parseDuplicateFilename(error.message);
        setDuplicateDialog({ id, existingFilename });
        return;
      }
      throw error;
    }
  };

  const handleAcceptAnyway = async () => {
    if (!duplicateDialog?.id) return;
    const { id } = duplicateDialog;
    setDuplicateDialog(null);
    try {
      await onAcceptScraped?.(id, { force: true });
      setLocalQueue((prev) => prev.filter((item) => item.id !== id));
    } catch { /* parent refresh restores queue */ }
  };

  const handleReject = async (id) => {
    setLocalQueue((prev) => prev.filter((item) => item.id !== id));
    try {
      await onRejectScraped?.(id);
    } catch { /* parent refresh restores queue */ }
  };

  // ── Scrape Now handler ──
  const handleScrapeNow = () => {
    setShowDatePicker(false);

    // Reset display filters
    setStateFilter(new Set());
    setTypeFilter(new Set());
    setEnergyTypeFilter(new Set());

    const now = new Date();
    const todayYear = String(now.getFullYear());
    const todayMonth = MONTHS[now.getMonth()];
    const todayDay = now.getDate();

    const noDateChosen = scrapeYears.size === 0 && scrapeMonths.size === 0 && !scrapeDay;

    // For the backend call we send the first selected value (or today's)
    const chosenYear = noDateChosen ? todayYear : (scrapeYears.size > 0 ? [...scrapeYears][0] : null);
    const chosenMonth = noDateChosen ? todayMonth : (scrapeMonths.size > 0 ? [...scrapeMonths][0] : null);
    const chosenDay = noDateChosen ? todayDay : (scrapeDay ? parseInt(scrapeDay, 10) : null);

    const scrapeFilters = {
      year: chosenYear ? parseInt(chosenYear, 10) : null,
      month: chosenMonth || null,
      day: chosenDay,
    };

    setActiveScrapeFilters(scrapeFilters);

    // Sync display year filter
    if (scrapeFilters.year != null) {
      setYearFilter(new Set([String(scrapeFilters.year)]));
    } else {
      setYearFilter(new Set());
    }
    if (scrapeFilters.month) {
      setMonthFilter(new Set([scrapeFilters.month]));
    } else {
      setMonthFilter(new Set());
    }

    onRunScraper?.("", scrapeFilters.year, scrapeFilters.month, scrapeFilters.day);
  };

  // ── Datepicker badge label ──
  const scrapeBadgeLabel = (() => {
    const parts = [];
    if (scrapeMonths.size === 1) parts.push([...scrapeMonths][0].slice(0, 3));
    else if (scrapeMonths.size > 1) parts.push(`${scrapeMonths.size} months`);
    if (scrapeYears.size === 1) parts.push([...scrapeYears][0]);
    else if (scrapeYears.size > 1) parts.push(`${scrapeYears.size} years`);
    return parts.join(" ");
  })();

  if (!open || typeof document === "undefined") return null;

  const modal = (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="absolute inset-0 bg-black/50"
            onClick={onClose}
            aria-hidden
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="scraped-docs-title"
            className="relative flex flex-col bg-white rounded-lg shadow-2xl overflow-hidden"
            style={{ width: "90vw", height: "85vh", maxWidth: "1400px" }}
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* ── Header ── */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white shrink-0">
              <div>
                <h2 id="scraped-docs-title" className="text-xl font-bold text-gray-900">
                  New Scraped Documents
                </h2>
                <p className="text-sm text-gray-600 mt-0.5">
                  Total: {filtered.length} document{filtered.length !== 1 ? "s" : ""}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  * Date column shows publication date from the PDF, not scrape date
                </p>
              </div>
              <div className="flex items-center gap-2">
                {/* ── Date picker + Scrape Now ── */}
                <div className="relative flex items-center gap-2" data-datepicker>
                  {/* Calendar toggle */}
                  <button
                    onClick={() => setShowDatePicker((prev) => !prev)}
                    title="Filter by date"
                    className="h-9 w-9 flex items-center justify-center rounded-lg border border-[#1a2744] text-[#1a2744] hover:bg-[#1a2744] hover:text-white transition-colors"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none"
                      viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round"
                        d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </button>

                  {/* Date picker dropdown — now with checkboxes */}
                  {showDatePicker && (
                    <div className="absolute top-11 right-0 z-50 bg-white border border-gray-200 rounded-xl shadow-xl p-4 w-80">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                        Scrape by Publication Date
                      </p>

                      {/* Year checkboxes */}
                      <div className="mb-3">
                        <label className="text-xs font-medium text-gray-600 block mb-1">Year</label>
                        <MultiCheckboxDropdown
                          label="Years"
                          options={[...YEAR_OPTIONS_LIST].reverse()} // newest first
                          selected={scrapeYears}
                          onChange={setScrapeYears}
                          width="w-full"
                          maxHeight="max-h-40"
                          searchable
                        />
                      </div>

                      {/* Month checkboxes */}
                      <div className="mb-3">
                        <label className="text-xs font-medium text-gray-600 block mb-1">Month</label>
                        <MultiCheckboxDropdown
                          label="Months"
                          options={MONTHS}
                          selected={scrapeMonths}
                          onChange={setScrapeMonths}
                          width="w-full"
                          maxHeight="max-h-40"
                        />
                      </div>

                      {/* Day (unchanged — plain input) */}
                      <div className="mb-4">
                        <label className="text-xs font-medium text-gray-600 block mb-1">
                          Day <span className="text-gray-400 font-normal">(optional)</span>
                        </label>
                        <input
                          type="number"
                          min={1}
                          max={31}
                          placeholder="e.g. 15"
                          value={scrapeDay}
                          onChange={(e) => setScrapeDay(e.target.value)}
                          className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a2744]"
                        />
                      </div>

                      {/* Summary */}
                      <div className="text-xs text-gray-500 mb-3 bg-gray-50 rounded-lg px-3 py-2">
                        Will scrape:{" "}
                        <span className="font-semibold text-gray-700">
                          {scrapeDay ? `${scrapeDay} ` : ""}
                          {scrapeMonths.size === 0
                            ? "Any Month"
                            : scrapeMonths.size === 1
                            ? [...scrapeMonths][0]
                            : `${scrapeMonths.size} months`}{" "}
                          {scrapeYears.size === 0
                            ? "Any Year"
                            : scrapeYears.size === 1
                            ? [...scrapeYears][0]
                            : `${scrapeYears.size} years`}
                        </span>
                      </div>

                      {/* Clear */}
                      <button
                        onClick={() => {
                          setScrapeYears(new Set());
                          setScrapeMonths(new Set());
                          setScrapeDay("");
                          setActiveScrapeFilters(null);
                        }}
                        className="text-xs text-gray-400 hover:text-gray-600 underline mb-3 block"
                      >
                        Clear date filter
                      </button>
                    </div>
                  )}

                  {/* Scrape Now button */}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleScrapeNow}
                    disabled={scrapeRunning}
                    className="border-[#1a2744] text-[#1a2744] hover:bg-[#1a2744] hover:text-white"
                  >
                    {scrapeRunning ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Scraping...
                      </>
                    ) : (
                      <>
                        Scrape Now
                        {scrapeBadgeLabel && (
                          <span className="ml-1.5 bg-[#1a2744] text-white text-[10px] px-1.5 py-0.5 rounded-full font-bold">
                            {scrapeBadgeLabel}
                          </span>
                        )}
                      </>
                    )}
                  </Button>
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  className="h-9 w-9 p-0"
                  onClick={onClose}
                  aria-label="Close"
                >
                  <X className="w-5 h-5" />
                </Button>
              </div>
            </div>

            {/* ── Filters ── */}
            <div className="px-6 py-3 border-b border-gray-200 bg-gray-50 shrink-0">
              <div className="flex flex-wrap items-end gap-3">
                {/* Rows per page — unchanged plain Select */}
                <div className="w-28">
                  <label className="text-xs font-medium text-gray-600 block mb-1">Rows per page</label>
                  <Select
                    value={rowsPerPage}
                    onChange={(e) => setRowsPerPage(Number(e.target.value))}
                    className="h-9 text-sm bg-white"
                  >
                    <option value={10}>10</option>
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </Select>
                </div>

                {/* Year — multi-select checkbox dropdown */}
                <div className="w-36">
                  <label className="text-xs font-medium text-gray-600 block mb-1">Year</label>
                  <MultiCheckboxDropdown
                    label="Years"
                    options={[...YEAR_OPTIONS_LIST].reverse()}
                    selected={yearFilter}
                    onChange={setYearFilter}
                    width="w-full"
                    maxHeight="max-h-56"
                    searchable
                  />
                </div>

                {/* State — multi-select checkbox dropdown */}
                <div className="w-44">
                  <label className="text-xs font-medium text-gray-600 block mb-1">State</label>
                  <MultiCheckboxDropdown
                    label="States"
                    options={STATE_LIST}
                    selected={stateFilter}
                    onChange={setStateFilter}
                    width="w-full"
                    maxHeight="max-h-56"
                  />
                </div>

                {/* Month — multi-select checkbox dropdown */}
                <div className="w-40">
                  <label className="text-xs font-medium text-gray-600 block mb-1">Month</label>
                  <MultiCheckboxDropdown
                    label="Months"
                    options={MONTHS}
                    selected={monthFilter}
                    onChange={setMonthFilter}
                    width="w-full"
                    maxHeight="max-h-56"
                  />
                </div>

                {/* Document Type — multi-select checkbox dropdown */}
                <div className="w-44">
                  <label className="text-xs font-medium text-gray-600 block mb-1">Document Type</label>
                  <MultiCheckboxDropdown
                    label="Types"
                    options={DOC_TYPE_LIST}
                    selected={typeFilter}
                    onChange={setTypeFilter}
                    width="w-full"
                    maxHeight="max-h-56"
                  />
                </div>

                {/* Energy Type — multi-select checkbox dropdown */}
                <div className="w-52 min-w-[12rem]">
                  <label className="text-xs font-medium text-gray-600 block mb-1">Energy Type</label>
                  <MultiCheckboxDropdown
                    label="Energy Types"
                    options={ENERGY_TYPE_LIST}
                    selected={energyTypeFilter}
                    onChange={setEnergyTypeFilter}
                    width="w-full"
                    maxHeight="max-h-56"
                  />
                </div>

                {/* Search */}
                <div className="flex-1 min-w-[180px]">
                  <label className="text-xs font-medium text-gray-600 block mb-1">Search</label>
                  <Input
                    type="text"
                    placeholder="Search documents..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="h-9 text-sm bg-white"
                  />
                </div>

                <button
                  type="button"
                  onClick={clearFilters}
                  className="text-xs text-blue-600 hover:text-blue-800 underline pb-2"
                >
                  Clear Filters
                </button>
              </div>
            </div>

            {/* ── Table ── */}
            <div className="flex-1 overflow-auto min-h-0">
              {scrapeRunning ? (
                <div className="flex flex-col items-center justify-center h-full py-20 text-gray-600">
                  <Loader2 className="w-10 h-10 animate-spin text-[#1a2744] mb-4" />
                  <p className="text-sm font-medium">Scraping websites, please wait...</p>
                </div>
              ) : filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full py-20 text-center px-8">
                  <p className="text-gray-700 font-medium">
                    {activeScrapeFilters
                      ? "No documents found for the selected publication date. Try a different date or clear filters."
                      : "No new documents. Click 'Scrape Now' to check for updates."}
                  </p>
                </div>
              ) : (
                <table className="w-full border-collapse text-sm">
                  <thead className="sticky top-0 z-10">
                    <tr className="bg-[#1a2744] text-white">
                      <th className="px-3 py-3 text-left font-semibold border-r border-[#2a3a5c] w-14">S.No.</th>
                      <th
                        className="px-3 py-3 text-left font-semibold border-r border-[#2a3a5c] w-28 cursor-pointer select-none hover:bg-[#243456]"
                        onClick={toggleDateSort}
                      >
                        <span className="inline-flex items-center gap-1">
                          Date
                          {dateSort === "asc"
                            ? <ChevronUp className="w-4 h-4" />
                            : <ChevronDown className="w-4 h-4" />}
                        </span>
                      </th>
                      <th className="px-3 py-3 text-left font-semibold border-r border-[#2a3a5c] w-32">Doc Type</th>
                      <th className="px-3 py-3 text-left font-semibold border-r border-[#2a3a5c] w-32">Energy Type</th>
                      <th className="px-3 py-3 text-left font-semibold border-r border-[#2a3a5c] w-28">State</th>
                      <th className="px-3 py-3 text-left font-semibold border-r border-[#2a3a5c] min-w-[200px]">Description</th>
                      <th className="px-3 py-3 text-center font-semibold w-36">Attachments</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageItems.map((item, index) => {
                      const sno = (safePage - 1) * rowsPerPage + index + 1;
                      const title = item.title || "Untitled document";
                      const category = item.category || "General";
                      const powerBadge = getPowerTypeBadge(item.power_type || "General");
                      const isNewThisSession =
                        lastScrapeSession && item.scrape_session === lastScrapeSession;
                      return (
                        <tr
                          key={item.id}
                          className={`${
                            index % 2 === 0
                              ? "bg-white border-b border-gray-200"
                              : "bg-gray-50 border-b border-gray-200"
                          } ${isNewThisSession ? "border-l-4 border-l-green-500 bg-green-50" : ""}`}
                        >
                          <td className="px-3 py-3 border-r border-gray-200 text-gray-700">{sno}</td>
                          <td
                            className="px-3 py-3 border-r border-gray-200 text-gray-800 whitespace-nowrap"
                            title={`Published: ${item.publication_date || "Unknown"} | Scraped: ${item.scraped_at?.slice(0, 10)}`}
                          >
                            {getDisplayDate(item)}
                          </td>
                          <td className="px-3 py-3 border-r border-gray-200">
                            <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium border ${badgeClass(CATEGORY_BADGE, category)}`}>
                              {category}
                            </span>
                          </td>
                          <td className="px-3 py-3 border-r border-gray-200">
                            <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium border ${powerBadge.className}`}>
                              {powerBadge.label}
                            </span>
                          </td>
                          <td className="px-3 py-3 border-r border-gray-200 text-gray-800">{item.state || "—"}</td>
                          <td className="px-3 py-3 border-r border-gray-200 text-gray-800" title={title}>
                            <div className="flex flex-col gap-1">
                              <span>{truncateTitle(title)}</span>
                              {item.already_in_system || item.duplicate_of ? (
                                <span className="w-fit rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800">
                                  Already in system
                                </span>
                              ) : null}
                            </div>
                          </td>
                          <td className="px-3 py-3 text-center align-middle">
                            <div className="flex flex-col items-center gap-2">
                              <div className="flex items-center justify-center gap-1">
                                {item.source_url ? (
                                  <>
                                    <a
                                      href={item.source_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center justify-center w-8 h-8 rounded border border-gray-300 bg-white hover:bg-blue-50 text-gray-700"
                                      title="View PDF"
                                    >
                                      <Eye className="w-4 h-4" />
                                    </a>
                                    <a
                                      href={item.source_url}
                                      download
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center justify-center w-8 h-8 rounded border border-gray-300 bg-white hover:bg-blue-50 text-gray-700"
                                      title="Download PDF"
                                    >
                                      <Download className="w-4 h-4" />
                                    </a>
                                  </>
                                ) : (
                                  <span className="text-xs text-gray-400">N/A</span>
                                )}
                              </div>
                              <div className="flex items-center gap-1">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 px-2 text-xs hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700"
                                  onClick={() => {
                                    setFilenameError("");
                                    setIsUploadingEditedFile(false);
                                    setReviewDialog({
                                      id: item.id,
                                      filename: item.file || item.filename || "",
                                      item,
                                    });
                                  }}
                                >
                                  <Pencil className="w-3 h-3 mr-0.5" />
                                  Edit
                                </Button>
                                <Button
                                  size="sm"
                                  disabled={scrapeActionLoading[item.id]}
                                  className="h-7 px-2 text-xs bg-green-600 hover:bg-green-700 text-white"
                                  onClick={() => handleAccept(item.id)}
                                >
                                  {scrapeActionLoading[item.id] ? (
                                    <><Loader2 className="w-3 h-3 mr-1 animate-spin" />Processing...</>
                                  ) : (
                                    <><Check className="w-3 h-3 mr-0.5" />Accept</>
                                  )}
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={scrapeActionLoading[item.id]}
                                  className="h-7 px-2 text-xs hover:bg-red-50 hover:border-red-300 hover:text-red-700"
                                  onClick={() => handleReject(item.id)}
                                >
                                  <X className="w-3 h-3 mr-0.5" />
                                  Reject
                                </Button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            {/* ── Pagination ── */}
            {!scrapeRunning && filtered.length > 0 && (
              <div className="flex items-center justify-center gap-4 px-6 py-3 border-t border-gray-200 bg-gray-50 shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={safePage <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </Button>
                <span className="text-sm text-gray-700 font-medium">
                  Page {safePage} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={safePage >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                </Button>
              </div>
            )}

            {/* ── Duplicate Dialog ── */}
            {duplicateDialog && (
              <div className="absolute inset-0 z-[110] flex items-center justify-center bg-black/40 p-6">
                <div
                  role="alertdialog"
                  aria-labelledby="duplicate-doc-title"
                  className="max-w-md w-full rounded-lg bg-white shadow-xl border border-amber-200 p-6"
                  onClick={(e) => e.stopPropagation()}
                >
                  <h3 id="duplicate-doc-title" className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                    <span aria-hidden>⚠️</span> Duplicate Document
                  </h3>
                  <p className="mt-3 text-sm text-gray-700">This document may already exist in your system.</p>
                  {duplicateDialog.existingFilename ? (
                    <p className="mt-2 text-sm font-mono text-gray-900 bg-gray-50 border border-gray-200 rounded px-3 py-2 break-all">
                      {duplicateDialog.existingFilename}
                    </p>
                  ) : null}
                  <p className="mt-3 text-sm text-gray-700">Do you want to accept it anyway?</p>
                  <div className="mt-6 flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setDuplicateDialog(null)}
                      disabled={scrapeActionLoading[duplicateDialog?.id]}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      className="bg-amber-600 hover:bg-amber-700 text-white"
                      onClick={handleAcceptAnyway}
                      disabled={scrapeActionLoading[duplicateDialog?.id]}
                    >
                      {scrapeActionLoading[duplicateDialog?.id] ? (
                        <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Accepting...</>
                      ) : "Accept Anyway"}
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* ── Review / Edit Filename Dialog ── */}
            {reviewDialog && (
              <div className="absolute inset-0 z-[110] flex items-center justify-center bg-black/40 p-6">
                <div
                  className="max-w-lg w-full rounded-lg bg-white shadow-xl border border-blue-200 p-6"
                  onClick={(e) => e.stopPropagation()}
                >
                  <h3 className="text-lg font-semibold text-gray-900">Correct Filename</h3>
                  <p className="mt-2 text-sm text-gray-600">
                    Correct the filename before uploading the document.
                  </p>
                  <div className="mt-4 rounded-md border border-blue-200 bg-blue-50 p-3">
                    <p className="text-sm font-medium text-blue-900">Filename format</p>
                    <p className="mt-1 text-xs text-blue-700">State_EnergyType_DocumentType_Year.pdf</p>
                    <p className="mt-2 text-xs text-gray-600">
                      Example: <span className="font-medium">Maharashtra_Solar_Policy_2025.pdf</span>
                    </p>
                  </div>
                  <div className="mt-5">
                    <label className="block text-sm font-medium text-gray-700 mb-2">Filename</label>
                    <Input
                      value={reviewDialog.filename}
                      onChange={(e) => {
                        setFilenameError("");
                        setReviewDialog((prev) => ({ ...prev, filename: e.target.value }));
                      }}
                    />
                    {filenameError && (
                      <p className="mt-2 text-xs text-red-600">{filenameError}</p>
                    )}
                  </div>
                  <div className="mt-6 flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={isUploadingEditedFile}
                      onClick={() => { setFilenameError(""); setReviewDialog(null); }}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      className="bg-green-600 hover:bg-green-700 text-white"
                      disabled={isUploadingEditedFile}
                      onClick={async () => {
                        const filename = reviewDialog.filename.trim();
                        const validationError = validateFilename(filename);
                        if (validationError) { setFilenameError(validationError); return; }
                        const { id } = reviewDialog;
                        try {
                          setIsUploadingEditedFile(true);
                          await handleAccept(id, { filename });
                          setReviewDialog(null);
                        } catch (err) {
                          setFilenameError(err?.message || "Failed to upload document. Please try again.");
                        } finally {
                          setIsUploadingEditedFile(false);
                        }
                      }}
                    >
                      {isUploadingEditedFile ? (
                        <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Uploading...</>
                      ) : "Accept"}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  return createPortal(modal, document.body);
}
