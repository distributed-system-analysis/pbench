export const uid = () => {
  const head = Date.now().toString(36);
  const tail = Math.random().toString(36).substring(2);

  return head + tail;
};

/**
 * Determine whether the specified password meets the requirements for a valid password
 * Requirements include length, presence of upper-case letters, digits, and special characters
 * @function
 * @param {string} password - Entered password
 * @param {number} passwordLength - Minimum required length of password
 * @return {boolean} - true if the password is valid, false otherwise
 */
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

/**
 * Check if email entered by user is valid or not
 * @function
 * @param {string} email - Entered email
 * @return {boolean} - true if the email is valid, false otherwise
 */
export const validateEmail = (email) => {
  return {
    email: !/\S+@\S+\.\S+/.test(email) ? "Enter a valid Email" : "",
  };
};
