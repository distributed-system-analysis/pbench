import React, { useEffect } from 'react';
import favicon from './assets/logo/favicon.ico';
import './App.css';
import MainLayout from "./modules/containers/MainLayout/index";
import '@patternfly/patternfly/patternfly.css';


function App() {  
  
  useEffect(() => {
    const faviconLogo = document.getElementById("favicon");
    faviconLogo.setAttribute("href", favicon);
  }, [])

 
  return (
    <div className="App">
      <b>Pbench Dashboard for {window.endpoints.identification}</b>
      <MainLayout />
    </div> 
  );
}

export default App;
