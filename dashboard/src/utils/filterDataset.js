export const filterData = (dataArray, startDate, endDate, searchKey) => {
  return dataArray.filter((data) => {
    let datasetDate = new Date(data.metadata["dataset.created"]);
    return (
      data.name.includes(searchKey) &&
      datasetDate >= startDate &&
      datasetDate <= endDate
    );
  });
};
