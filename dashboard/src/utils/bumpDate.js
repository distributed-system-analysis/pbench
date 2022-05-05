const bumpToDate = (date, numberOfDays) => {
  const bumpedDate = date.setUTCDate(date.getUTCDate() + numberOfDays);
  return bumpedDate;
};

export default bumpToDate;
