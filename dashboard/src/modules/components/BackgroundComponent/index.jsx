import React from "react";
import "./index.less";

const BackgroundCard = ({ children }) => {
    return (
        <div className="background-image">
            {children}
        </div>
    )
}  

export default BackgroundCard;
