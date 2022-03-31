import {toast} from "react-toastify";

function incompleteData(bounce) {
    toast.error("Please fill all the fields", {
        transition: bounce
      });
}

export default incompleteData