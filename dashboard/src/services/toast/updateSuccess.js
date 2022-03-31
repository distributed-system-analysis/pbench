import {toast} from "react-toastify";

function updateSuccess(bounce) {
    toast.success("Account Updated Successfully", {
        transition: bounce
      });
}

export default updateSuccess