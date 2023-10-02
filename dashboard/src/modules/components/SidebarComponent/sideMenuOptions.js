import * as APP_ROUTES from "utils/routeConstants";

export const menuOptions = [
  {
    group: { key: "dashboard", title: "Dashboard" },
    submenu: [
      {
        name: "Overview",
        submenu: true,
        key: "overview",
        submenuOf: "dashboard",
        link: APP_ROUTES.OVERVIEW,
      },
      {
        name: "Analysis",
        submenu: true,
        key: "analysis",
        submenuOf: "dashboard",
        link: APP_ROUTES.ANALYSIS,
      },
      {
        name: "All runs",
        submenu: true,
        key: "all_runs",
        submenuOf: "dashboard",
        link: APP_ROUTES.ALL_RUNS,
      },
      {
        name: "Results",
        submenu: true,
        key: "results",
        submenuOf: "dashboard",
        link: APP_ROUTES.RESULTS,
      },
      {
        name: "Visualization",
        submenu: true,
        key: "visualization",
        submenuOf: "dashboard",
        link: APP_ROUTES.VISUALIZATION,
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
        link: APP_ROUTES.SEARCH,
      },
    ],
  },
];

export const menuOptionsNonLoggedIn = [
  { key: "dashboard", link: "/", name: "Dashboard" },
  { key: "search", link: APP_ROUTES.SEARCH, name: "Search" },
  { key: "expore", link: APP_ROUTES.EXPLORE, name: "Explore" },
];
