import React,{useState} from 'react'
import {useTable,useSortBy,useGlobalFilter,usePagination, useRowSelect} from 'react-table'
import { Modal, Button } from '@patternfly/react-core';
import upArrow from '../../assets/up.png'
import downArrow from '../../assets/down.png'
import './table.css'
import { GlobalFilter} from '../GlobalFilter'
import moment from 'moment'
import { Checkbox } from '../checkbox/Checkbox'
import axios from 'axios'
import { cssTransition,ToastContainer } from 'react-toastify'
import deletionSuccess from '../../services/toast/deletionSuccess';
import loginRequired from '../../services/toast/loginRequired';

const bounce = cssTransition({
    enter: "animate__animated animate__bounceIn",
    exit: "animate__animated animate__bounceOut"
  });
function Table({columns,data,extraColumns,from,to,accessType,setIsDatasetDeleted,isDatasetDeleted,setIsDatasetUpdated,isDatasetUpdated,setLoading,isUserLogin}) {
    const [isModalOpen,setIsModalOpen]=useState(false)
    const [modalTitle,setModalTitle]=useState('')
    const {getTableProps,getTableBodyProps,headerGroups,page,nextPage,previousPage,canNextPage,canPreviousPage,pageOptions,gotoPage,pageCount,setPageSize,prepareRow,selectedFlatRows,state,setGlobalFilter}=useTable({
        columns:columns,
        data:data
    },useGlobalFilter,useSortBy,usePagination,useRowSelect,
    hooks => {
        hooks.visibleColumns.push(columns => [
            {
                id: 'selection',
                Header: ({ getToggleAllRowsSelectedProps }) => (
                  <div>
                    <Checkbox {...getToggleAllRowsSelectedProps()}/>
                  </div>
                ),
                Cell: ({ row }) => (
                    <Checkbox {...row.getToggleRowSelectedProps()} />
                ),
                display:true
              },

          ...columns,
        ])
      }
    )

    const {globalFilter,pageIndex,pageSize}=state
    const token=localStorage.getItem('token')
    let extraData={access:false,deletion:false}
    if(extraColumns.length===0)
    {}
    else if(extraColumns.length===2)
    extraData={access:true,deletion:true}
    else if(extraColumns[0].value==='access')
    extraData={access:true,deletion:false}
    else if(extraColumns[0].value==='deletion')
    extraData={access:false,deletion:true}
  const handleModalToggle=()=>{
    setIsModalOpen(!isModalOpen)
}
    const deleteDatasets=(selectedDatasets)=>{
        if(isUserLogin)
        {
        axios.all(selectedDatasets.map(dataset=>axios.post(`${process.env.REACT_APP_DELETE}`,{
             user:localStorage.getItem('user'),
             name:dataset.original.name
        },
        {
            headers:{
                'Content-Type':'application/json',
                'Accept':'application/json',
                "Authorization":`Bearer ${token}`
              }
        }))).then(res=>{
            setIsDatasetDeleted(!isDatasetDeleted)
            handleModalToggle()
            deletionSuccess(bounce)
            })
            .catch(err=>console.log(err))
          }
          else
          {
            loginRequired(bounce)
          }
    }
    const updateDatasets=(selectedDatasets)=>{
        if(isUserLogin)
        {
        axios.all(selectedDatasets.map(dataset=>axios.post(`${process.env.REACT_APP_PUBLISH}`,{
             name:dataset.original.name,
             access:dataset.values["Access Type"]==="private"?"public":"private"
        },
        {
            headers:{
                'Content-Type':'application/json',
                'Accept':'application/json',
                "Authorization":`Bearer ${token}`
              }
        }))).then(res=>{
            setIsDatasetUpdated(!isDatasetUpdated)
            setLoading(true)
            })
            .catch(err=>console.log(err))        
    }
    else
    {
      loginRequired()
    }
  }
    console.log(selectedFlatRows);
  return (
      <>
      <GlobalFilter filter={globalFilter} setFilter={setGlobalFilter}/>
    <table {...getTableProps()} className='dataTable'>
        <thead>
        {
            headerGroups.map(headerGroup=>(
                <tr {...headerGroup.getHeaderGroupProps}>
                    { 
                        headerGroup.headers.map(column=>(
                            
                          column.display===true?(<th {...column.getHeaderProps(column.getSortByToggleProps())}>{
                          column.render('Header')}
                          {
                          column.isSorted?(column.isSortedDesc?<img src={upArrow} alt="asc" height="14px" width="14px"/>:<img src={downArrow} alt="desc" height="14px" width="14px"/>):''}
                          </th>):(extraData.access===true&&extraData.deletion===true?(<th {...column.getHeaderProps(column.getSortByToggleProps())}>{
                          column.render('Header')}
                          {
                          column.isSorted?(column.isSortedDesc?<img src={upArrow} alt="asc" height="14px" width="14px"/>:<img src={downArrow} alt="desc" height="14px" width="14px"/>):''}
                          </th>):(extraData.access===true&&column.Header==="Access Type"?(<th {...column.getHeaderProps(column.getSortByToggleProps())}>{
                          column.render('Header')}
                          {
                          column.isSorted?(column.isSortedDesc?<img src={upArrow} alt="asc" height="14px" width="14px"/>:<img src={downArrow} alt="desc" height="14px" width="14px"/>):''}
                          </th>):(extraData.deletion===true&&column.Header==="Deletion Date"?(<th {...column.getHeaderProps(column.getSortByToggleProps())}>{
                          column.render('Header')}
                          {
                          column.isSorted?(column.isSortedDesc?<img src={upArrow} alt="asc" height="14px" width="14px"/>:<img src={downArrow} alt="desc" height="14px" width="14px"/>):''}
                          </th>):"")))
                        ))
                    }
                </tr>
            ))
        }

        </thead>
        <tbody {...getTableBodyProps()}>
            {   

                page.map((row,i)=>{ 
                    prepareRow(row)
                    return(
                        <tr {...row.getRowProps()}>
                            {
                                row.cells.map(cell=>{

                                    let formattedDate=moment(row.cells[3].value).format('YYYY/MM/DD')
                                    let fromDate=from
                                    let toDate=to
                                    let accessTypeValue=Object.keys(accessType).length===0?false:true                                               
                                    return cell.column.display===true?
                                    ((!accessTypeValue?!accessTypeValue:row.cells[4].value===accessType.value)&&(Date.parse(formattedDate)>=Date.parse(fromDate))&&Date.parse(formattedDate)<=Date.parse(toDate)&&<td {...cell.getCellProps()}>{cell.render('Cell')}</td>):
                                    (extraData.access===true&&extraData.deletion===true)?
                                    ((!accessTypeValue?!accessTypeValue:row.cells[4].value===accessType.value)&&(Date.parse(formattedDate)>=Date.parse(fromDate))&&Date.parse(formattedDate)<=Date.parse(toDate)&&<td {...cell.getCellProps()}>{cell.render('Cell')}</td>):
                                    (extraData.access===true&&cell.column.Header==="Access Type")?
                                    ((!accessTypeValue?!accessTypeValue:row.cells[4].value===accessType.value)&&(Date.parse(formattedDate)>=Date.parse(fromDate))&&Date.parse(formattedDate)<=Date.parse(toDate)&&<td {...cell.getCellProps()}>{cell.render('Cell')}</td>):
                                    (extraData.deletion===true&&cell.column.Header==="Deletion Date")?
                                    ((!accessTypeValue?!accessTypeValue:row.cells[4].value===accessType.value)&&(Date.parse(formattedDate)>=Date.parse(fromDate))&&Date.parse(formattedDate)<=Date.parse(toDate)&&<td {...cell.getCellProps()}>{cell.render('Cell')}</td>):""

                                })
                              
                            }
                        </tr>
                    )
                })
            }
        </tbody>
    </table>
    <div className='pagination'>
        <div>
        <button className={`dlt-btn ${selectedFlatRows.length>0?'btn-enabled':'btn-disabled'}`} onClick={()=>
        {
            setModalTitle('Confirm Deletion')
            handleModalToggle()
            }}>Delete Datasets</button>
        <button className={`chng-btn ${selectedFlatRows.length>0?'btn-enabled-green':'btn-disabled'}`} onClick={()=>{
            setModalTitle('Confirm Update')
            handleModalToggle()}}>Change Access Types</button>
        </div>
        <div className='pagination-container'>
        <span className='pageInfo'>
            Page {' '}
            <strong>
                {pageIndex+1} of {pageOptions.length}
            </strong>{' '}
        </span>
        <span className='gotoPage'>
            | Go to page:{' '}
            <input type='number' className='destinationPage' defaultValue={pageIndex+1} onChange={e=>{
                const pageNumber=e.target.value?Number(e.target.value)-1:0
                gotoPage(pageNumber)
            }}
            style={{width:'50px'}}></input>
        </span>
        <select value={pageSize} onChange={e=>setPageSize(Number(e.target.value))} className='pageSize'>
            {
                [10,25,50].map(pageSize=>(
                    <option key={pageSize} value={pageSize}>Show {pageSize}</option>
                ))
            }
        </select>
        <button onClick={()=>gotoPage(0)} disabled={!canPreviousPage} className='firstPage'>{'<<'}</button>
        <button onClick={()=>previousPage()} disabled={!canPreviousPage} className='previousPage'>Previous</button>
        <button onClick={()=>nextPage()} disabled={!canNextPage} className='nextPage'>Next</button>
        <button onClick={()=>gotoPage(pageCount-1)} disabled={!canNextPage} className='lastPage'>{'>>'}</button>
        </div>
    </div>
    <ToastContainer transition={bounce} position='top-center' hideProgressBar={true} autoClose={3000}/>
    <Modal
          width={'50%'}
          title={modalTitle}
          isOpen={isModalOpen}
          titleIconVariant="warning"
          onClose={handleModalToggle}
          actions={[
            <Button key="confirm" variant="primary" onClick={()=>{
                modalTitle==='Confirm Deletion'?deleteDatasets(selectedFlatRows):updateDatasets(selectedFlatRows)
            }}>
              Confirm
            </Button>,
            <Button key="cancel" variant="link" onClick={handleModalToggle}>
              Cancel
            </Button>
          ]}
        >
          <h3>The following datasets are scheduled for {modalTitle==='Confirm Deletion'?'deletion':'update'}</h3>
          <ul>
          {
            selectedFlatRows.slice(0,5).map((dataset)=>{
              return(<li>
                {dataset.original.name}
              </li>)
            })
          }
          </ul>
          {selectedFlatRows.length>5&& <span>+ {selectedFlatRows.length-5} more</span>}
        </Modal>
    </>
  )
}

export default Table