import React from 'react';
import ToastComponent from "modules/components/ToastNotificationComponent";
import { useSelector } from "react-redux";
import { Spinner } from '@patternfly/react-core';

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
        <div>Pbench Dashboard</div>
        </>
    )
}
export default MainLayout;
