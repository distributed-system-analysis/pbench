import {toast} from "react-toastify";

function editFailed(errMsg,bounce) {
  toast.error(errMsg,{
    transition:bounce
  })
}

export default editFailed