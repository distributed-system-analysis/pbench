export const COLUMNS=[
    {
      Header:"Controller",
      accessor:"controller",
      display:true
    },
    {
       Header:"Name",
       accessor:"name",
       display:true
    },
    {
      Header:"Created At",
    accessor:(m)=>m.metadata["dataset.created"],
    display:true
    },
    {
      Header:"Access Type",
      accessor:(m)=>m.metadata["dataset.access"],
      display:false
    },
    {
      Header:"Deletion Date",
      accessor:(m)=>m.metadata["server.deletion"],
      display:false
    }
]