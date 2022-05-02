import * as types from "./types";
import API from "../utils/api";

export const fetchPublicDatasets=()=>async(dispatch)=>{
    try {
        dispatch({type:types.LOADING});
        const response=await API.get('api/v1/datasets/list?metadata=dataset.created&access=public',{
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json",
              Authorization: `Bearer`,
            }});
            dispatch({type:types.COMPLETED})
            return response;
    } catch (error) {
        return error;        
    }
}
