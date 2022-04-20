import moment from "moment"

export const formatDate=(date,type)=>{
    return moment(date).format(type)
}