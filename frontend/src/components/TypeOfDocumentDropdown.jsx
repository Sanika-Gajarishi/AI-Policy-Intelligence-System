import {
  useState,
  useRef,
  useEffect,
  useLayoutEffect,
  useCallback,
} from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "./ui/Button";

const DOCUMENT_TYPE_OPTIONS = [
  { key: "act", label: "Act" },
  { key: "circular", label: "Circular" },
  { key: "electricity_plan", label: "Electricity Plan" },
  { key: "gazette", label: "Gazette" },
  { key: "notification", label: "Notification" },
  { key: "order", label: "Order" },
  { key: "policy", label: "Policy" },
  { key: "regulation", label: "Regulation" },
  { key: "roadmap", label: "Roadmap" },
];

const MENU_MAX_HEIGHT = 256;
const GAP = 8;
const PANEL_Z = 9999;

function measureOpenDirection(rect) {
  const spaceBelow = window.innerHeight - rect.bottom - GAP;
  const spaceAbove = rect.top - GAP;

  return (
    spaceBelow < MENU_MAX_HEIGHT &&
    spaceAbove >= spaceBelow
  );
}

function rectToCoords(rect, openUp) {
  if (openUp) {
    return {
      left: rect.left,
      width: rect.width,
      top: undefined,
      bottom: window.innerHeight - rect.top + GAP,
    };
  }

  return {
    left: rect.left,
    width: rect.width,
    top: rect.bottom + GAP,
    bottom: undefined,
  };
}

export function TypeOfDocumentDropdown({
  documentTypes,
  onDocumentTypeChange,
}) {
  const [open, setOpen] = useState(false);
  const [placement, setPlacement] = useState("below");

  const [coords, setCoords] = useState({
    top: 0,
    left: 0,
    width: 0,
    bottom: undefined,
  });

  const triggerRef = useRef(null);
  const panelRef = useRef(null);

  const updatePosition = useCallback(() => {
    const el = triggerRef.current;
    if (!el || !open) return;

    const rect = el.getBoundingClientRect();
    const openUp = measureOpenDirection(rect);

    setPlacement(openUp ? "above" : "below");
    setCoords(rectToCoords(rect, openUp));
  }, [open]);

  useLayoutEffect(() => {
    if (open) updatePosition();
  }, [open, updatePosition]);

  useEffect(() => {
    if (!open) return;

    const reposition = () =>
      requestAnimationFrame(updatePosition);

    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);

    return () => {
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [open, updatePosition]);

  useEffect(() => {
    if (!open) return;

    const handler = (e) => {
      if (
        triggerRef.current?.contains(e.target) ||
        panelRef.current?.contains(e.target)
      ) {
        return;
      }

      setOpen(false);
    };

    document.addEventListener("mousedown", handler);

    return () =>
      document.removeEventListener("mousedown", handler);
  }, [open]);

  const selectedCount = Object.values(documentTypes).filter(Boolean).length;

  return (
    <div>
      <Button
        ref={triggerRef}
        variant="outline"
        size="sm"
        className="w-full justify-between bg-white hover:bg-gray-50"
        onClick={() => setOpen(!open)}
      >
        <span>Select Document Types</span>

        <span className="text-xs text-gray-500">
          {selectedCount} selected
        </span>
      </Button>

      {createPortal(
        <AnimatePresence>
          {open && (
            <motion.div
              ref={panelRef}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed max-h-64 overflow-y-auto rounded-lg border border-gray-200 bg-white p-2"
              style={{
                zIndex: PANEL_Z,
                left: coords.left,
                width: coords.width,
                top: coords.top,
                bottom: coords.bottom,
              }}
            >
              {DOCUMENT_TYPE_OPTIONS.map((docType) => (
                <div
                  key={docType.key}
                  className="flex items-center gap-2 px-3 py-2 hover:bg-gray-50 cursor-pointer rounded"
                  onClick={() =>
                    onDocumentTypeChange(
                      docType.key,
                      !documentTypes[docType.key]
                    )
                  }
                >
                  <input
                    type="checkbox"
                    checked={documentTypes[docType.key]}
                    readOnly
                  />

                  <span>{docType.label}</span>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </div>
  );
}