import React, { useEffect } from 'react';
import { BrowserRouter, Route, Routes } from "react-router-dom";
import favicon from './assets/logo/favicon.ico';
import './App.css';
import MainLayout from "./modules/containers/MainLayout/index";
import * as AppRoutes from "./utils/routeConstants";
import AuthComponent from './modules/components/AuthComponent';
import '@patternfly/patternfly/patternfly.css';

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
