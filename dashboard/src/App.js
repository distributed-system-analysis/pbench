import React from 'react'
import { BrowserRouter as Router,Route,Routes } from 'react-router-dom'
import { Provider } from 'react-redux'
import store from './redux/store'
import DatasetList from './pages/datasetList/DatasetList'
import UserAuth from './pages/userAuth/UserAuth'
// import Profile from './pages/profile/Profile'

function App() {
  return (
    <Provider store={store}>
    <>
    <Router>
      <Routes>
    <Route exact path="/" element={<UserAuth/>}/>
    <Route exact path="/dashboard/:username" element={<DatasetList/>}/>
    <Route exact path="/dashboard/public" element={<DatasetList/>}/>
    </Routes>
    </Router>
    </>
    </Provider>
  )
}

export default App