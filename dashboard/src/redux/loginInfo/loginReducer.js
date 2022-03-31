import { STORE_LOGIN_INFO } from "./loginTypes"
const initialState={
    owner:'',
    token:'',
    isLogin:false
}

export const loginReducer=(state=initialState,action)=>
{
    switch(action.type){
       case STORE_LOGIN_INFO:
           return {
           owner:action.payload.owner,
           token:action.payload.token,
           isLogin:action.payload.isLogin
       }
       default: return state
    }
}