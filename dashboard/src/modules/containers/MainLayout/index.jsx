import "./index.less";

import { Outlet, useNavigate } from "react-router-dom";
import {
  Page,
  PageSection,
  PageSectionVariants,
  Spinner,
} from "@patternfly/react-core";

import HeaderComponent from "modules/components/HeaderComponent";
import React from "react";
import Sidebar from "modules/components/SidebarComponent";
import ToastComponent from "modules/components/ToastNotificationComponent";
import { useSelector } from "react-redux";

const MainLayout = () => {
  const { alerts } = useSelector((state) => state.toastReducer);
  const isLoading = useSelector((state) => state.loading.isLoading);
  const navigate = useNavigate();
  return (
    <>
      {alerts && alerts.length > 0 && <ToastComponent />}
      <Page header={<HeaderComponent />} sidebar={<Sidebar />}>
        <PageSection
          variant={PageSectionVariants.light}
          padding={{ default: "noPadding" }}
        >
          {isLoading && <Spinner className="spinner" />}

          <Outlet context={navigate} />
        </PageSection>
      </Page>
    </>
  );
};
export default MainLayout;
