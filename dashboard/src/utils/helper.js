export const uid = () => {
  const head = Date.now().toString(36);
  const tail = Math.random().toString(36).substring(2);

  return head + tail;
};

export const validatePassword = (password, passwordLength) => {
  return {
    passwordLength: password.length >= passwordLength ? "success" : "error",
    passwordSpecialChars: /[`!@#$%^&*()_+\-=\]{};':"\\|,.<>?~]/.test(password)
      ? "success"
      : "error",
    passwordContainsNumber: /\d/.test(password) ? "success" : "error",
    passwordBlockLetter: /[A-Z]/.test(password) ? "success" : "error",
  };
};

export const validateEmail = (email) => {
  return {
    email: !/\S+@\S+\.\S+/.test(email) ? "Enter a valid Email" : "",
  };
};

