export const menuOptions = [
  {
    group: "dashboard",
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
      {
        name: "Pbench Kibana",
        submenu: true,
        key: "pbench_kibana",
        submenuOf: "tools",
        link: "#",
      },
    ],
  },
];
