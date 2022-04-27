export const constructNewDate = (date) => {
  return new Date(`${date.split(":")[0]}T00:00:00`);
};
