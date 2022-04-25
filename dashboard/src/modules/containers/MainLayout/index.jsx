import React from 'react';
import ToastComponent from "modules/components/ToastNotificationComponent";
import { useSelector } from "react-redux";
import { Page, Spinner } from '@patternfly/react-core';
import NavbarDrawer from 'modules/components/NavbarDrawerComponent';
import Sidebar from 'modules/components/SidebarComponent';
import TableWithFavorite from "modules/components/TableComponent";

const MainLayout = () => {
    const { alerts } = useSelector((state) => state.toastReducer);
    const isLoading = useSelector(state => state.loading.isLoading);
    return (
        <>
        
        {
            alerts && alerts.length > 0 &&
            <ToastComponent />
        }
        {
            isLoading &&
            <Spinner />
        }
        <Page header={<NavbarDrawer/>} sidebar={Sidebar()}>
          <TableWithFavorite />
        </Page>
        </>
    )
}
export default MainLayout;
