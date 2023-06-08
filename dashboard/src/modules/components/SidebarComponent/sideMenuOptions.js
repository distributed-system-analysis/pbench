export const menuOptions = [
  {
    group: { key: "dashboard", title: "Dashboard" },
    submenu: [
      {
        name: "Overview",
        submenu: true,
        key: "overview",
        submenuOf: "dashboard",
        link: "overview",
      },
      {
        name: "Analysis",
        submenu: true,
        key: "analysis",
        submenuOf: "dashboard",
        link: "analysis",
      },
      {
        name: "All runs",
        submenu: true,
        key: "all_runs",
        submenuOf: "dashboard",
        link: "all_runs",
      },
      {
        name: "Results",
        submenu: true,
        key: "results",
        submenuOf: "dashboard",
        link: "results",
      },
      {
        name: "Relay",
        submenu: true,
        key: "relay",
        submenuOf: "dashboard",
        link: "relay",
      },
    ],
  },
  {
    group: { key: "tools", title: "Tools" },
    submenu: [
      {
        name: "Search",
        submenu: true,
        key: "search",
        submenuOf: "tools",
        link: "search",
      },
    ],
  },
];

export const menuOptionsNonLoggedIn = [
  { key: "dashboard", link: "/", name: "Dashboard" },
  { key: "search", link: "search", name: "Search" },
  { key: "expore", link: "explore", name: "Explore" },
];
