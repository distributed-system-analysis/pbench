import React,{useState,useEffect} from 'react'
import { useParams } from 'react-router-dom';
import { useSelector} from 'react-redux';
import "@patternfly/react-core/dist/styles/base.css";
import 'bootstrap/dist/css/bootstrap.min.css';
import Select from 'react-select'
import './datasetList.css'
import axios from 'axios';
import {
  PageSection,
  PageSectionVariants,
  Divider,
  Text,
  TextContent,
  Card,
  CardBody,
  Split,
  SplitItem,
  DatePicker,
  isValidDate,
  yyyyMMddFormat
} from '@patternfly/react-core';
import {Navigate,useNavigate} from 'react-router-dom'
import { COLUMNS } from '../../components/columns';
import Table from '../../components/table/Table'; 
import NavigationDrawer from '../../components/NavigationDrawer/NavigationDrawer';
import moment from 'moment';
import { ClockLoader } from 'react-spinners';
let datapoints=[]
let modifiedData=[]
const userOptions=[
  {value:'access',label:'Access Type'},
  {value:'deletion',label:'Deletion Date'}
]
const accessOptions=[
  {value:'public',label:'Public'},
  {value:'private',label:'Private'}
]
function DatasetList() {
  const [from, setFrom] = useState(moment(new Date(1990,10,4)).format('YYYY/MM/DD'));
  const [isDatasetDeleted,setIsDatasetDeleted]=useState(false)
  const [isDatasetUpdated,setIsDatasetUpdated]=useState(false)
  const [to, setTo] = useState(moment(new Date(2040,10,4)).format('YYYY/MM/DD'));
  const [loading,setLoading]=useState(true)
  const [accessType,setAccessType]=useState({})
  const toValidator = date => isValidDate(from) && date >= from ? '' : 'To date must be less than from date';
  const onFromChange = (_str, date) => {
    const newDataTwo=datapoints.filter(point=>{
      let x=moment(point.metadata["dataset.created"]).format("YYYY/MM/DD")
      return Date.parse(x)>=Date.parse(date)&&Date.parse(x)<=Date.parse(date)  
    })
    modifiedData=newDataTwo
    setDataset(newDataTwo)
    setFrom(new Date(date));
    moment(date).format('DD/MM/YYYY')
    if (isValidDate(date)) {
      date.setDate(date.getDate() + 1);
      setTo(yyyyMMddFormat(date));
      
    }
    else {
      setTo('');
    }
  };
  let owner=useSelector(state=>state.owner)
  let token=useSelector(state=>state.token)
  let isLogin=useSelector(state=>state.isLogin)
  const params=useParams()
  const isUserLogin=params.username===undefined?false:true
  const [extraColumns,setExtraColumns]=useState([])
  const navigate=useNavigate()
  if(localStorage.getItem('token')!==null)
  isLogin=true
  const [dataset,setDataset]=useState([])
 useEffect(()=>{

    const value=localStorage.getItem('token')
    if(value!==null)
    {
      owner=localStorage.getItem('user')
      token=localStorage.getItem('token')
    }
     axios.get(`${process.env.REACT_APP_DATASETLIST}?metadata=dataset.created&${isUserLogin?`owner:${owner}`:''}&metadata=dataset.access&metadata=server.deletion&${isUserLogin?'':'access:public'}`,{
       headers:{
        'Content-Type':'application/json',
        'Accept':'application/json',
        "Authorization":`Bearer ${token}`
       }
     }).then(res=>{
       localStorage.setItem('user',owner)
       localStorage.setItem('token',token)
       datapoints=res.data;
       modifiedData=res.data
       setDataset(res.data)
       setLoading(false)

     }).catch(err=>{
       isLogin=false
       localStorage.clear();
       if(isLogin===false)
        {
          navigate('/')
        }
     })
    
 },[isDatasetDeleted,isDatasetUpdated])
 const customTheme=(theme)=>{
   return {
     ...theme,
     colors:{
       ...theme.colors,
       primary25:'orange',
       primary:'green'
     }
   }
 }
 const accessHandler=(e)=>{
   const newDataThree=modifiedData.filter(point=>{
     return point.metadata["dataset.access"]===e.value
   })
   setDataset(newDataThree)
 }
 if(isLogin||(isUserLogin===false)){
  return (
     <>
        <NavigationDrawer isUserLogin={isUserLogin}/>
        <PageSection variant={PageSectionVariants.light}>
          <TextContent>
            <Text component="h1" className='datasetTitle'>YOUR DATASETS</Text>
          </TextContent>
        </PageSection>
          {loading?(
            <div className='loadingDiv'>
          <ClockLoader color='#36D7B7' size={80} loading={loading}></ClockLoader>
          </div>
          )
          :
          (<>
        <Split className='splitFilter'>
      <SplitItem>
        <DatePicker
          onChange={onFromChange}
          aria-label="Start date"
          placeholder="YYYY-MM-DD"

        />
      </SplitItem>
      <SplitItem style={{ padding: '6px 12px 0 12px' }}>
        to
      </SplitItem>
      <SplitItem>
        <DatePicker
          value={to}
          onChange={date => {
            const newData=datapoints.filter(point=>{
              let x=moment(point.metadata["dataset.created"]).format("YYYY/MM/DD")
              return Date.parse(x)>=Date.parse(from)&&Date.parse(x)<=Date.parse(date)
              
            })
            modifiedData=newData
            setDataset(newData)
            setTo(date);
          }}
          isDisabled={!isValidDate(from)}
          rangeStart={from}
          validators={[toValidator]}
          aria-label="End date"
          placeholder="YYYY-MM-DD"
        />
      </SplitItem>
    </Split>
    <Select
    options={accessOptions}
    theme={customTheme}
    onChange={accessHandler}
    placeholder="Sort by Access type"
    isSearchable
    className="accessBox"
    >
    </Select>
        <Divider component="div" />
        <PageSection>
          <Card>
              <CardBody>
  <span>
          <Select options={userOptions}
            onChange={setExtraColumns}
             theme={customTheme}
            className="selectBox"
            placeholder="Select what you want to see"
            isSearchable
            noOptionsMessage={()=>'You have Selected all Possible columns :)'}
            isMulti
          />
          </span>
               <Table
                  columns={COLUMNS}
                  data={dataset}
                  extraColumns={extraColumns}
                  from={moment(from).format('YYYY/MM/DD')}
                  to={moment(to).format('YYYY/MM/DD')}
                  accessType={accessType}
                  setIsDatasetDeleted={setIsDatasetDeleted}
                  isDatasetDeleted={isDatasetDeleted}
                  setIsDatasetUpdated={setIsDatasetUpdated}
                  isDatasetUpdated={isDatasetUpdated}
                  setLoading={setLoading}
                  isUserLogin={isUserLogin}
                />
              </CardBody>
          </Card>
          </PageSection>
          </>
          )
        }
          

      </>)
      }
      return <Navigate to="/"></Navigate>
}

export default DatasetList
