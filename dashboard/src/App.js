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
      Pbench Dashboard
      <MainLayout />
    </div> 
  );
}

export default App;
