export const bumpToDate = (date, numberOfDays) => {
  return date.setUTCDate(date.getUTCDate() + numberOfDays);
};

export const dateFromUTCString = (strDate) => {
  return new Date(strDate + "Z");
};

export const getTodayMidnightUTCDate = () => {
  const midnightUTC = new Date();
  midnightUTC.setUTCHours(0, 0, 0, 0);
  return midnightUTC;
};
