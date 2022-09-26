import "./index.less";

import {
  Page,
  PageSection,
  PageSectionVariants,
  Spinner,
} from "@patternfly/react-core";

import HeaderComponent from "modules/components/HeaderComponent";
import { Outlet } from "react-router-dom";
import React from "react";
import Sidebar from "modules/components/SidebarComponent";
import ToastComponent from "modules/components/ToastNotificationComponent";
import { useSelector } from "react-redux";

const MainLayout = () => {
  const { alerts } = useSelector((state) => state.toastReducer);
  const isLoading = useSelector((state) => state.loading.isLoading);

  return (
    <>
      {alerts && alerts.length > 0 && <ToastComponent />}
      <Page header={<HeaderComponent />} sidebar={<Sidebar />}>
        <PageSection
          variant={PageSectionVariants.light}
          padding={{ default: "noPadding" }}
        >
          {isLoading && <Spinner className="spinner" />}

          <Outlet />
        </PageSection>
      </Page>
    </>
  );
};
export default MainLayout;
