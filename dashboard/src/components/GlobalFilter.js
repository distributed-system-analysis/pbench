import React from 'react'
import searchIcon from '../assets/search.svg'
import './globalFilter.css'
export const GlobalFilter = ({filter,setFilter}) => {
  return (
    <div className='searchField'>
      <div className='searchIconContainer'>
       <img src={searchIcon} alt="searchIcon" height="20px" width="20px" className='search-Icon'/>
       </div>
      <input type='text' value={filter||''} onChange={e=>setFilter(e.target.value)} placeholder='Search in Dashboard' className='dashboardInput'></input>
      </div>
  )
}
