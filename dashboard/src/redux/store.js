import { createStore } from "redux";
import { loginReducer } from "./loginInfo/loginReducer";

const store=createStore(loginReducer)

export default store