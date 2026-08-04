/** Canonical energy type filter values (option value) and display labels — "All Types" first, then A–Z by label */
export const ENERGY_TYPE_FILTER_OPTIONS = [
  { value: "", label: "All Types" },
  { value: "BESS", label: "ESS / BESS / Battery Energy Storage System" },
  { value: "Biomass", label: "Biomass" },
  { value: "Clean Energy", label: "Clean Energy" },
  { value: "General", label: "General" },
  { value: "Green Hydrogen", label: "Green Hydrogen" },
  { value: "Grid", label: "Grid" },
  { value: "Hybrid", label: "Hybrid" },
  { value: "Integrated Renewable", label: "Integrated Renewable" },
  { value: "Renewable Energy", label: "Renewable Energy" },
  { value: "Solar", label: "Solar" },
  { value: "Transmission", label: "Transmission" },
  { value: "Wind", label: "Wind" },
];

export const ENERGY_TYPE_ALIASES = {
  ESS: "BESS",
  BESS: "BESS",
  "Battery Energy Storage System": "BESS",
  "Battery Energy Storage Systems": "BESS",
  "Energy Storage System": "BESS",
  "Energy Storage Systems": "BESS",
  Hydro: "Green Hydrogen",
  Hydrogen: "Green Hydrogen",
  "Integrated Clean Energy": "Integrated Renewable",
  "Integreated Clean Energy": "Integrated Renewable",
  "Integreated Renewable": "Integrated Renewable",
  "Integrated Renewable Energy": "Integrated Renewable",
  "Integreated Renewable Energy": "Integrated Renewable",
  Renewable: "Integrated Renewable",
  Hybrid: "Hybrid",
  "Hybrid Energy": "Hybrid",
  "Hybrid Power": "Hybrid",
};

const ENERGY_TYPE_KEYWORD_ALIASES = [
  {
    canonical: "BESS",
    keywords: [
      "ess",
      "bess",
      "battery energy storage system",
      "battery energy storage systems",
      "energy storage system",
      "energy storage systems",
    ],
  },
  {
    canonical: "Integrated Renewable",
    keywords: [
      "integrated renewable",
      "integreated renewable",
      "integrated renewable energy",
      "integreated renewable energy",
      "integrated clean energy",
      "integreated clean energy",
    ],
  },
];

export function normalizePowerTypeForFilter(powerType) {
  if (!powerType) return "General";
  const pt = String(powerType).trim();
  return ENERGY_TYPE_ALIASES[pt] || pt;
}

export function getCanonicalEnergyType(value) {
  if (!value) return "General";
  const normalizedValue = String(value).replace(/[_-]+/g, " ").toLowerCase().trim();
  const directAlias = Object.entries(ENERGY_TYPE_ALIASES).find(
    ([alias]) => alias.toLowerCase() === normalizedValue
  );
  if (directAlias) return directAlias[1];

  const keywordMatch = ENERGY_TYPE_KEYWORD_ALIASES.find(({ keywords }) =>
    keywords.some((keyword) =>
      new RegExp(`\\b${keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`).test(normalizedValue)
    )
  );

  return keywordMatch ? keywordMatch.canonical : normalizePowerTypeForFilter(value);
}

export function matchesEnergyTypeFilter(policy, typeFilter) {
  if (!typeFilter || typeFilter === "") return true;

  const selected = getCanonicalEnergyType(typeFilter)
    .toLowerCase()
    .trim();

  const searchableText = [
    policy?.power_type,
    policy?.energy_type,
    policy?.file,
    policy?.title,
    policy?.description,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  // Solar should also show Hybrid and Integrated docs
  if (selected === "solar") {
    return (
      searchableText.includes("solar") ||
      searchableText.includes("hybrid") ||
      searchableText.includes("integrated")
    );
  }

  // Wind should also show Hybrid and Integrated docs
  if (selected === "wind") {
    return (
      searchableText.includes("wind") ||
      searchableText.includes("hybrid") ||
      searchableText.includes("integrated")
    );
  }

  // Hybrid should ONLY show hybrid docs
  if (selected === "hybrid") {
    return searchableText.includes("hybrid");
  }

  // Integrated Renewable should ONLY show integrated docs
  if (selected === "integrated renewable") {
    return searchableText.includes("integrated");
  }

  // Default behavior for everything else
  return searchableText.includes(selected);
}