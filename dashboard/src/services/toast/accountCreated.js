import {toast} from "react-toastify";
function accountCreated(bounce)
  {
    toast.success("New Pbench Account created.Login to visit dashboard", {
      transition: bounce
    });
  }

export default accountCreated