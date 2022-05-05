const addOneDay = (date) => {
  const newDate = new Date(date.setDate(date.getDate() + 1));
  const pad = (num) => (num < 10 ? "0" + num : num);
  const mNum = newDate.getMonth() + 1;
  const dNum = newDate.getDate();
  return `${newDate.getFullYear()}-${pad(mNum)}-${pad(dNum)}`;
};

export default addOneDay;
