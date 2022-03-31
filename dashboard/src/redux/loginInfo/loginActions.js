import { STORE_LOGIN_INFO } from "./loginTypes"

export const storeLoginInfo=(logindetails)=>{
    return {
        type:STORE_LOGIN_INFO,
        payload:logindetails
    }
}