import React, { useEffect } from 'react';
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import favicon from './assets/logo/favicon.ico';
import './App.css';
import MainLayout from "./modules/containers/MainLayout/index";
import * as AppRoutes from "./utils/routeConstants";
import AuthComponent from './modules/components/AuthComponent';
import '@patternfly/patternfly/patternfly.css';
import Cookies from 'js-cookie';

const AuthRoute = props => {
  const isAuthUser = Cookies.get('isLoggedIn');
  if (isAuthUser) return <Navigate to="/home" />;
  else if (!isAuthUser) return <Navigate to="/auth" />;

  return <Route {...props} />;
};

const GuardedRoute = ({...props}) => {
  const loggedIn = Cookies.get('isLoggedIn');
  if (loggedIn) {
    return <Route {...props} />;
  }
  console.log('You are redirected because you are not logged in')
  return <Navigate to="/login" />
}

function App() {  
  
  useEffect(() => {
    const faviconLogo = document.getElementById("favicon");
    faviconLogo.setAttribute("href", favicon);
  }, []);

  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<MainLayout />} />           
          <Route path={AppRoutes.AUTH} element={<AuthComponent />} />
          <Route path={AppRoutes.AUTH_LOGIN} element={<AuthComponent />} />
          <Route path={AppRoutes.AUTH_SIGNUP} element={<AuthComponent />} />            
        </Routes>
      </BrowserRouter>
      
    </div> 
  );
}

export default App;
