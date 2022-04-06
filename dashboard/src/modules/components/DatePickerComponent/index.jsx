import React,{useState} from 'react'
import { InputGroup, InputGroupText,Split,SplitItem,DatePicker,isValidDate,yyyyMMddFormat, Button } from '@patternfly/react-core'
import moment from 'moment';

function DatePickerWidget({dataArray,setPublicData,controllerName,setDateRange}) {
    const [from, setFrom] = useState(moment(new Date(1990,10,4)).format('YYYY/MM/DD'));
    const [to, setTo] = useState(moment(new Date(2040,10,4)).format('YYYY/MM/DD'));
    const toValidator = date => isValidDate(from) && date >= from ? '' : 'To date must be less than from date';
    let modifiedArray=[];
    const onFromChange = (_str, date) => {
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

      const filterByDate=()=>{
         modifiedArray=dataArray.filter(data=>{
          let formattedData=moment(data.metadata["dataset.created"]).format("YYYY/MM/DD")
          return Date.parse(formattedData)>=Date.parse(from)&&Date.parse(formattedData)<=Date.parse(to)&&(data.name).includes(controllerName)
         })
         setPublicData(modifiedArray)
         setDateRange(from,to)
      }
  return (
    <InputGroup style={{marginLeft:'10px'}}>
    <InputGroupText>Filter By Date</InputGroupText>
        <DatePicker
          onChange={onFromChange}
          aria-label="Start date"
          placeholder="YYYY-MM-DD"

        />
      <InputGroupText>to</InputGroupText>
        <DatePicker
          value={to}
          onChange={(date)=>
            setTo(date)
          }
          isDisabled={!isValidDate(from)}
          rangeStart={from}
          validators={[toValidator]}
          aria-label="End date"
          placeholder="YYYY-MM-DD"
        />
      <Button variant='control' onClick={filterByDate}>Update</Button>
    </InputGroup>
  )
}

export default DatePickerWidget