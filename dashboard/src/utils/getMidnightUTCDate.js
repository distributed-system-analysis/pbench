export const getTodayMidnightUTCDate = () => {
  const midnightUTC = new Date();
  midnightUTC.setUTCHours(0, 0, 0, 0);
  return midnightUTC;
};
