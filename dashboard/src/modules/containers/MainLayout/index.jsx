import "./index.less";

import { Outlet, useNavigate } from "react-router-dom";
import { Page, PageSection, PageSectionVariants } from "@patternfly/react-core";

import Footer from "modules/components/FooterComponent";
import HeaderComponent from "modules/components/HeaderComponent";
import LoadingComponent from "modules/components/LoadingComponent";
import React from "react";
import Sidebar from "modules/components/SidebarComponent";
import ToastComponent from "modules/components/ToastNotificationComponent";
import { useSelector } from "react-redux";

const MainLayout = () => {
  const { alerts } = useSelector((state) => state.toastReducer);
  const navigate = useNavigate();
  return (
    <>
      {alerts && alerts.length > 0 && <ToastComponent />}
      <Page header={<HeaderComponent />} sidebar={<Sidebar />}>
        <PageSection
          variant={PageSectionVariants.light}
          padding={{ default: "noPadding" }}
        >
          <LoadingComponent>
            <Outlet context={navigate} />
          </LoadingComponent>
          <Footer />
        </PageSection>
      </Page>
    </>
  );
};
export default MainLayout;
