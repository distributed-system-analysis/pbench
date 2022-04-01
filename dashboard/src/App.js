import React, { useEffect } from 'react';
import { BrowserRouter, Route, Routes } from "react-router-dom";
import favicon from './assets/logo/favicon.ico';
import './App.css';
import MainLayout from "./modules/containers/MainLayout/index";
import AuthLayout from "./modules/containers/AuthLayout/index";
import * as AppRoutes from "./utils/routeConstants";
import LoginComponent from './modules/components/LoginComponent';
import '@patternfly/patternfly/patternfly.css';

function App() {  
  
  useEffect(() => {
    const faviconLogo = document.getElementById("favicon");
    faviconLogo.setAttribute("href", favicon);
  }, [])
  

  
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<MainLayout />} />
          <Route path={AppRoutes.AUTH} element={<AuthLayout />}>
            <Route path={AppRoutes.AUTH_LOGIN} element={<LoginComponent />} />          
          </Route>
        </Routes>
      </BrowserRouter>
      
    </div> 
  );
}

export default App;
