export const constructUTCDate = (strDate) => {
  const date = new Date(strDate);
  date.setUTCMinutes(date.getUTCMinutes() - date.getTimezoneOffset());
  return date;
};
