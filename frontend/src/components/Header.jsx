import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bell, Settings, LogOut, MoreVertical } from "lucide-react";
import { Button } from "./ui/Button";
import ScrapedDocumentsModal from "./ScrapedDocumentsModal";

export default function Header({
  user,
  onLogout,
  language,
  translations,
  setLanguage,
  scrapeQueue = [],
  scrapeQueueCount = 0,
  scrapeActionLoading = false,
  scrapeRunning = false,
  onAcceptScraped,
  onRejectScraped,
  onRefreshScrapeQueue,
  onRunScraper,
}) {
  const [showSettingsDropdown, setShowSettingsDropdown] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);

  const t = translations;

  const handleBellClick = () => {
    const next = !showNotifications;
    setShowNotifications(next);
    if (next && onRefreshScrapeQueue) {
      onRefreshScrapeQueue();
    }
  };

  const handleCloseModal = () => {
    setShowNotifications(false);
  };

  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50"
    >
      <div className="w-full max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-3">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-white">
                <path
                  d="M3 12h18m-9-9v18"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
                <circle cx="12" cy="12" r="3" fill="currentColor" />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900">RE Policy Analyser</h1>
              <p className="text-xs text-gray-500">Dashboard</p>
            </div>
          </div>

          <div className="flex flex-col items-center">
            <h2 className="text-lg font-bold text-gray-800">
              {t.welcome}, {user?.full_name || user?.email || "User"}
            </h2>
            <p className="text-sm font-bold text-gray-700">{t.policyAIDashboard}</p>
          </div>

          <div className="flex items-center space-x-2">
            <Button
              variant="ghost"
              size="sm"
              className="relative p-2 hover:bg-gray-100 rounded-lg"
              onClick={handleBellClick}
              aria-label="New scraped documents"
              aria-expanded={showNotifications}
            >
              <Bell className="w-5 h-5 text-gray-600" />
              {scrapeQueueCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                  {scrapeQueueCount > 99 ? "99+" : scrapeQueueCount}
                </span>
              )}
            </Button>

            <ScrapedDocumentsModal
              open={showNotifications}
              onClose={handleCloseModal}
              scrapeQueue={scrapeQueue}
              scrapeRunning={scrapeRunning}
              scrapeActionLoading={scrapeActionLoading}
              onRunScraper={onRunScraper}
              onAcceptScraped={onAcceptScraped}
              onRejectScraped={onRejectScraped}
            />

            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                className="flex items-center space-x-1 p-2 hover:bg-gray-100 rounded-lg"
                onClick={() => setShowSettingsDropdown(!showSettingsDropdown)}
              >
                <Settings className="w-5 h-5 text-gray-600" />
                <span className="text-sm text-gray-700">{t.settings}</span>
              </Button>

              <AnimatePresence>
                {showSettingsDropdown && (
                  <motion.div
                    initial={{ opacity: 0, y: -10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -10, scale: 0.95 }}
                    className="absolute top-full right-0 mt-2 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50"
                  >
                    <div className="p-2">
                      <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        {t.language}
                      </div>
                      {[
                        { code: "english", name: "English", flag: "🇺🇸" },
                        { code: "hindi", name: "हिन्दी", flag: "🇮🇳" },
                        { code: "marathi", name: "मराठी", flag: "🇮🇳" },
                      ].map((lang) => (
                        <button
                          key={lang.code}
                          type="button"
                          onClick={() => {
                            setLanguage(lang.code);
                            setShowSettingsDropdown(false);
                          }}
                          className={`w-full flex items-center space-x-3 px-3 py-2 text-sm rounded-md transition-colors ${
                            language === lang.code
                              ? "bg-blue-50 text-blue-700"
                              : "hover:bg-gray-100 text-gray-700"
                          }`}
                        >
                          <span className="text-lg">{lang.flag}</span>
                          <span>{lang.name}</span>
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <Button
              variant="ghost"
              size="sm"
              onClick={onLogout}
              className="flex items-center space-x-1 p-2 hover:bg-red-50 hover:text-red-600 rounded-lg transition-colors"
            >
              <LogOut className="w-5 h-5" />
              <span className="text-sm">{t.logout}</span>
            </Button>

            <Button variant="ghost" size="sm" className="p-2 hover:bg-gray-100 rounded-lg">
              <MoreVertical className="w-5 h-5 text-gray-600" />
            </Button>
          </div>
        </div>
      </div>
    </motion.header>
  );
}