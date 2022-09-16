import React from "react";
import { Outlet } from "react-router-dom";
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
import "./index.less";

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
