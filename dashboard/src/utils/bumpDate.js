export const bumpToDate = (date, numberOfDays) => {
  return date.setUTCDate(date.getUTCDate() + numberOfDays);
};
