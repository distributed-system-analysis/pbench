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
];

export const menuOptionsNonLoggedIn = [
  { key: "dashboard", link: "/", name: "Dashboard" },
  {
    key: "visualization",
    link: APP_ROUTES.VISUALIZATION,
    name: "Visualization",
  },
];
