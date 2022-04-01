import React from 'react';
import { Route, Routes, Outlet } from "react-router-dom";
import ToastComponent from "../../components/ToastNotificationComponent";
import LoginComponent  from '../../components/LoginComponent';
import { useSelector } from "react-redux";
import { Spinner } from '@patternfly/react-core';
import * as AppRoutes from "../../../utils/routeConstants";

const AuthLayout = () => {
    const { alerts } = useSelector((state) => state.toastReducer);
    const isLoading = useSelector(state => state.loading.isLoading);
    return (
        <>
       
        <Outlet />
        </>
       
    )
}
export default AuthLayout;