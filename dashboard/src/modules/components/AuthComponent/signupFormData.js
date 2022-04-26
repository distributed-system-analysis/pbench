export const signupFormData = [
  {
    key: 1,
    label: "First name",
    id: "horizontal-form-first-name",
    name: "firstName",
    isRequired: true,
    type: "text",
  },
  {
    key: 2,
    label: "Last name",
    id: "horizontal-form-last-name",
    name: "lastName",
    isRequired: true,
    type: "text",
  },
  {
    key: 3,
    label: "User name",
    id: "horizontal-form-user-name",
    name: "userName",
    isRequired: true,
    type: "text",
  },
  {
    key: 4,
    label: "Email address",
    id: "horizontal-form-email-address",
    name: "email",
    isRequired: true,
    type: "text",
  },
  {
    key: 5,
    label: "Password",
    id: "horizontal-form-password",
    name: "password",
    isRequired: true,
    type: "password",
  },
  {
    key: 6,
    label: "Confirm password",
    id: "horizontal-form-confirm-password",
    name: "passwordConfirm",
    isRequired: true,
    type: "password",
  },
];


export const passwordConstraintsText = [
  {
    label: "characters",
    name: "passwordLength",
  },
  {
    label: "1 special character",
    name: "passwordSpecialChars",
  },
  {
    label: "1 number",
    name: "passwordContainsNumber",
  },
  {
    label: "1 uppercase letter",
    name: "passwordBlockLetter",
  }
] 
