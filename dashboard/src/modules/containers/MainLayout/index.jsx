import React from "react";
import { Outlet, useLocation } from "react-router-dom";
import ToastComponent from "modules/components/ToastNotificationComponent";
import { useSelector } from "react-redux";
import HeaderComponent from "modules/components/HeaderComponent";
import {
  Spinner,
  Page,
  PageSection,
  PageSectionVariants,
} from "@patternfly/react-core";
import Sidebar from "modules/components/SidebarComponent";
import TableWithFavorite from "modules/components/TableComponent";
import "./index.less";

const LoginView = () => {
  const { pathname } = useLocation();
  return (
    <>
      {pathname === "/" ? (
        <TableWithFavorite />
      ) : (
        <div>Please login to view the page</div>
      )}
    </>
  );
};

const MainLayout = () => {
  const { alerts } = useSelector((state) => state.toastReducer);
  const isLoading = useSelector((state) => state.loading.isLoading);
  const { loginDetails } = useSelector((state) => state.userAuth);

  return (
    <>
      {alerts && alerts.length > 0 && <ToastComponent />}
      <Page header={<HeaderComponent />} sidebar={<Sidebar />}>
        {loginDetails?.isLoggedIn ? (
          <PageSection variant={PageSectionVariants.light}>
            {isLoading && <Spinner className="spinner" />}
            <Outlet />
          </PageSection>
        ) : (
          <LoginView />
        )}
      </Page>
    </>
  );
};
export default MainLayout;
