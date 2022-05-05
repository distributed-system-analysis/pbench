import { constructUTCDate } from "./constructDate";
export const filterData = (dataArray, startDate, endDate, controllerValue) => {
  let res = dataArray.filter((data) => {
    let datasetDate = constructUTCDate(`${data.metadata["dataset.created"]}Z`);
    return (
      data.controller.includes(controllerValue) &&
      datasetDate >= startDate &&
      datasetDate <= endDate
    );
  });
  return res;
};
