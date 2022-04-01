import React from 'react';
import './index.less';
import ToastComponent from "../../components/ToastNotificationComponent";
import LoginComponent  from '../../components/LoginComponent';
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
        <LoginComponent/>
        </>
    )
}
export default MainLayout;