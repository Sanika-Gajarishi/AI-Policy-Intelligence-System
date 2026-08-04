import { getToken } from "./auth";

const API_URL = process.env.REACT_APP_API_URL;
function requireToken() {
  const token = getToken();
  if (!token) {
    throw new Error("Not authenticated");
  }
  return token;
}

function withTokenQuery(path) {
  const token = requireToken();
  const separator = path.includes("?") ? "&" : "?";
  return `${API_URL}${path}${separator}token=${encodeURIComponent(token)}`;
}

async function parseResponse(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message =
      typeof data.detail === "string"
        ? data.detail
        : data.message || "Request failed";
    const error = new Error(message);
    error.status = res.status;
    error.detail = data.detail;
    throw error;
  }
  return data;
}

export async function fetchScrapeQueueCount() {
  const res = await fetch(withTokenQuery("/scrape-queue/count"));
  return parseResponse(res);
}

export async function fetchScrapeQueue() {
  const res = await fetch(withTokenQuery("/scrape-queue"));
  return parseResponse(res);
}

export async function runScraper(options = {}) {
  const { state, year, month, day, fast = true } = options;
  const params = new URLSearchParams();
  if (state && state !== "All States") params.set("state", state);
  if (year !== null && year !== undefined) params.set("year", year);
  if (month) params.set("month", month);
  if (day !== null && day !== undefined) params.set("day", day);
  params.set("fast", fast ? "true" : "false");
  const query = params.toString();
  const path = query ? `/scrape?${query}` : "/scrape";
  const res = await fetch(withTokenQuery(path));
  return parseResponse(res);
}

export async function acceptScrapedDocument(id, options = {}) {
  const token = requireToken();
  const res = await fetch(`${API_URL}/accept-scraped`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, token, force: options.force === true , filename: options.filename || null, }),
  });
  return parseResponse(res);
}

export async function rejectScrapedDocument(id) {
  const token = requireToken();
  const res = await fetch(`${API_URL}/reject-scraped`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, token }),
  });
  return parseResponse(res);
}

export async function clearScrapeQueue() {
  const res = await fetch(withTokenQuery("/scrape-queue/clear"), {
    method: "POST",
  });
  return parseResponse(res);
}