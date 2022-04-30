export const formatDate = (date) => {
  const pad = (num) => (num < 10 ? "0" + num : num);
  const mNum = date.getUTCMonth() + 1;
  const dNum = date.getUTCDate();
  return `${date.getUTCFullYear()}-${pad(mNum)}-${pad(dNum)}`;
};
