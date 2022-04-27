export const filterData = (dataArray, startDate, endDate, controllerValue) => {
  let res = dataArray.filter((data) => {
    let datasetDate = new Date(
      `${data.metadata["dataset.created"].split(":")[0]}T00:00:00`
    );
    return (
      data.controller.includes(controllerValue) &&
      datasetDate >= startDate &&
      datasetDate <= endDate
    );
  });
  return res;
};
