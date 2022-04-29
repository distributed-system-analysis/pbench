export const constructUTCDate = (date) => {
  date.setUTCMinutes(date.getUTCMinutes() - date.getTimezoneOffset());
  return date
};
